from __future__ import annotations

import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


os.environ.setdefault("MPLCONFIGDIR", str(Path("data/.matplotlib-cache").resolve()))


def collect_market_metrics(market: str, now: datetime, config: dict[str, Any]) -> list[dict[str, str]]:
    if market == "domestic":
        return collect_domestic_metrics(now, config)
    if market == "overseas":
        return collect_overseas_metrics(config)
    raise ValueError(f"지원하지 않는 market입니다: {market}")


def collect_domestic_metrics(now: datetime, config: dict[str, Any]) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    errors: list[str] = []

    for label, pykrx_code, naver_code in [
        ("KOSPI", "1001", "KOSPI"),
        ("KOSDAQ", "2001", "KOSDAQ"),
    ]:
        index_metric = None
        try:
            index_metric = fetch_naver_index(label, naver_code)
        except Exception as exc:
            errors.append(f"{label} 네이버 실패: {exc}")
        if index_metric is None:
            try:
                index_metric = fetch_pykrx_index(label, pykrx_code, now)
            except Exception as exc:
                errors.append(f"{label} KRX 실패: {exc}")
        if index_metric is not None:
            metrics.append(index_metric)

    watchlist = config.get("domestic_watchlist", [])
    for item in watchlist:
        code = str(item.get("code", "")).zfill(6)
        name = str(item.get("name", code))
        if not code:
            continue
        try:
            metrics.append(fetch_naver_stock(name, code))
        except Exception as exc:
            errors.append(f"{name} 네이버 실패: {exc}")

    if not metrics:
        metrics.append(
            metric(
                "데이터 소스",
                "KRX/네이버금융",
                "연결 실패",
                "확인 필요",
                "warn",
                "pykrx 설치, 네트워크, 네이버 페이지 구조를 확인하세요.",
            )
        )
    if errors:
        metrics.append(
            metric(
                "데이터 소스",
                "수집 로그",
                f"{len(errors)}건",
                "일부 실패",
                "warn",
                " / ".join(errors[:2]),
            )
        )
    return metrics


def fetch_pykrx_index(label: str, index_code: str, now: datetime) -> dict[str, str] | None:
    from pykrx import stock  # type: ignore

    end = now.strftime("%Y%m%d")
    start = (now - timedelta(days=14)).strftime("%Y%m%d")
    frame = stock.get_index_ohlcv_by_date(start, end, index_code)
    if frame.empty or "종가" not in frame:
        return None
    closes = frame["종가"].dropna()
    if len(closes) < 2:
        return None
    current = float(closes.iloc[-1])
    previous = float(closes.iloc[-2])
    pct = ((current / previous) - 1.0) * 100.0 if previous else 0.0
    return metric("시장", label, format_number(current), format_percent(pct), tone_from_value(pct), "KRX pykrx")


def fetch_naver_index(label: str, code: str) -> dict[str, str]:
    url = f"https://finance.naver.com/sise/sise_index.naver?code={code}"
    html = fetch_text(url, encoding="euc-kr")
    value = extract_first(html, r'id="now_value">([^<]+)<')
    change_block = extract_first(html, r'id="change_value_and_rate">(.*?)</span>\s*</span>')
    change_values = re.findall(r"<span>([^<]+)</span>|([+-]?\d+(?:\.\d+)?%)", change_block)
    change_parts = [left or right for left, right in change_values if left or right]
    change = " ".join(change_parts) if change_parts else clean(re.sub(r"<.*?>", " ", change_block))
    change = re.sub(r"\s+", " ", change).strip()
    quotient = extract_first(html, r'<div class="quotient\s*([^"]*)"')
    tone = "down" if "dn" in quotient or "-" in change or "하락" in change else "up" if "up" in quotient or "+" in change or "상승" in change else "neutral"
    return metric("시장", label, value, change, tone, "네이버금융")


def fetch_naver_stock(label: str, code: str) -> dict[str, str]:
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    html = fetch_text(url, encoding="euc-kr")
    value = extract_first(html, r'<p class="no_today">.*?<span class="blind">([^<]+)</span>')
    change = extract_first(html, r'<p class="no_exday">.*?<span class="blind">([^<]+)</span>.*?<span class="blind">([^<]+)</span>')
    block_start = html.find("no_exday")
    block = html[block_start : block_start + 1200] if block_start >= 0 else html
    tone = "down" if "no_down" in block or "ico down" in block else "up" if "no_up" in block or "ico up" in block else "neutral"
    if change and "%" not in change:
        parts = change.split()
        if len(parts) >= 2:
            sign = "-" if tone == "down" else "+" if tone == "up" else ""
            change = f"{sign}{parts[0]} {sign}{parts[1]}%"
    return metric("관심종목", label, value, change, tone, f"네이버금융 {code}")


def collect_overseas_metrics(config: dict[str, Any]) -> list[dict[str, str]]:
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return [
            metric(
                "데이터 소스",
                "yfinance",
                "미설치",
                "pip 필요",
                "warn",
                "pip install -r requirements.txt 실행 후 다시 시도하세요.",
            )
        ]

    cache_dir = Path("data/.yfinance-cache").resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    if hasattr(yf, "set_tz_cache_location"):
        yf.set_tz_cache_location(str(cache_dir))

    ticker_map = config.get(
        "overseas_tickers",
        {
            "^GSPC": "S&P 500",
            "^IXIC": "NASDAQ",
            "^DJI": "Dow Jones",
            "CL=F": "WTI 원유",
            "GC=F": "금",
            "BTC-USD": "Bitcoin",
            "ETH-USD": "Ethereum",
            "KRW=X": "달러/원",
        },
    )
    metrics: list[dict[str, str]] = []
    for ticker, label in ticker_map.items():
        try:
            history = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            closes = history["Close"].dropna()
            if len(closes) < 2:
                raise RuntimeError("종가 데이터 부족")
            current = float(closes.iloc[-1])
            previous = float(closes.iloc[-2])
            pct = ((current / previous) - 1.0) * 100.0 if previous else 0.0
            group = overseas_group_for_ticker(ticker)
            metrics.append(
                metric(group, str(label), format_price(current, ticker), format_percent(pct), tone_from_value(pct), f"yfinance {ticker}")
            )
        except Exception as exc:
            metrics.append(metric("데이터 소스", str(label), "수집 실패", str(ticker), "warn", str(exc)[:120]))
    return metrics


def overseas_group_for_ticker(ticker: str) -> str:
    if ticker in {"^GSPC", "^IXIC", "^DJI"}:
        return "미국 증시"
    if ticker in {"CL=F", "GC=F"}:
        return "원자재"
    if ticker.endswith("-USD"):
        return "가상자산"
    return "환율"


def fetch_text(url: str, encoding: str = "utf-8") -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode(encoding, errors="ignore")


def extract_first(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise RuntimeError(f"패턴을 찾지 못했습니다: {pattern}")
    if len(match.groups()) == 1:
        return clean(match.group(1))
    return clean(" ".join(match.groups()))


def metric(group_name: str, label: str, value: str, delta: str, tone: str, note: str) -> dict[str, str]:
    return {
        "group_name": group_name,
        "label": label,
        "value": value,
        "delta": delta,
        "tone": tone,
        "note": note,
    }


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace(",", ",")).strip()


def format_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def format_price(value: float, ticker: str) -> str:
    if ticker in {"CL=F", "GC=F", "BTC-USD", "ETH-USD"}:
        return f"${value:,.2f}"
    if ticker == "KRW=X":
        return f"{value:,.2f}원"
    return format_number(value)


def format_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def tone_from_value(value: float) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "neutral"
