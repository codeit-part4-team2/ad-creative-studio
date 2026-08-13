import pytest
from PIL import Image

from app.backend.services.storyboard import (
    build_storyboard,
    current_source_fingerprint,
)
from app.backend.services.store import HISTORY, PRODUCTS


@pytest.fixture(autouse=True)
def _clear_store():
    PRODUCTS.clear()
    HISTORY.clear()
    yield
    PRODUCTS.clear()
    HISTORY.clear()


@pytest.fixture
def seeded_result(tmp_path):
    static_root = tmp_path / "data"
    output_root = static_root / "outputs"
    output_root.mkdir(parents=True)
    source_path = output_root / "source.png"
    Image.new("RGB", (1024, 1024), "#315a78").save(source_path)
    card_path = output_root / "card.png"
    Image.new("RGB", (1080, 1350), "#f0c040").save(card_path)

    PRODUCTS["prd_1"] = {
        "product_name": "휴대용 선풍기",
        "selling_points": ["USB-C 충전", "8시간 사용"],
    }
    HISTORY.append(
        {
            "job_id": "job_1",
            "product_id": "prd_1",
            "results": [
                {
                    "result_id": "res_abc123",
                    "tone": "practical",
                    "time_slot": "commute_am",
                    "headline": "출근길 필수템",
                    "subcopy": "가볍고 시원하게",
                    "source_image_url": "/files/outputs/source.png",
                    "images": {
                        "thumbnail": "/files/outputs/thumb.png",
                        "sns_card": "/files/outputs/card.png",
                    },
                }
            ],
        }
    )
    return static_root, output_root, source_path


def test_storyboard_uses_only_stored_product_facts(seeded_result):
    static_root, output_root, image_path = seeded_result

    board = build_storyboard(
        "res_abc123",
        output_root=output_root,
        static_root=static_root,
    )

    assert board.image_path == image_path.resolve()
    assert [scene.display_text for scene in board.scenes] == [
        "휴대용 선풍기, 나왔습니다.",
        "광고입니다.",
        "USB-C 충전, 됩니다.",
        "보세요. 전 일합니다.",
    ]
    assert [scene.image_purpose for scene in board.scenes] == [
        "hero",
        "self_aware",
        "benefit",
        "cta",
    ]
    assert board.script_version == "deadpan-ai-v4"
    assert board.pronunciation_review_required is True
    assert all("할인" not in scene.display_text for scene in board.scenes)


def test_storyboard_without_selling_points_keeps_four_scene_contract(
    seeded_result,
):
    static_root, output_root, _ = seeded_result
    PRODUCTS["prd_1"]["selling_points"] = []

    board = build_storyboard(
        "res_abc123",
        output_root=output_root,
        static_root=static_root,
    )

    assert len(board.scenes) == 4
    assert board.scenes[2].display_text == "장점은 화면으로 보세요."


def test_storyboard_rejects_path_outside_output_root(seeded_result, tmp_path):
    static_root, output_root, _ = seeded_result
    secret_path = tmp_path / "secret.png"
    Image.new("RGB", (10, 10), "red").save(secret_path)
    HISTORY[0]["results"][0]["source_image_url"] = "/files/../secret.png"

    with pytest.raises(ValueError, match="허용된 출력 경로"):
        build_storyboard(
            "res_abc123",
            output_root=output_root,
            static_root=static_root,
        )


def test_storyboard_rejects_legacy_result_without_clean_source(seeded_result):
    static_root, output_root, _ = seeded_result
    HISTORY[0]["results"][0].pop("source_image_url")

    with pytest.raises(ValueError, match="무자막 원본 이미지"):
        build_storyboard(
            "res_abc123",
            output_root=output_root,
            static_root=static_root,
        )


def test_storyboard_rejects_non_rush_hour_result(seeded_result):
    static_root, output_root, _ = seeded_result
    HISTORY[0]["results"][0]["time_slot"] = "afternoon"

    with pytest.raises(ValueError, match="출근·퇴근"):
        build_storyboard(
            "res_abc123",
            output_root=output_root,
            static_root=static_root,
        )


def test_source_fingerprint_changes_when_image_bytes_change(seeded_result):
    static_root, output_root, image_path = seeded_result
    first = current_source_fingerprint(
        "res_abc123",
        output_root=output_root,
        static_root=static_root,
    )
    Image.new("RGB", (1080, 1350), "#823838").save(image_path)

    second = current_source_fingerprint(
        "res_abc123",
        output_root=output_root,
        static_root=static_root,
    )

    assert first != second


def test_storyboard_rejects_unknown_result(seeded_result):
    static_root, output_root, _ = seeded_result

    with pytest.raises(ValueError, match="찾을 수 없습니다"):
        build_storyboard(
            "res_missing",
            output_root=output_root,
            static_root=static_root,
        )
