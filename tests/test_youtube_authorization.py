import pytest

from scripts.authorize_youtube import (
    ensure_external_token_path,
    write_credentials_atomically,
)


def test_token_path_must_be_outside_repository(tmp_path):
    repo_root = tmp_path / "repo"
    token_path = repo_root / "secrets" / "youtube_token.json"

    with pytest.raises(ValueError, match="저장소 밖"):
        ensure_external_token_path(token_path, repo_root)


def test_external_token_path_is_accepted(tmp_path):
    repo_root = tmp_path / "repo"
    token_path = tmp_path / "operator-secrets" / "youtube_token.json"

    resolved = ensure_external_token_path(token_path, repo_root)

    assert resolved == token_path.resolve()


def test_credentials_are_written_atomically_without_temp_residue(tmp_path):
    token_path = tmp_path / "operator-secrets" / "youtube_token.json"

    write_credentials_atomically(token_path, '{"token": "secret"}')

    assert token_path.read_text(encoding="utf-8") == '{"token": "secret"}'
    assert list(token_path.parent.glob(f".{token_path.name}.*.tmp")) == []
