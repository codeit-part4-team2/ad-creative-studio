from app.backend.services.comic_script import (
    ComicLineKind,
    PronunciationLexicon,
    build_comic_script,
)


def test_script_has_one_self_aware_beat_and_factual_cta():
    script = build_comic_script(
        product_name="테스트 전자레인지",
        selling_points=("간편 조리",),
        time_slot="commute_am",
        lexicon=PronunciationLexicon({}),
    )

    assert [line.kind for line in script.lines] == [
        ComicLineKind.INTRO,
        ComicLineKind.SELF_AWARE,
        ComicLineKind.BENEFIT,
        ComicLineKind.CTA,
    ]
    assert sum(line.kind is ComicLineKind.SELF_AWARE for line in script.lines) == 1
    assert script.lines[-1].display_text.endswith("확인해 보세요.")
    assert all("할인" not in line.display_text for line in script.lines)


def test_script_uses_only_one_stored_selling_point():
    script = build_comic_script(
        product_name="휴대용 선풍기",
        selling_points=("USB-C 충전", "8시간 사용"),
        time_slot="commute_pm",
        lexicon=PronunciationLexicon({"USB-C 충전": "유에스비 씨 충전"}),
    )

    benefit = next(
        line for line in script.lines if line.kind is ComicLineKind.BENEFIT
    )
    assert benefit.display_text == "주요 특징은 USB-C 충전입니다."
    assert benefit.spoken_text == "주요 특징은 유에스비 씨 충전입니다."


def test_unknown_ascii_or_number_pronunciation_requires_review():
    result = PronunciationLexicon({}).resolve("ABC-1200")

    assert result.display_text == "ABC-1200"
    assert result.spoken_text == "ABC-1200"
    assert result.review_required is True


def test_registered_pronunciation_is_used_without_review():
    result = PronunciationLexicon(
        {"ABC-1200": "에이비씨 천이백"}
    ).resolve("ABC-1200")

    assert result.spoken_text == "에이비씨 천이백"
    assert result.review_required is False


def test_hangul_only_text_does_not_require_manual_pronunciation():
    result = PronunciationLexicon({}).resolve("휴대용 선풍기")

    assert result.spoken_text == "휴대용 선풍기"
    assert result.review_required is False

