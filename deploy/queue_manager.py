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

  [rev.3 — PR 리뷰 반영] 예상 대기시간(avg_gen_sec) 계산 시 "요청 전체 소요시간"
  (다운로드+전처리+생성+저장)이 아니라 "실제 GPU 점유 시간"(stage_times_sec.generate)
  만으로 평균을 내도록 수정. 다운로드/전처리는 여러 요청이 동시에 겹쳐 진행되므로
  전체 시간 기준으로 예측하면 실제 대기시간보다 과대추정됨 (리뷰에서 지적된 4번째
  요청 기준 52.9초 예측 vs 실측 3.72초, 약 14배 괴리).

- 기존 /infer 응답 바디(JSON 스키마)는 변경하지 않는다.
  예상 대기 시간은 응답 헤더(X-Estimated-Wait-Sec, X-Queue-Position)로만 노출.
  → 박재철님 프론트 계약 변경 없음.
- main.py 쪽 사용법(`async with queue_manager.slot(request_id) as ctx:`)은
  그대로 유지 — 내부 동작만 "차단"에서 "카운팅"으로 바뀜.

TODO(재헌):
  - DEFAULT_AVG_GEN_SEC 값을 gpu_monitor.jsonl 또는 실측 generate 단계 평균으로 교체
"""

import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field


# ── 설정값 ────────────────────────────────────────────────
DEFAULT_AVG_GEN_SEC = 13.5   # 실측 generate 단계 평균 (fast_composite/768/4-step, 캐시 미스 기준, 8/20 측정: 13.58/12.00/15.16)
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
        """실제 GPU 점유 시간(generate 단계)만의 평균.
        다운로드/전처리는 여러 요청이 병렬로 겹치므로 여기 포함하지 않는다.
        """
        if not self._recent_durations:
            return DEFAULT_AVG_GEN_SEC
        return sum(self._recent_durations) / len(self._recent_durations)

    def record_gpu_duration(self, generate_sec: float) -> None:
        """요청 완료 후, 엔진이 반환한 실제 GPU 생성 시간
        (stage_times_sec['generate'])을 롤링 평균에 반영한다.
        main.py에서 결과를 받은 직후 호출해야 한다.
        """
        self._recent_durations.append(generate_sec)

    def queue_position(self, request_id: str) -> int:
        """1부터 시작하는 대기열 맨 뒤 순번.

        주의: main.py는 항상 slot() 진입 "전"에 이 메서드를 호출하므로,
        request_id가 이미 self._waiting에 들어있는 경우는 현재 구조상 발생하지 않는다.
        (과거에는 이미 대기 중인 요청의 순번을 재조회하는 경우까지 방어적으로 처리했으나,
        검증되지 않은 채 남아있던 코드라 PR 리뷰 반영해 단순화함.)
        """
        return len(self._waiting) + 1

    def estimated_wait_sec(self, request_id: str) -> float:
        # 내 앞에 몇 명이 처리 중/대기 중인지 * 평균 처리시간
        ahead = self.queue_position(request_id) - 1
        return round(ahead * self.avg_gen_sec, 1)

    @asynccontextmanager
    async def slot(self, request_id: str):
        """요청 하나가 큐에 등록되어 처리되는 동안 쓰는 관측용 컨텍스트.
        GPU 접근을 막지 않는다 — 등록/해제와 "전체" 소요시간(참고용) 기록만 한다.
        실제 GPU 직렬화는 engine.run() 내부의 threading.Lock이 담당.

        주의: ctx.duration_sec은 다운로드~저장까지 포함한 전체 처리 시간이라
        예상 대기시간(avg_gen_sec) 계산에는 쓰지 않는다 (아래 record_gpu_duration 참조).
        X-Gen-Time-Sec 헤더 등 "이번 요청이 총 얼마나 걸렸는지" 참고용으로만 사용.

        사용 예 (main.py):
            async with queue_manager.slot(request_id) as ctx:
                result = await asyncio.to_thread(engine.run, ...)
            queue_manager.record_gpu_duration(result["stage_times_sec"]["generate"])
            # ctx.duration_sec 에 전체 처리 시간 기록됨 (X-Gen-Time-Sec용)
        """
        self._waiting.append(request_id)
        start = time.monotonic()
        ctx = _SlotContext()
        try:
            yield ctx
        finally:
            ctx.duration_sec = round(time.monotonic() - start, 2)
            if request_id in self._waiting:
                self._waiting.remove(request_id)


@dataclass
class _SlotContext:
    duration_sec: float = 0.0