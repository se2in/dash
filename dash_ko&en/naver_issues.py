from __future__ import annotations

import html
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


STOPWORDS = {
    "기자",
    "뉴스",
    "증시",
    "시장",
    "국내",
    "한국",
    "관련",
    "오늘",
    "오전",
    "오후",
    "올해",
    "이번",
    "지난",
    "가운데",
    "가능성",
    "전망",
    "투자",
    "상승",
    "하락",
    "강세",
    "약세",
    "거래",
    "기준",
}

THEME_KEYWORDS = {
    "반도체/HBM": {"반도체", "HBM", "삼성전자", "SK하이닉스", "하이닉스", "장비", "메모리", "AI"},
    "금리/환율": {"금리", "환율", "달러", "원화", "채권", "국고채", "연준", "FOMC"},
    "2차전지": {"2차전지", "배터리", "전기차", "양극재", "리튬", "에코프로", "LG에너지솔루션"},
    "금융/증권": {"금융", "은행", "증권", "보험", "지주", "KB금융", "신한지주", "메리츠"},
    "바이오/헬스케어": {"바이오", "제약", "헬스케어", "임상", "셀트리온", "삼성바이오"},
    "조선/방산": {"조선", "방산", "수주", "LNG", "한화에어로스페이스", "현대로템"},
    "에너지/유가": {"유가", "원유", "WTI", "정유", "에너지", "태양광", "전력"},
    "자동차": {"자동차", "현대차", "기아", "부품", "전장", "자율주행"},
}


@dataclass
class NewsArticle:
    title: str
    summary: str
    url: str
    source: str
    published_at: str = ""


def build_domestic_core_issues(
    metrics: list[dict[str, Any]],
    config: dict[str, Any],
    now: datetime,
    articles: list[NewsArticle] | None = None,
) -> list[dict[str, str]]:
    if not bool(config.get("naver_issue_enabled", True)):
        return []

    articles = articles if articles is not None else collect_naver_finance_news(config)
    if not articles:
        return fallback_issues(metrics)

    market_notes = summarize_market_moves(metrics)
    theme_scores = score_themes(articles, metrics)
    keyword_counts = count_keywords(articles)
    issues = []

    for rank, (theme, score) in enumerate(theme_scores[:4], start=1):
        related = related_articles(theme, articles)
        top_article = related[0] if related else articles[0]
        keywords = keywords_for_theme(theme, keyword_counts, top_article)
        severity = "core" if rank <= 2 else "risk"
        title = f"{theme} 이슈"
        body = compose_issue_body(theme, keywords, top_article, market_notes)
        issues.append({"severity": severity, "title": title, "body": body})

    while len(issues) < 4:
        article = articles[len(issues) % len(articles)]
        issues.append(
            {
                "severity": "normal",
                "title": "뉴스 모멘텀",
                "body": f"{article.title} - {article.summary[:95]}",
            }
        )
    return issues[:4]


def collect_naver_finance_news(config: dict[str, Any]) -> list[NewsArticle]:
    if os.environ.get(str(config.get("naver_client_id_env", "NAVER_CLIENT_ID"))) and os.environ.get(
        str(config.get("naver_client_secret_env", "NAVER_CLIENT_SECRET"))
    ):
        try:
            return collect_with_naver_openapi(config)
        except Exception:
            pass

    queries = config.get(
        "domestic_naver_news_queries",
        ["금융 증시", "코스피 코스닥", "반도체 삼성전자 SK하이닉스", "환율 금리 유가"],
    )
    limit = int(config.get("naver_news_limit", 32))
    articles: list[NewsArticle] = []
    seen: set[str] = set()
    for query in queries:
        for article in parse_naver_search_page(query):
            key = article.url or article.title
            if key in seen:
                continue
            seen.add(key)
            articles.append(article)
            if len(articles) >= limit:
                return articles
    return articles


def collect_with_naver_openapi(config: dict[str, Any]) -> list[NewsArticle]:
    client_id = os.environ[str(config.get("naver_client_id_env", "NAVER_CLIENT_ID"))]
    client_secret = os.environ[str(config.get("naver_client_secret_env", "NAVER_CLIENT_SECRET"))]
    query = quote(str(config.get("naver_openapi_query", "금융 증시 반도체 환율")))
    display = int(config.get("naver_news_limit", 32))
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display={display}&sort=date"
    request = Request(
        url,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urlopen(request, timeout=20) as response:
        data = response.read().decode("utf-8", errors="ignore")
    import json

    payload = json.loads(data)
    articles = []
    for item in payload.get("items", []):
        title = clean_text(strip_tags(item.get("title", "")))
        summary = clean_text(strip_tags(item.get("description", "")))
        url = item.get("originallink") or item.get("link") or ""
        articles.append(NewsArticle(title=title, summary=summary, url=url, source="Naver OpenAPI", published_at=item.get("pubDate", "")))
    return articles


def parse_naver_search_page(query: str) -> list[NewsArticle]:
    url = f"https://search.naver.com/search.naver?where=news&sm=tab_jum&sort=1&query={quote(query)}"
    html_text = fetch_text(url)
    soup = BeautifulSoup(html_text, "html.parser")
    articles = []
    for title_link in soup.select('a[data-heatmap-target=".tit"]'):
        title = clean_text(title_link.get_text(" ", strip=True))
        if not title:
            continue
        container = nearest_container(title_link)
        body_link = container.select_one('a[data-heatmap-target=".body"]') if container else None
        summary = clean_text(body_link.get_text(" ", strip=True)) if body_link else ""
        source = extract_source(container) if container else "Naver News"
        url = title_link.get("href", "")
        body = fetch_naver_article_body(url) if "n.news.naver.com" in url else ""
        if body:
            summary = f"{summary} {body[:260]}".strip()
        articles.append(NewsArticle(title=title, summary=summary, url=url, source=source))
    return articles


def nearest_container(node: Any) -> Any:
    current = node
    for _ in range(8):
        current = current.parent
        if current is None:
            return None
        if current.select_one('a[data-heatmap-target=".body"]'):
            return current
    return node.parent


def extract_source(container: Any) -> str:
    if container is None:
        return "Naver News"
    source = container.select_one(".sds-comps-profile-info-title-text")
    if source:
        return clean_text(source.get_text(" ", strip=True))
    return "Naver News"


def fetch_naver_article_body(url: str) -> str:
    try:
        page = fetch_text(url)
    except Exception:
        return ""
    soup = BeautifulSoup(page, "html.parser")
    node = soup.select_one("#dic_area") or soup.select_one("#newsct_article") or soup.select_one("article")
    if not node:
        return ""
    return clean_text(node.get_text(" ", strip=True))


def score_themes(articles: list[NewsArticle], metrics: list[dict[str, Any]]) -> list[tuple[str, int]]:
    text_blob = " ".join(f"{item.title} {item.summary}" for item in articles)
    scores: dict[str, int] = {}
    for theme, words in THEME_KEYWORDS.items():
        score = 0
        for word in words:
            score += text_blob.count(word) * 3
        score += market_theme_boost(theme, metrics)
        scores[theme] = score
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [item for item in ranked if item[1] > 0] or ranked[:4]


def market_theme_boost(theme: str, metrics: list[dict[str, Any]]) -> int:
    boost = 0
    for item in metrics:
        label = str(item.get("label", ""))
        delta = parse_delta(item.get("delta", ""))
        move_score = int(abs(delta) * 8)
        if theme == "반도체/HBM" and any(name in label for name in ("삼성전자", "SK하이닉스", "한미반도체")):
            boost += max(2, move_score)
        if theme == "금리/환율" and any(name in label for name in ("달러", "KOSPI", "KOSDAQ")):
            boost += max(1, move_score // 2)
        if theme == "에너지/유가" and any(name in label for name in ("WTI", "원유")):
            boost += max(2, move_score)
    return boost


def summarize_market_moves(metrics: list[dict[str, Any]]) -> str:
    moves = []
    for item in metrics:
        delta = parse_delta(item.get("delta", ""))
        if abs(delta) >= 1.0:
            moves.append(f"{item.get('label')} {item.get('delta')}")
    return ", ".join(moves[:4]) or "주요 가격 지표 변동은 제한적"


def related_articles(theme: str, articles: list[NewsArticle]) -> list[NewsArticle]:
    words = THEME_KEYWORDS.get(theme, set())
    scored = []
    for article in articles:
        text = f"{article.title} {article.summary}"
        score = sum(text.count(word) for word in words)
        if score:
            scored.append((score, article))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [article for _, article in scored]


def keywords_for_theme(theme: str, keyword_counts: Counter[str], article: NewsArticle) -> list[str]:
    theme_words = [word for word in THEME_KEYWORDS.get(theme, set()) if word in f"{article.title} {article.summary}"]
    top_words = [word for word, _ in keyword_counts.most_common(8) if word not in theme_words]
    return (theme_words + top_words)[:4]


def compose_issue_body(theme: str, keywords: list[str], article: NewsArticle, market_notes: str) -> str:
    keyword_text = ", ".join(keywords) if keywords else theme
    summary = article.summary or article.title
    return f"키워드: {keyword_text}. 시장 급등락: {market_notes}. 대표 뉴스: {article.title} - {summary[:110]}"


def count_keywords(articles: list[NewsArticle]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for article in articles:
        text = f"{article.title} {article.summary}"
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", text):
            token = normalize_token(token)
            if len(token) < 2 or token in STOPWORDS:
                continue
            counter[token] += 1
    return counter


def fallback_issues(metrics: list[dict[str, Any]]) -> list[dict[str, str]]:
    market_notes = summarize_market_moves(metrics)
    return [
        {
            "severity": "core",
            "title": "뉴스 수집 확인 필요",
            "body": f"네이버 금융 뉴스 수집 결과가 없어 시장 급등락 데이터만 반영했습니다. 시장 급등락: {market_notes}",
        }
    ]


def parse_delta(value: Any) -> float:
    text = str(value or "")
    matches = re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%", text)
    if matches:
        try:
            return float(matches[-1])
        except ValueError:
            return 0.0
    return 0.0


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        },
    )
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<.*?>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(value: str) -> str:
    return re.sub(r"<.*?>", " ", value or "")


def normalize_token(token: str) -> str:
    return token.strip("·,.…'\"[](){}")
