import io
import hashlib
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.schemas.video import VideoJob
from app.backend.services import store, overlay, auth
from app.backend.services.scene_images import SceneImage, SceneImageSet
from app.backend.services.tts_provider import TTSAudio
from app.backend.services.video_renderer import RenderResult
from app.backend.services.video_workflow import VideoWorkflowService
from app.backend.services.youtube_publisher import DisabledPublisher
from app.backend.services.store import PRODUCTS, JOBS, HISTORY
from app.backend.schemas.generation import GenerationRequest
from app.backend.api.generations import build_generation_plan

client = TestClient(app)


class _ApiTestRenderer:
    def validate_runtime(self) -> None:
        return None

    def render(self, storyboard, *, scene_images, speech_audio, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"test-video")
        return RenderResult(
            output_path=output_path,
            sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            duration_sec=12.5,
            width=1080,
            height=1920,
            video_codec="h264",
            audio_codec="aac",
            tts_audio_sha256=hashlib.sha256(b"test-tts").hexdigest(),
            scene_image_sha256s=scene_images.sha256s,
            caption_layout_version="bright-outline-v1",
        )


class _ApiTestSceneProvider:
    def build(self, *, storyboard, product_image_url, output_dir):
        images = []
        for index, purpose in enumerate(("hero", "self_aware", "benefit")):
            path = output_dir / f"{purpose}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"scene-{index}".encode("ascii"))
            images.append(
                SceneImage(
                    purpose=purpose,
                    path=path.resolve(),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    source="api-test",
                )
            )
        return SceneImageSet(images=tuple(images))


class _ApiTestTTSProvider:
    def validate_runtime(self) -> None:
        return None

    def synthesize(self, spoken_text: str, output_path: Path) -> TTSAudio:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(spoken_text.encode("utf-8"))
        return TTSAudio(
            path=output_path.resolve(),
            duration_sec=1.0,
            sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            engine="melotts-korean",
            voice_preset="deadpan-ai-v1",
        )


@pytest.fixture(autouse=True)
def _clear_store(tmp_path, monkeypatch):
    """
    ?ㅼ젣 媛쒕컻???곗씠??data/store.json, data/outputs/쨌data/videos/??湲곗〈 ?뚯씪)瑜?    ?덈? 嫄대뱶由ъ? ?딅룄濡?寃⑸━?쒕떎.
    - store.STORE_PATH: pytest??tmp_path(?뚯뒪??醫낅즺 ???먮룞 ?뺣━?섎뒗 ?꾩떆 ?붾젆?곕━)濡?由щ떎?대젆??
      ?꾩쟾??蹂꾨룄 ?뚯씪?대씪 ?ㅼ젣 data/store.json? ?쎌????곗????딅뒗??
    - overlay.OUTPUT_DIR: data/outputs/ ?먯껜媛 ?꾨땲??洹?"?섏쐞"???뚯뒪???꾩슜 ?쒕툕?대뜑濡?由щ떎?대젆??
      ?뺤쟻 ?뚯씪 ?쒕튃(/files/...)? data/ ?붾젆?곕━ 留덉슫?몄뿉 臾띠뿬?덉뼱 ?꾩쟾??諛뽰쑝濡?類????녾린 ?뚮Ц??
      理쒖냼??湲곗〈 ?곕え ?뚯씪???덈뒗 data/outputs/ 理쒖긽?꾨뒗 ??嫄대뱶由ш퀬 ?쒕툕?대뜑留?留뚮뱾怨?吏?대떎.
    - ?ㅼ젣 肄붾? ?쇱툩 ?뚰겕?뚮줈???뚯뒪???꾩슜 ?λ㈃쨌TTS쨌?뚮뜑?щ? 二쇱엯?섍퀬, 紐⑤뱺 ?곸긽 ?뚯씪??      tmp_path ?꾨옒???앹꽦??data/videos/瑜?嫄대뱶由ъ? ?딅뒗??
    - ?몄쬆(customer_id+PIN) ?꾩엯 ??紐⑤뱺 ?곹뭹/?앹꽦 endpoint媛 濡쒓렇?몄쓣 ?붽뎄?섍쾶 ?먮떎.
      媛쒕퀎 ?뚯뒪???섏떗 媛쒕? ?꾨? 怨좎퀜???ㅻ뜑瑜??ｊ쾶 ?섎뒗 ??? ?ш린???뚯뒪???꾩슜
      怨좉컼?щ? ?섎굹 留뚮뱾??濡쒓렇?명븯怨?洹??좏겙??怨듭슜 client ?몄뒪?댁뒪??湲곕낯 ?ㅻ뜑濡?      諛뺤븘?붾떎 - 洹몃윭硫?湲곗〈 ?뚯뒪??肄붾뱶??????以꾨룄 ??嫄대뱶?ㅻ룄 ?쒕떎.
    """
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")

    test_output_dir = overlay.OUTPUT_DIR / f"_pytest_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(overlay, "OUTPUT_DIR", test_output_dir)

    app.state.video_workflow = VideoWorkflowService(
        renderer=_ApiTestRenderer(),
        scene_image_provider=_ApiTestSceneProvider(),
        tts_provider=_ApiTestTTSProvider(),
        publisher=DisabledPublisher("test_channel"),
        now=lambda: datetime.now(timezone.utc),
        video_dir=tmp_path / "videos",
        work_dir=tmp_path / "video-work",
    )

    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    store.VIDEO_JOBS.clear()
    auth.CUSTOMERS.clear()
    auth.SESSIONS.clear()
    auth.create_customer("CUS-TEST", "?뚯뒪?몄긽??, "000000")
    token = auth.verify_login("CUS-TEST", "000000")
    client.headers["Authorization"] = f"Bearer {token}"
    yield
    if test_output_dir.exists():
        shutil.rmtree(test_output_dir)  # ?뚯뒪?멸? 留뚮뱺 ?쒕툕?대뜑留???젣 - ?뺤젣 ?뚯씪? ??嫄대뱶由?    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    store.VIDEO_JOBS.clear()
    auth.CUSTOMERS.clear()
    auth.SESSIONS.clear()


def _upload_product(name="?ㅽ? ?먯뼱?꾨씪?댁뼱 5L"):
    files = {"image": ("p.png", io.BytesIO(b"fakebytes"), "image/png")}
    data = {"product_name": name, "price": 89000, "selling_points": "湲곕쫫 ?놁씠,1?멸?援?}
    r = client.post("/api/v1/products", files=files, data=data)
    assert r.status_code == 200
    return r.json()["product_id"]


def test_generate_returns_404_for_unknown_product():
    r = client.post("/api/v1/generations", json={"product_id": "prd_nope", "time_slots": ["morning"]})
    assert r.status_code == 404


def test_generate_rejects_empty_time_slots():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": []})
    assert r.status_code == 400


def test_generate_rejects_more_than_max_time_slots():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={
        "product_id": pid,
        "time_slots": ["morning", "commute_am", "afternoon", "commute_pm"],
    })
    assert r.status_code == 400


def test_generate_returns_202_and_expected_total_count():
    pid = _upload_product()
    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["morning", "evening"],
            "output_formats": ["sns_card", "story_vertical"],
        },
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    # ??4醫?湲곕낯媛? x ?쒓컙? 2媛?x 鍮꾩쑉 2媛?= ?묒뾽 ?⑥쐞 16媛?    time.sleep(0.5)  # BackgroundTasks ?꾨즺 ?湲?    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["total_count"] == 16


def test_output_formats_increase_job_work_without_duplicating_prompt_plan():
    """臾멸뎄 怨꾪쉷? ?쒓컙?x?ㅼ씠怨??ㅼ젣 ?대?吏 ?묒뾽?됰쭔 鍮꾩쑉 ?섎쭔??利앷??쒕떎."""
    product = {"product_name": "而ㅽ뵾硫붿씠而?, "price": 50000, "selling_points": []}

    req_one_format = GenerationRequest(
        product_id="x", time_slots=["morning", "evening"], output_formats=["thumbnail"]
    )
    req_two_formats = GenerationRequest(
        product_id="x", time_slots=["morning", "evening"],
        output_formats=["sns_card", "story_vertical"],
    )

    plan_one = build_generation_plan(req_one_format, product)
    plan_two = build_generation_plan(req_two_formats, product)

    # 臾멸뎄 怨꾪쉷? ?쒓컙? 2 x ??4(湲곕낯媛? = 8 濡??숈씪?섎떎.
    assert len(plan_one) == 8
    assert len(plan_two) == 8
    assert len(plan_one) == len(plan_two)


def test_full_flow_populates_history():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["commute_am"]})
    job_id = r.json()["job_id"]

    time.sleep(0.5)
    result = client.get(f"/api/v1/generations/{job_id}")
    assert result.status_code == 200
    assert len(result.json()["results"]) == 4  # ??4醫?
    history = client.get("/api/v1/history").json()
    assert any(h["job_id"] == job_id for h in history)


def test_copy_patch_updates_job_and_history():
    pid = _upload_product()

    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["morning"],
        },
    )
    job_id = r.json()["job_id"]

    time.sleep(0.5)

    result_response = client.get(f"/api/v1/generations/{job_id}")
    assert result_response.status_code == 200

    results = result_response.json()["results"]
    assert results

    target = results[0]
    result_id = target["result_id"]

    # PATCH ???대?吏 ?곹깭 ???    old_images = target["images"].copy()
    assert old_images

    old_image_bytes = {
        image_format: client.get(url).content
        for image_format, url in old_images.items()
    }

    patch = client.patch(
        f"/api/v1/generations/{job_id}/copy",
        json={
            "result_id": result_id,
            "headline": "???ㅻ뱶?쇱씤",
            "subcopy": "???쒕툕移댄뵾",
        },
    )

    assert patch.status_code == 200
    assert patch.json()["job_id"] == job_id
    assert patch.json()["result_id"] == result_id
    assert patch.json()["headline"] == "???ㅻ뱶?쇱씤"
    assert patch.json()["subcopy"] == "???쒕툕移댄뵾"

    # JOBS 履?寃곌낵媛 ?ㅼ젣濡??섏젙?먮뒗吏 ?뺤씤
    updated_result = client.get(f"/api/v1/generations/{job_id}")
    assert updated_result.status_code == 200

    updated_target = next(
        item
        for item in updated_result.json()["results"]
        if item["result_id"] == result_id
    )

    assert updated_target["headline"] == "???ㅻ뱶?쇱씤"
    assert updated_target["subcopy"] == "???쒕툕移댄뵾"

    # 臾멸뎄 ?섏젙 ???ㅼ젣 PNG媛 ?ㅼ떆 ?앹꽦?먮뒗吏 ?뺤씤
    new_images = updated_target["images"]

    assert new_images.keys() == old_images.keys()

    for image_format, new_url in new_images.items():
        old_url = old_images[image_format]

        # ??PNG ?뚯씪 URL?댁뼱????        assert new_url != old_url

        new_image_response = client.get(new_url)
        assert new_image_response.status_code == 200
        assert new_image_response.headers["content-type"] == "image/png"

        # ?ㅼ젣 PNG ?댁슜??蹂寃쎈릺?댁빞 ??        assert new_image_response.content != old_image_bytes[image_format]

    # HISTORY?먮룄 ?숈씪???섏젙??諛섏쁺?먮뒗吏 ?뺤씤
    history = client.get("/api/v1/history")
    assert history.status_code == 200

    history_entry = next(
        item
        for item in history.json()
        if item["job_id"] == job_id
    )

    history_target = next(
        item
        for item in history_entry["results"]
        if item["result_id"] == result_id
    )

    assert history_target["headline"] == "???ㅻ뱶?쇱씤"
    assert history_target["subcopy"] == "???쒕툕移댄뵾"
    assert history_target["images"] == new_images

def test_copy_patch_rejects_blank_copy():
    pid = _upload_product()

    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["morning"],
        },
    )
    job_id = r.json()["job_id"]

    time.sleep(0.5)

    result_response = client.get(f"/api/v1/generations/{job_id}")
    result_id = result_response.json()["results"][0]["result_id"]

    patch = client.patch(
        f"/api/v1/generations/{job_id}/copy",
        json={
            "result_id": result_id,
            "headline": "   ",
            "subcopy": "?뺤긽 ?쒕툕移댄뵾",
        },
    )

    assert patch.status_code == 422

def test_copy_patch_rejects_missing_result():
    pid = _upload_product()

    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["morning"],
        },
    )
    job_id = r.json()["job_id"]

    time.sleep(0.5)

    patch = client.patch(
        f"/api/v1/generations/{job_id}/copy",
        json={
            "result_id": "res_doesnotexist",
            "headline": "???ㅻ뱶?쇱씤",
            "subcopy": "???쒕툕移댄뵾",
        },
    )

    assert patch.status_code == 404


def test_copy_patch_rejects_missing_job():
    patch = client.patch(
        "/api/v1/generations/job_doesnotexist/copy",
        json={
            "result_id": "res_doesnotexist",
            "headline": "x",
            "subcopy": "y",
        },
    )

    assert patch.status_code == 404


def test_favorite_toggle_flow():
    """S3 ???앹꽦 ?대젰 利먭꺼李얘린 ?좉?."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    history = client.get("/api/v1/history").json()
    entry = next(h for h in history if h["job_id"] == job_id)
    assert entry["favorite"] is False  # 湲곕낯媛?
    toggled = client.patch(f"/api/v1/history/{job_id}/favorite")
    assert toggled.status_code == 200
    assert toggled.json()["favorite"] is True

    favorites_only = client.get("/api/v1/history", params={"favorite_only": True}).json()
    assert any(h["job_id"] == job_id for h in favorites_only)

    # ?ㅼ떆 ?좉??섎㈃ 爰쇱쭚
    toggled_again = client.patch(f"/api/v1/history/{job_id}/favorite")
    assert toggled_again.json()["favorite"] is False

    favorites_only_after = client.get("/api/v1/history", params={"favorite_only": True}).json()
    assert not any(h["job_id"] == job_id for h in favorites_only_after)


def test_favorite_toggle_404_for_unknown_job():
    resp = client.patch("/api/v1/history/job_doesnotexist/favorite")
    assert resp.status_code == 404


def test_generation_result_images_are_real_files_not_mock_url():
    """M3+S2 ??洹쒓꺽蹂꾨줈 ?ㅼ젣 ?ㅻ쾭?덉씠 ?대?吏媛 ?앹꽦?섎뒗吏 (???댁긽 placehold.co mock ?꾨떂)."""
    pid = _upload_product()
    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["commute_am"],
            "output_formats": ["story_vertical"],
        },
    )
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    first_tone = result["results"][0]
    assert "placehold.co" not in str(first_tone["images"])
    assert first_tone["source_image_url"].startswith("/files/outputs/")
    source_response = client.get(first_tone["source_image_url"])
    assert source_response.status_code == 200
    assert first_tone["source_image_url"] not in first_tone["images"].values()
    for fmt, url in first_tone["images"].items():
        assert url.startswith("/files/outputs/")
        served = client.get(url)
        assert served.status_code == 200  # ?뺤쟻 ?쒕튃?쇰줈 ?ㅼ젣 ?대┝


def test_generate_rejects_duplicate_while_job_in_progress():
    """以묐났 ?앹꽦 ?붿껌 諛⑹? ??媛숈? ?곹뭹??吏꾪뻾 以?queued/processing)??job???덉쑝硫?409."""
    pid = _upload_product()
    JOBS["job_fake_inprogress"] = {
        "customer_id": "CUS-TEST",
        "status": "processing",
        "progress": 10,
        "current_step": None,
        "completed_count": 0,
        "total_count": 4,
        "estimated_seconds": 60,
        "product_id": pid,
        "request": {},
        "result": None,
        "error_message": None,
    }

    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    assert r.status_code == 409


def test_generate_allows_new_request_after_previous_completed():
    """?댁쟾 job??completed/failed硫?以묐났 諛⑹?????嫄몃━怨??덈줈 ?앹꽦 媛?ν빐???쒕떎."""
    pid = _upload_product()
    JOBS["job_fake_done"] = {
        "customer_id": "CUS-TEST",
        "status": "completed",
        "progress": 100,
        "current_step": None,
        "completed_count": 4,
        "total_count": 4,
        "estimated_seconds": 60,
        "product_id": pid,
        "request": {},
        "result": [],
        "error_message": None,
    }

    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    assert r.status_code == 202


def test_download_one_returns_png_file():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    tone = result["results"][0]["tone"]

    resp = client.get(f"/api/v1/download/{job_id}", params={"tone": tone, "output_format": "thumbnail"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_download_one_404_for_unknown_job():
    resp = client.get("/api/v1/download/job_nope", params={"tone": "emotional", "output_format": "thumbnail"})
    assert resp.status_code == 404


def test_download_one_409_for_unfinished_job():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    # ?꾨즺 湲곕떎由ъ? ?딄퀬 諛붾줈 ?ㅼ슫濡쒕뱶 ?쒕룄
    JOBS[job_id]["status"] = "processing"  # ?뺤떎?섍쾶 誘몄셿猷??곹깭濡?怨좎젙
    resp = client.get(f"/api/v1/download/{job_id}", params={"tone": "emotional", "output_format": "thumbnail"})
    assert resp.status_code == 409


def test_download_all_returns_zip_with_all_images():
    pid = _upload_product()
    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["morning"],
            "output_formats": ["thumbnail", "sns_card"],
        },
    )
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    resp = client.get(f"/api/v1/download/{job_id}/all")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    # ??4醫?x ?좏깮 鍮꾩쑉 2醫?= 8媛??뚯씪
    assert len(names) == 8


def test_download_rejects_path_traversal_attempt():
    """_url_to_path媛 data/outputs/ 諛뽰쑝濡??섍???寃쎈줈瑜?嫄곕??섎뒗吏 (諛⑹뼱??寃利?."""
    from app.backend.api.download import _url_to_path
    from fastapi import HTTPException

    try:
        _url_to_path("/files/../../etc/passwd")
        assert False, "?덉쇅媛 諛쒖깮?덉뼱????
    except HTTPException as e:
        assert e.status_code == 400


def test_exposure_returns_404_for_unknown_product():
    resp = client.get("/api/v1/exposure/prd_doesnotexist")
    assert resp.status_code == 404


def test_exposure_returns_unavailable_when_no_matching_generation():
    """?곹뭹? ?덈뒗???대떦 ?쒓컙?濡??앹꽦??寃??놁쑝硫?available=False."""
    pid = _upload_product()
    resp = client.get(f"/api/v1/exposure/{pid}", params={"at": "2026-08-05T07:00:00+09:00"})
    assert resp.status_code == 200
    assert resp.json()["available"] is False
    assert resp.json()["time_slot"] == "morning"


def test_exposure_accepts_at_query_param_for_demo():
    """?at= ?뚮씪誘명꽣濡??꾩쓽 ?쒓컖 湲곗? 議고쉶 媛??(諛쒗몴 ?곕え??."""
    pid = _upload_product()
    client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["evening"]})
    time.sleep(0.5)

    resp = client.get(f"/api/v1/exposure/{pid}", params={"at": "2026-08-05T20:30:00+09:00"})
    assert resp.status_code == 200
    assert resp.json()["time_slot"] == "evening"
    assert resp.json()["available"] is True


def test_download_all_returns_404_when_no_files_exist_on_disk():
    """?붿뒪?ъ뿉???뚯씪???щ씪吏?寃쎌슦 鍮?ZIP??200?쇰줈 議곗슜??二쇰㈃ ???섍퀬 404?ъ빞 ?쒕떎."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    # 寃곌낵??completed?몃뜲, ?붿뒪???뚯씪??媛뺤젣濡?吏?뚯꽌 "?뚯씪 ?놁쓬" ?곹솴???ы쁽
    result = client.get(f"/api/v1/generations/{job_id}").json()
    for tone_result in result["results"]:
        for url in tone_result["images"].values():
            from app.backend.api.download import _url_to_path
            path = _url_to_path(url)
            if path.exists():
                path.unlink()

    resp = client.get(f"/api/v1/download/{job_id}/all")
    assert resp.status_code == 404


def test_download_all_zip_does_not_collide_across_multiple_time_slots():
    """?쒓컙? 2媛??댁긽??job?먯꽌 ZIP arcname??tone_format留??곕㈃ ?쒕줈 ?ㅻⅨ ?쒓컙?
    ?뚯씪??媛숈? ?대쫫?쇰줈 寃뱀퀜?⑥졇???덈컲???좎떎?쒕떎 - time_slot??arcname???ы븿?댁빞 ?쒕떎."""
    pid = _upload_product()
    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["morning", "evening"],
            "output_formats": ["thumbnail", "sns_card"],
        },
    )
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    resp = client.get(f"/api/v1/download/{job_id}/all")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    # ?쒓컙? 2 x ??4 x ?좏깮 鍮꾩쑉 2 = 16媛??뚯씪???꾨? ?좊땲?ы빐????    assert len(names) == 16
    assert len(set(names)) == 16  # 以묐났 ?놁쓬


def test_download_one_with_time_slot_returns_correct_slot():
    """time_slot??吏?뺥븯硫?洹??쒓컙????대?吏瑜??뺥솗??諛쏆븘???쒕떎 (?щ윭 ?쒓컙?媛 ?욎씤 job)."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning", "evening"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    tone = result["results"][0]["tone"]

    resp = client.get(f"/api/v1/download/{job_id}", params={
        "tone": tone, "output_format": "thumbnail", "time_slot": "evening",
    })
    assert resp.status_code == 200
    assert "evening" in resp.headers["content-disposition"]


def test_video_creation_flow_for_rush_hour_slot():
    pid = _upload_product()
    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["commute_am"],
            "output_formats": ["story_vertical"],
        },
    )
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    result_id = result["results"][0]["result_id"]
    assert result_id.startswith("res_")

    video_resp = client.post("/api/v1/videos", json={"result_id": result_id})
    assert video_resp.status_code == 202
    video_job_id = video_resp.json()["video_job_id"]
    assert video_resp.json()["render_status"] == "queued"

    status_resp = client.get(f"/api/v1/videos/{video_job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["render_status"] == "completed"
    assert status_resp.json()["video_url"] == f"/files/videos/{video_job_id}.mp4"

    # History??寃곌낵?먮룄 video_url??諛섏쁺?쇱빞 ??(?덈줈怨좎묠?대룄 ?ㅼ떆 蹂댁씠?꾨줉)
    updated_history = client.get("/api/v1/history").json()
    updated_result = updated_history[0]["results"][0]
    assert updated_result["video_url"] == f"/files/videos/{video_job_id}.mp4"


def test_video_creation_rejects_non_rush_hour_slot():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["afternoon"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    result_id = result["results"][0]["result_id"]

    video_resp = client.post("/api/v1/videos", json={"result_id": result_id})
    assert video_resp.status_code == 400


def test_video_creation_404_for_unknown_result_id():
    video_resp = client.post("/api/v1/videos", json={"result_id": "res_doesnotexist"})
    assert video_resp.status_code == 404


def test_video_status_404_for_unknown_job():
    resp = client.get("/api/v1/videos/video_doesnotexist")
    assert resp.status_code == 404


def test_video_completion_persists_video_url_across_restart():
    """?쇱툩 ?꾨즺 ??store.save()媛 ?몄텧?쇱꽌, ?ъ떆??load) ?꾩뿉??video_url???⑥븘?덉뼱???쒕떎."""
    pid = _upload_product()
    r = client.post(
        "/api/v1/generations",
        json={
            "product_id": pid,
            "time_slots": ["commute_am"],
            "output_formats": ["story_vertical"],
        },
    )
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    result_id = result["results"][0]["result_id"]

    video_resp = client.post("/api/v1/videos", json={"result_id": result_id})
    video_job_id = video_resp.json()["video_job_id"]
    client.get(f"/api/v1/videos/{video_job_id}")  # completed濡?留뚮뱾怨?video_url 諛섏쁺

    # ?ъ떆?묒쓣 ?됰궡: 硫붾え由?鍮꾩슦怨?store.load()濡?蹂듦뎄
    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    store.VIDEO_JOBS.clear()
    store.load()

    restored = VideoJob.model_validate(store.VIDEO_JOBS[video_job_id])
    assert restored.video_url == f"/files/videos/{video_job_id}.mp4"
    assert restored.render_status == "completed"
