from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def collect_telegram_news(market: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not bool(config.get("telegram_enabled", False)):
        return []

    channels = load_channel_config(Path(str(config.get("telegram_channels_path", "sources/telegram_channels.json"))))
    channels = [item for item in channels if item.get("market") == market]
    if not channels:
        return [setup_news_item(market, "텔레그램 채널 목록이 없습니다.", "sources/telegram_channels.json을 채워주세요.")]

    api_id = os.environ.get(str(config.get("telegram_api_id_env", "TELEGRAM_API_ID")))
    api_hash = os.environ.get(str(config.get("telegram_api_hash_env", "TELEGRAM_API_HASH")))
    if api_id and api_hash:
        try:
            return asyncio.run(fetch_with_telethon(market, channels, int(api_id), api_hash, config))
        except Exception as exc:
            return [setup_news_item(market, "텔레그램 API 수집 실패", str(exc)[:180])]

    manual_items = manual_channel_items(market, channels, int(config.get("telegram_limit", 30)))
    if manual_items:
        return manual_items
    return [
        setup_news_item(
            market,
            "텔레그램 API 설정 필요",
            "TELEGRAM_API_ID, TELEGRAM_API_HASH 환경변수를 설정하거나 channels 파일에 latest_text를 넣어주세요.",
        )
    ]


def load_channel_config(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("channels", [])
    if not isinstance(raw, list):
        raise ValueError("텔레그램 채널 설정은 list 또는 {'channels': [...]} 형식이어야 합니다.")
    return [dict(item) for item in raw]


async def fetch_with_telethon(
    market: str,
    channels: list[dict[str, Any]],
    api_id: int,
    api_hash: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    from telethon import TelegramClient  # type: ignore
    from telethon.tl.functions.channels import GetFullChannelRequest  # type: ignore

    session_path = str(config.get("telegram_session_path", "data/telegram_dashboard.session"))
    limit = int(config.get("telegram_limit", 30))
    messages_per_channel = int(config.get("telegram_messages_per_channel", 3))
    results: list[dict[str, Any]] = []

    async with TelegramClient(session_path, api_id, api_hash) as client:
        for channel in channels:
            username = str(channel.get("username", "")).lstrip("@")
            if not username:
                continue
            try:
                entity = await client.get_entity(username)
                full = await client(GetFullChannelRequest(entity))
                subscribers = int(getattr(full.full_chat, "participants_count", 0) or channel.get("subscribers", 0) or 0)
                messages = await client.get_messages(entity, limit=messages_per_channel)
                message = next((item for item in messages if getattr(item, "message", None)), None)
                if not message:
                    continue
                text = str(message.message)
                results.append(
                    {
                        "market": market,
                        "source": channel.get("title") or getattr(entity, "title", username),
                        "title": first_line(text) or str(channel.get("title") or username),
                        "summary": summarize_text(text),
                        "url": f"https://t.me/{username}/{message.id}",
                        "published_at": message.date.isoformat() if getattr(message, "date", None) else "",
                        "subscribers": subscribers,
                        "region": channel.get("region", ""),
                    }
                )
            except Exception as exc:
                results.append(setup_news_item(market, channel.get("title", username), f"수집 실패: {exc}"))

    results.sort(key=lambda item: int(item.get("subscribers") or 0), reverse=True)
    return results[:limit]


def manual_channel_items(market: str, channels: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    results = []
    for channel in channels:
        text = str(channel.get("latest_text", "")).strip()
        if not text:
            continue
        username = str(channel.get("username", "")).lstrip("@")
        message_id = channel.get("message_id", "")
        url = str(channel.get("url") or (f"https://t.me/{username}/{message_id}" if username and message_id else f"https://t.me/{username}"))
        results.append(
            {
                "market": market,
                "source": channel.get("title") or username,
                "title": channel.get("headline") or first_line(text) or channel.get("title") or username,
                "summary": summarize_text(text),
                "url": url,
                "published_at": channel.get("published_at", ""),
                "subscribers": int(channel.get("subscribers", 0) or 0),
                "region": channel.get("region", ""),
            }
        )
    results.sort(key=lambda item: int(item.get("subscribers") or 0), reverse=True)
    return results[:limit]


def setup_news_item(market: str, title: str, summary: str) -> dict[str, Any]:
    return {
        "market": market,
        "source": "Telegram",
        "title": title,
        "summary": summary,
        "url": "",
        "published_at": datetime.now().isoformat(timespec="seconds"),
        "subscribers": 0,
        "region": "domestic" if market == "domestic" else "overseas",
    }


def first_line(text: str) -> str:
    for line in text.splitlines():
        line = clean_text(line)
        if line:
            return line[:90]
    return ""


def summarize_text(text: str, limit: int = 220) -> str:
    text = clean_text(re.sub(r"https?://\S+", "", text))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
