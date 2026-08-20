"""
S1 - 시간대 전환 사이니지 동시 요청 부하 처리 (큐 매니저)

설계 요약 (rev.2 — 8/20 수정)
------------------------------
- 실제 GPU 직렬화는 InferenceEngine 내부의 threading.Lock(`_gpu_lock`)이 이미
  담당하고 있고, 처리 완료 후 `gpu_queue_wait_sec`(실측 대기시간)까지
  응답 바디에 채워주고 있음이 확인됨 (model_server/inference.py 참조).

  → 따라서 이 모듈은 더 이상 요청을 세마포어로 "막지" 않는다.
    막으면 이미지 다운로드/전처리(마스킹 등)까지 불필요하게 직렬화되어
    오히려 대기 시간이 늘어난다 (엔진 내부 락은 GPU 생성 구간만 잠그므로,
    바깥에서 전체를 막을 이유가 없음).

  → 이 모듈의 역할은 딱 하나: 지금 몇 명이 큐에 들어와 있는지 "관찰"해서
    사전(prediction) 대기 순번 / 예상 대기 시간을 계산해 UX용으로 보여주는 것.
    실측치는 엔진이 반환하는 gpu_queue_wait_sec(사후 값)가 담당.

- 기존 /infer 응답 바디(JSON 스키마)는 변경하지 않는다.
  예상 대기 시간은 응답 헤더(X-Estimated-Wait-Sec, X-Queue-Position)로만 노출.
  → 박재철님 프론트 계약 변경 없음.
- main.py 쪽 사용법(`async with queue_manager.slot(request_id) as ctx:`)은
  그대로 유지 — 내부 동작만 "차단"에서 "카운팅"으로 바뀜.

TODO(재헌):
  - DEFAULT_AVG_GEN_SEC 값을 gpu_monitor.jsonl 또는 실측 gen_time_sec 평균으로 교체
  - 필요하면 estimated_wait_sec를 engine의 gpu_queue_wait_sec 실측 롤링 평균과
    합쳐서 더 정확하게 만들기 (지금은 전체 요청 처리시간 기준 근사치)
"""

import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field


# ── 설정값 ────────────────────────────────────────────────
DEFAULT_AVG_GEN_SEC = 5.0   # TODO: 실측값으로 교체 (fast_composite/768/4-step 기준)
ROLLING_WINDOW = 20          # 최근 N건으로 평균 갱신


@dataclass
class QueueManager:
    """실제 동시성 제어(직렬화)는 하지 않는다 — 그건 InferenceEngine._gpu_lock 몫.
    이 클래스는 "지금 큐에 몇 명이 들어와 있는가"만 관찰해서
    대기 순번 / 예상 대기 시간을 계산해주는 관측용(non-blocking) 매니저.
    FastAPI lifespan에서 앱 시작 시 인스턴스 하나만 생성해서 공유합니다.
    """

    _waiting: deque = field(default_factory=deque)   # 현재 처리 중/대기 중인 요청 id들 (순번 계산용)
    _recent_durations: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_WINDOW)
    )

    @property
    def avg_gen_sec(self) -> float:
        if not self._recent_durations:
            return DEFAULT_AVG_GEN_SEC
        return sum(self._recent_durations) / len(self._recent_durations)

    def queue_position(self, request_id: str) -> int:
        """1부터 시작. 아직 대기열에 없으면 대기열 맨 뒤 기준으로 계산."""
        if request_id in self._waiting:
            return list(self._waiting).index(request_id) + 1
        return len(self._waiting) + 1

    def estimated_wait_sec(self, request_id: str) -> float:
        # 내 앞에 몇 명이 처리 중/대기 중인지 * 평균 처리시간
        ahead = self.queue_position(request_id) - 1
        return round(ahead * self.avg_gen_sec, 1)

    @asynccontextmanager
    async def slot(self, request_id: str):
        """요청 하나가 큐에 등록되어 처리되는 동안 쓰는 관측용 컨텍스트.
        더 이상 GPU 접근을 막지 않는다 — 등록/해제와 소요시간 기록만 한다.
        실제 GPU 직렬화는 engine.run() 내부의 threading.Lock이 담당.

        사용 예 (main.py, 기존 코드 그대로):
            async with queue_manager.slot(request_id) as ctx:
                result = await asyncio.to_thread(engine.run, ...)
            # ctx.duration_sec 에 (다운로드~생성 포함) 전체 처리 시간 기록됨
        """
        self._waiting.append(request_id)
        start = time.monotonic()
        ctx = _SlotContext()
        try:
            yield ctx
        finally:
            ctx.duration_sec = round(time.monotonic() - start, 2)
            self._recent_durations.append(ctx.duration_sec)
            if request_id in self._waiting:
                self._waiting.remove(request_id)


@dataclass
class _SlotContext:
    duration_sec: float = 0.0