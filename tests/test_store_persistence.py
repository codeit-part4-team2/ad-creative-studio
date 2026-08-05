from app.backend.services import store


def test_save_then_load_restores_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.PRODUCTS.clear()
    store.JOBS.clear()
    store.HISTORY.clear()

    store.PRODUCTS["prd_1"] = {"product_name": "선풍기"}
    store.JOBS["job_1"] = {"status": "completed", "product_id": "prd_1"}
    store.HISTORY.append({"job_id": "job_1", "product_id": "prd_1", "favorite": True})
    store.save()

    # 서버 재시작을 흉내: 메모리 비우고 load()로 복구
    store.PRODUCTS.clear()
    store.JOBS.clear()
    store.HISTORY.clear()
    store.load()

    assert store.PRODUCTS["prd_1"]["product_name"] == "선풍기"
    assert store.JOBS["job_1"]["status"] == "completed"
    assert store.HISTORY[0]["favorite"] is True


def test_load_is_noop_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "does_not_exist.json")
    store.PRODUCTS.clear()
    store.load()
    assert store.PRODUCTS == {}


def test_load_handles_corrupted_file_gracefully(tmp_path, monkeypatch):
    bad_file = tmp_path / "store.json"
    bad_file.write_text("이건 JSON이 아님{{{", encoding="utf-8")
    monkeypatch.setattr(store, "STORE_PATH", bad_file)

    store.PRODUCTS.clear()
    store.load()  # 예외 없이 조용히 무시되어야 함
    assert store.PRODUCTS == {}


def test_load_handles_wrong_encoding_gracefully(tmp_path, monkeypatch):
    """UTF-8이 아닌 다른 인코딩으로 저장된(깨진) 파일이어도 죽지 않아야 한다."""
    bad_file = tmp_path / "store.json"
    bad_file.write_bytes("이건 인코딩이 다름".encode("cp949"))
    monkeypatch.setattr(store, "STORE_PATH", bad_file)

    store.PRODUCTS.clear()
    store.load()  # 예외 없이 조용히 무시되어야 함
    assert store.PRODUCTS == {}


def test_reset_for_tests_clears_memory_and_file(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.PRODUCTS["x"] = {}
    store.save()
    assert store.STORE_PATH.exists()

    store.reset_for_tests()
    assert store.PRODUCTS == {}
    assert not store.STORE_PATH.exists()
