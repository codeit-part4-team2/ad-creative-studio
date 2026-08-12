from __future__ import annotations

import os
import tempfile
from pathlib import Path


YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def ensure_external_token_path(token_path: Path, repo_root: Path) -> Path:
    """Return an absolute token path only when it is outside the repository."""
    resolved_token = token_path.expanduser().resolve()
    resolved_repo = repo_root.resolve()
    if resolved_token.is_relative_to(resolved_repo):
        raise ValueError("YouTube 토큰은 저장소 밖에 보관해야 합니다")
    return resolved_token


def write_credentials_atomically(token_path: Path, credentials_json: str) -> None:
    """Write credentials through a temporary sibling and atomically replace."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=token_path.parent,
            prefix=f".{token_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(credentials_json)
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(token_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    from google_auth_oauthlib.flow import InstalledAppFlow

    repo_root = Path(__file__).resolve().parents[1]
    client_secrets_value = os.environ.get("YOUTUBE_CLIENT_SECRETS_FILE", "")
    token_value = os.environ.get("YOUTUBE_TOKEN_FILE", "")
    if not client_secrets_value or not token_value:
        raise RuntimeError(
            "YOUTUBE_CLIENT_SECRETS_FILE과 YOUTUBE_TOKEN_FILE을 설정하세요"
        )

    client_secrets_path = Path(client_secrets_value).expanduser().resolve()
    if not client_secrets_path.is_file():
        raise FileNotFoundError(f"OAuth 클라이언트 파일이 없습니다: {client_secrets_path}")
    token_path = ensure_external_token_path(Path(token_value), repo_root)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_path),
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )
    credentials = flow.run_local_server(host="localhost", port=0)
    write_credentials_atomically(token_path, credentials.to_json())
    print(f"token: {token_path}")
    print(f"scope: {YOUTUBE_UPLOAD_SCOPE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
