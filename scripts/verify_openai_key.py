"""
OpenAI key가 실제로 동작하는지 최소 비용으로 확인하는 스크립트.

사용법:
    cp .env.example .env   # OPENAI_API_KEY 채운 뒤
    python scripts/verify_openai_key.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.backend.services import openai_client as oc  # noqa: E402


def main():
    print(f"모델: {oc.DEFAULT_MODEL}")
    print("호출 중...")
    result = oc.call_text_model(
        "다음 문장을 한 문장으로 요약해줘: 소형가전 광고 콘텐츠 생성 서비스 테스트입니다.",
        system="당신은 광고 카피라이터입니다.",
    )
    print("응답:", result)
    print("누적 사용량:", oc.get_usage())


if __name__ == "__main__":
    main()
