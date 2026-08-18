import subprocess
import threading
import time
import json
from pathlib import Path

LOG_PATH = Path("logs/gpu_monitor.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)  # logs/ 폴더가 없으면 생성

def get_gpu_snapshot() -> dict | None:
    """
    nvidia-smi를 한 번 호출해서 GPU 사용률.VRAM 사용량/전체를 딕셔너리로 반환.
    호출 실패(GPU 없음, nvidia-smi 없음 등) 시 None을 반환해서 이 함수를 쓰는 쪽이 서버 전체를 죽이지 않고 그냥 이번 회차만 건너뛸 수 있게 함
    """
    try:
        # subprocess.check_output: 셀 명령을 실행하고 표준출력(stdout)을 bytes로 받아옴.
        # 리스트로 인자를 넘기면 셸 인젝션 걱정 없이 안전하게 실행됨
        raw = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            timeout=3,  # nvidia-smi가 3초 넘게 응답 없으면 예외 발생 -> 서버가 무한정 멈추는 것 방지
        )
        text = raw.decode().strip()
        # 멀티 GPU 환경이면 줄이 여러 개 나올 수 있으니, 첫 줄(GPU 0)만 사용
        first_line = text.splitlines()[0]
        parts = first_line.split(",")
        util, vram_used, vram_total = [int(p.strip()) for p in parts]
    except Exception:
        return None
    
    return {
        "util_pct": util,
        "vram_used_mb": vram_used,
        "vram_total_mb": vram_total,
    }

    # bytes를 문자열로 디코딩하고, 앞뒤 공백/줄바꿈 제거
    text = raw.decode().strip()
    # "0, 8058, 23034" -> ["0", "8058", " 23034"] (콤마 앞뒤 공백이 아직 남아있음)
    parts = text.split(",")
    # 각 조각에 .strip()을 한번 더 해서 공백 제거 후 int로 변환
    util, vram_used, vram_total = [int(p.strip()) for p in parts]

    return {
        "util_pct": util,
        "vram_used_mb": vram_used,
        "vram_total_mb": vram_total
    }

def _watch_loop():
    """
    무한 루프를 돌면서 2초마다 GPU 스냅샷을 찍고 로그 파일에 한 줄씩 추가.
    이 함수 자체는 절대 return하지 않음 - 서버가 살아있는 한 계속 돎.
    """
    while True:
        try:
            snapshot = get_gpu_snapshot()
            if snapshot is not None:
                snapshot["timestamp"] = time.time()
                with open(LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(snapshot) + "\n")
        except Exception:
            # 예상치 못한 예외(디스크 풀, 권한 문제 등)로도 감시 스레드가 죽으면 안됨
            pass
        time.sleep(2)   # 2초 대기 후 다시 반복

def start_gpu_watcher():
    """
    서버 시작 시 딱 한 번 호출.
    _watch_loop을 별도 스레드에서 실행시켜서 메인 서버 동작을 막지 않게 함.
    """
    t = threading.Thread(target=_watch_loop, daemon=True)
    t.start()