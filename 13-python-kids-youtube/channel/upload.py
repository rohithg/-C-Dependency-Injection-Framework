"""Upload a finished episode to the operator's own YouTube channel."""

from __future__ import annotations

from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube"]


class CredentialsError(RuntimeError):
    pass


def secrets_path(config: dict, root: Path) -> Path:
    return root / config["client_secrets"]


def token_path(config: dict, root: Path) -> Path:
    return root / config["token_path"]


def require_ready(config: dict, root: Path) -> tuple[Path, Path]:
    if not config.get("upload_enabled"):
        raise CredentialsError("Upload is turned off in config.json.")
    secrets = secrets_path(config, root)
    token = token_path(config, root)
    if not secrets.exists():
        raise CredentialsError(
            "Missing Google client secret at "
            f"{secrets}. Add it, then run: python studio.py auth"
        )
    if not token.exists():
        raise CredentialsError("Missing YouTube token. Run: python studio.py auth")
    return secrets, token


def authenticate(config: dict, root: Path) -> Path:
    secrets = secrets_path(config, root)
    token = token_path(config, root)
    if not secrets.exists():
        raise CredentialsError(
            f"Put the Google desktop client file at {secrets} first."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    creds = flow.run_local_server(port=0)
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json())
    return token


def upload_files(video: Path, thumbnail: Path, body: dict, config: dict, root: Path) -> str:
    secrets, token = require_ready(config, root)
    if body.get("status", {}).get("selfDeclaredMadeForKids") is not True:
        raise CredentialsError("Refusing to upload a video that is not made for kids.")
    creds = _credentials(secrets, token)
    youtube = _service(creds)
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg"),
    ).execute()
    _add_to_playlist(youtube, video_id, config)
    return video_id


def _credentials(secrets: Path, token: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json())
    if not creds or not creds.valid:
        raise CredentialsError("YouTube token is not valid. Run: python studio.py auth")
    return creds


def _service(creds):
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=creds)


def _add_to_playlist(youtube, video_id: str, config: dict) -> None:
    title = config.get("playlist") or "Little Lantern"
    try:
        found = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        playlist_id = None
        for item in found.get("items", []):
            if item["snippet"]["title"] == title:
                playlist_id = item["id"]
                break
        if playlist_id is None:
            created = youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": "Short, calm learning stories for young children.",
                    },
                    "status": {"privacyStatus": "public"},
                },
            ).execute()
            playlist_id = created["id"]
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
    except Exception as exc:
        print(f"Video {video_id} is uploaded. Playlist step skipped: {exc}")
