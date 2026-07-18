import requests

from src.config import TFL_APP_KEY, TFL_BASE_URL

def _get(path: str, params: dict | None = None) -> list | dict:
    params = dict(params or {})
    if TFL_APP_KEY:
        params["app_key"] = TFL_APP_KEY

    resp = requests.get(f"{TFL_BASE_URL}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()

def get_line_status(mode: str = "tube") -> list[dict]:
    return _get(f"/Line/Mode/{mode}/Status")

def get_lines(mode: str = "tube") -> list[dict]:
    return _get(f"/Line/Mode/{mode}")

def get_route_sequence(line_id: str, direction: str = "outbound") -> dict:
    return _get(f"/Line/{line_id}/Route/Sequence/{direction}")
