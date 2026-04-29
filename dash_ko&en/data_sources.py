from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_external_payload(
    market: str,
    now: datetime,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    source = str(config.get("data_source", "sample")).lower()
    if source == "sample":
        return None
    if source == "json":
        return load_json_payload(market, now, config)
    if source == "api":
        return load_api_payload(market, now, config)
    if source == "auto":
        json_path = Path(str(config.get("data_json_path", "")))
        if json_path.exists():
            return load_json_payload(market, now, config)
        api_url = config.get(f"{market}_api_url")
        if api_url:
            return load_api_payload(market, now, config)
        return None
    raise ValueError(f"지원하지 않는 data_source입니다: {source}")


def load_json_payload(
    market: str,
    now: datetime,
    config: dict[str, Any],
) -> dict[str, Any]:
    path = Path(str(config.get("data_json_path", "sources/dashboard_payload.json")))
    if not path.exists():
        raise FileNotFoundError(f"JSON 데이터 파일을 찾지 못했습니다: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = select_market_payload(raw, market)
    return normalize_payload(payload, market, now)


def load_api_payload(
    market: str,
    now: datetime,
    config: dict[str, Any],
) -> dict[str, Any]:
    url = config.get(f"{market}_api_url")
    if not url:
        raise ValueError(f"{market}_api_url 설정이 없습니다.")

    timeout = int(config.get("api_timeout_seconds", 20))
    headers = {"Accept": "application/json"}
    auth_env = config.get("api_auth_env")
    if auth_env and os.environ.get(str(auth_env)):
        header_name = str(config.get("api_auth_header", "Authorization"))
        scheme = str(config.get("api_auth_scheme", "Bearer")).strip()
        token = os.environ[str(auth_env)]
        headers[header_name] = f"{scheme} {token}".strip()

    request = Request(str(url), headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"API 요청 실패: HTTP {exc.code} {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"API 연결 실패: {url} ({exc.reason})") from exc

    payload = select_market_payload(raw, market)
    return normalize_payload(payload, market, now)


def select_market_payload(raw: dict[str, Any], market: str) -> dict[str, Any]:
    if market in raw and isinstance(raw[market], dict):
        return raw[market]
    if "payload" in raw and isinstance(raw["payload"], dict):
        return raw["payload"]
    return raw


def normalize_payload(payload: dict[str, Any], market: str, now: datetime) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("market", market)
    normalized.setdefault("as_of_date", now.strftime("%Y-%m-%d"))
    normalized.setdefault("updated_at", now.isoformat(timespec="seconds"))
    normalized.setdefault("headline", "")

    for key in ("metrics", "sector_cards", "alerts", "ideas", "events", "news"):
        value = normalized.get(key)
        if value is None:
            normalized[key] = []
        elif not isinstance(value, list):
            raise ValueError(f"{key} 값은 list여야 합니다.")

    return normalized
