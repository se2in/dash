from __future__ import annotations

from typing import Any

from market_collectors import fetch_naver_stock
from naver_issues import NewsArticle, related_articles, score_themes


DEFAULT_SECTOR_STOCKS: dict[str, list[dict[str, str]]] = {
    "반도체/HBM": [
        {"code": "005930", "name": "삼성전자"},
        {"code": "000660", "name": "SK하이닉스"},
        {"code": "042700", "name": "한미반도체"},
        {"code": "240810", "name": "원익IPS"},
        {"code": "036930", "name": "주성엔지니어링"},
        {"code": "039030", "name": "이오테크닉스"},
    ],
    "금융/증권": [
        {"code": "105560", "name": "KB금융"},
        {"code": "055550", "name": "신한지주"},
        {"code": "086790", "name": "하나금융지주"},
        {"code": "005940", "name": "NH투자증권"},
        {"code": "006800", "name": "미래에셋증권"},
        {"code": "138040", "name": "메리츠금융지주"},
    ],
    "금리/환율": [
        {"code": "001450", "name": "현대해상"},
        {"code": "032830", "name": "삼성생명"},
        {"code": "000810", "name": "삼성화재"},
        {"code": "005830", "name": "DB손해보험"},
        {"code": "003410", "name": "쌍용C&E"},
    ],
    "에너지/유가": [
        {"code": "096770", "name": "SK이노베이션"},
        {"code": "010950", "name": "S-Oil"},
        {"code": "267250", "name": "HD현대"},
        {"code": "034020", "name": "두산에너빌리티"},
        {"code": "010120", "name": "LS ELECTRIC"},
    ],
    "2차전지": [
        {"code": "373220", "name": "LG에너지솔루션"},
        {"code": "006400", "name": "삼성SDI"},
        {"code": "003670", "name": "포스코퓨처엠"},
        {"code": "086520", "name": "에코프로"},
        {"code": "247540", "name": "에코프로비엠"},
    ],
    "바이오/헬스케어": [
        {"code": "068270", "name": "셀트리온"},
        {"code": "207940", "name": "삼성바이오로직스"},
        {"code": "128940", "name": "한미약품"},
        {"code": "302440", "name": "SK바이오사이언스"},
        {"code": "196170", "name": "알테오젠"},
    ],
    "조선/방산": [
        {"code": "012450", "name": "한화에어로스페이스"},
        {"code": "064350", "name": "현대로템"},
        {"code": "329180", "name": "HD현대중공업"},
        {"code": "010140", "name": "삼성중공업"},
        {"code": "042660", "name": "한화오션"},
    ],
    "자동차": [
        {"code": "005380", "name": "현대차"},
        {"code": "000270", "name": "기아"},
        {"code": "012330", "name": "현대모비스"},
        {"code": "011210", "name": "현대위아"},
        {"code": "204320", "name": "HL만도"},
    ],
}


def build_sector_temperature(
    metrics: list[dict[str, Any]],
    config: dict[str, Any],
    articles: list[NewsArticle],
    limit: int = 4,
) -> list[dict[str, Any]]:
    universe = config.get("sector_stock_universe", DEFAULT_SECTOR_STOCKS)
    theme_scores = score_themes(articles, metrics)
    cards: list[dict[str, Any]] = []

    for theme, score in theme_scores:
        stocks = top_rising_stocks_for_sector(universe.get(theme, []))
        related = related_articles(theme, articles)
        article = related[0] if related else None
        if not stocks and not article:
            continue
        cards.append(
            {
                "title": theme,
                "body": sector_body(score, stocks, article),
                "tone": tone_for_sector(score, stocks),
                "url": article.url if article else "",
                "top_stocks": stocks[:3],
            }
        )
        if len(cards) >= limit:
            return cards

    for theme, stocks_def in universe.items():
        if any(card["title"] == theme for card in cards):
            continue
        stocks = top_rising_stocks_for_sector(stocks_def)
        if not stocks:
            continue
        cards.append(
            {
                "title": theme,
                "body": sector_body(0, stocks, None),
                "tone": tone_for_sector(0, stocks),
                "url": "",
                "top_stocks": stocks[:3],
            }
        )
        if len(cards) >= limit:
            break
    return cards


def top_rising_stocks_for_sector(stocks: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stock in stocks:
        code = str(stock.get("code", "")).zfill(6)
        name = str(stock.get("name", code))
        if not code:
            continue
        try:
            metric = fetch_naver_stock(name, code)
            pct = parse_percent(metric.get("delta", ""))
            rows.append(
                {
                    "name": name,
                    "code": code,
                    "value": metric.get("value", ""),
                    "delta": metric.get("delta", ""),
                    "pct": pct,
                    "url": f"https://finance.naver.com/item/main.naver?code={code}",
                }
            )
        except Exception:
            continue
    rows.sort(key=lambda item: item.get("pct", 0.0), reverse=True)
    return rows[:3]


def sector_body(score: int, stocks: list[dict[str, Any]], article: NewsArticle | None) -> str:
    stock_text = ", ".join(f"{item['name']} {item['delta']}" for item in stocks[:3]) or "상승 종목 확인 필요"
    if article:
        return f"뉴스 점수 {score}. 상승 상위: {stock_text}. 대표 뉴스: {article.title}"
    return f"상승 상위: {stock_text}. 관련 뉴스 링크는 추가 수집 후 연결됩니다."


def tone_for_sector(score: int, stocks: list[dict[str, Any]]) -> str:
    best = stocks[0].get("pct", 0.0) if stocks else 0.0
    if best >= 3.0 or score >= 20:
        return "hot"
    if best >= 1.0 or score >= 10:
        return "warm"
    if best <= -1.0:
        return "cool"
    return "green"


def parse_percent(value: Any) -> float:
    import re

    matches = re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%", str(value or ""))
    if not matches:
        return 0.0
    try:
        return float(matches[-1])
    except ValueError:
        return 0.0
