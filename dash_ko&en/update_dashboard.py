from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import db
from data_sources import load_external_payload
from market_collectors import collect_market_metrics
from naver_issues import build_domestic_core_issues
from telegram_news import collect_telegram_news


KST = ZoneInfo("Asia/Seoul")
MARKETS = {"domestic", "overseas"}


DEFAULT_CONFIG: dict[str, Any] = {
    "database_path": "data/market_dashboard.sqlite",
    "output_dir": "output",
    "domestic_output": "domestic_dashboard.html",
    "overseas_output": "overseas_dashboard.html",
    "domestic_title": "RISE ETF 국내 브리핑",
    "overseas_title": "RiseETF 글로벌 투자 브리핑",
    "brand": "RiseETF",
    "data_source": "live",
    "data_json_path": "sources/dashboard_payload.json",
    "domestic_api_url": "",
    "overseas_api_url": "",
    "api_timeout_seconds": 20,
    "api_auth_env": "",
    "api_auth_header": "Authorization",
    "api_auth_scheme": "Bearer",
    "domestic_watchlist": [
        {"code": "005930", "name": "삼성전자"},
        {"code": "000660", "name": "SK하이닉스"},
        {"code": "042700", "name": "한미반도체"},
    ],
    "overseas_tickers": {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "^DJI": "Dow Jones",
        "CL=F": "WTI 원유",
        "GC=F": "금",
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "KRW=X": "달러/원",
    },
    "telegram_enabled": True,
    "telegram_channels_path": "sources/telegram_channels.json",
    "telegram_session_path": "data/telegram_dashboard.session",
    "telegram_api_id_env": "TELEGRAM_API_ID",
    "telegram_api_hash_env": "TELEGRAM_API_HASH",
    "telegram_limit": 30,
    "telegram_messages_per_channel": 3,
    "naver_issue_enabled": True,
    "naver_news_limit": 32,
    "domestic_naver_news_queries": [
        "금융 증시",
        "코스피 코스닥",
        "반도체 삼성전자 SK하이닉스",
        "환율 금리 유가",
    ],
    "naver_client_id_env": "NAVER_CLIENT_ID",
    "naver_client_secret_env": "NAVER_CLIENT_SECRET",
    "naver_openapi_query": "금융 증시 반도체 환율",
}


def load_config(path: str | Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    config_path = Path(path)
    if config_path.exists():
        config.update(json.loads(config_path.read_text(encoding="utf-8")))
    return config


def kst_now() -> datetime:
    return datetime.now(KST)


def make_payload(market: str, now: datetime, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or DEFAULT_CONFIG
    source = str(config.get("data_source", "live")).lower()
    if source == "live":
        payload = make_domestic_payload(now) if market == "domestic" else make_overseas_payload(now)
        payload["metrics"] = collect_market_metrics(market, now, config)
        payload["news"] = collect_telegram_news(market, config)
        if market == "domestic":
            payload["alerts"] = build_domestic_core_issues(payload["metrics"], config, now)
        payload["headline"] = (
            "KRX/네이버금융 가격 데이터와 텔레그램 뉴스 기반 브리핑"
            if market == "domestic"
            else "yfinance 가격 데이터와 텔레그램 뉴스 기반 브리핑"
        )
        return payload
    external_payload = load_external_payload(market, now, config)
    if external_payload is not None:
        external_payload.setdefault("news", collect_telegram_news(market, config))
        return external_payload
    if market == "domestic":
        return make_domestic_payload(now)
    if market == "overseas":
        return make_overseas_payload(now)
    raise ValueError(f"지원하지 않는 market입니다: {market}")


def make_domestic_payload(now: datetime) -> dict[str, Any]:
    rnd = random.Random(f"domestic-{now:%Y-%m-%d}")
    kospi = 6200 + rnd.randint(-35, 35)
    kosdaq = 1170 + rnd.randint(-14, 16)
    return {
        "as_of_date": now.strftime("%Y-%m-%d"),
        "updated_at": now.isoformat(timespec="seconds"),
        "headline": "국내 증시 마감 이후 수급과 테마를 한 화면에 정리",
        "metrics": [
            metric("시장", "KOSPI", f"{kospi:,}", "+0.44%", "up", "기관 순매수 전환 여부 확인"),
            metric("시장", "KOSDAQ", f"{kosdaq:,}", "+0.41%", "up", "반도체 장비주 변동성 확대"),
            metric("시장", "S&P 500", "7,126", "+1.20%", "up", "야간 선물 흐름 참고"),
            metric("시장", "나스닥", "21,550", "-1.73%", "down", "AI 서버주 차익 실현"),
            metric("수급", "기관", "+1.81조", "순매수", "up", "지수 상승 견인"),
            metric("수급", "외국인", "-1,597억", "순매도", "down", "장중 변동성 확대"),
            metric("수급", "개인", "-2,775억", "순매도", "neutral", "차익 실현"),
            metric("가상자산", "Bitcoin", "$77,000", "+3.24%", "up", "위험선호 회복"),
            metric("가상자산", "Ethereum", "$2,424", "+3.89%", "up", "자동매매 관심 지속"),
        ],
        "sector_cards": [
            {
                "title": "반도체",
                "body": "SK하이닉스 실적 기대와 HBM 공급망 재평가. 삼성전자 장비 투자 확인 필요.",
                "tone": "hot",
            },
            {
                "title": "AI 전력/냉각",
                "body": "코세스, 전력기기, 냉각 장비가 데이터센터 증설 뉴스에 민감하게 반응.",
                "tone": "warm",
            },
            {
                "title": "2차전지",
                "body": "업황 회복 기대는 살아 있으나 확인 전까지는 단기 트레이딩 관점 유지.",
                "tone": "cool",
            },
            {
                "title": "방산",
                "body": "지정학 리스크와 수주 잔고가 동시 부각. 추격 매수보다 눌림 구간 선별.",
                "tone": "blue",
            },
        ],
        "alerts": [
            {
                "severity": "core",
                "title": "핵심 매크로 변수",
                "body": "미-이란 휴전 지속 여부와 유가 방향이 이번 주 국내 위험자산 선호를 좌우.",
            },
            {
                "severity": "risk",
                "title": "리스크",
                "body": "SK하이닉스 실적 발표 전후 HBM 가이던스가 기대보다 낮으면 장비주 동반 조정 가능.",
            },
        ],
        "ideas": [
            idea(
                1,
                "DRAM Capex 확장기, 삼성 추격 수혜 장비주",
                "반도체 장비",
                5,
                "SK하이닉스 1Q26 영업이익 전망과 DRAM Capex 증액 가능성에 장비주 재평가.",
                "실적 발표 이후 삼성전자 장비투자 재개 여부가 다음 확인 포인트.",
                ["원익IPS 074600", "주성엔지니어링 036930"],
                "삼성전자 Capex 가이던스 유지 시 모멘텀 지연",
                "RISE 반도체 ETF",
            ),
            idea(
                2,
                "AI 데이터센터 전력원, 연료전지 장비 단독 공급",
                "AI 전력 인프라",
                4,
                "AI 데이터센터 급증으로 전력 병목이 구조적 이슈로 부상.",
                "블룸에너지 500억 원 서버용 전력셀 수주 뉴스가 국내 밸류체인에 확산.",
                ["코세스 089890", "두산퓨얼셀 336260"],
                "수주 공백 또는 정책 보조금 축소",
                "RISE 글로벌 클라우드&통신 ETF",
            ),
            idea(
                3,
                "HBM4 세대 전환, TC본더 독점 공급사",
                "HBM 후공정",
                5,
                "HBM3에서 HBM4로 전환되며 패키징 정밀도 요구가 급증.",
                "SK하이닉스 HBM4 양산 일정과 장비 발주 확인이 핵심.",
                ["한미반도체 042700", "이오테크닉스 039030"],
                "양산 일정 지연 가능성",
                "RISE HBF 소부장 ETF",
            ),
            idea(
                4,
                "국내 데이터센터 붐, 전력기기 납기 병목 수혜",
                "전력 인프라",
                4,
                "국내 하이퍼스케일 IDC 신설과 노후 전력망 교체 사이클 동시 진행.",
                "일렉트릭에너지, 변압기, 전선 기업의 수출 잔고 확인.",
                ["LS일렉트릭 010120", "HD현대일렉트릭 267260"],
                "국내 IDC 인허가 지연",
                "RISE 글로벌 데이터센터 ETF",
            ),
        ],
        "events": make_events(now, "domestic"),
    }


def make_overseas_payload(now: datetime) -> dict[str, Any]:
    rnd = random.Random(f"overseas-{now:%Y-%m-%d}")
    spx = 7080 + rnd.randint(-50, 55)
    nasdaq = 24250 + rnd.randint(-120, 130)
    return {
        "as_of_date": now.strftime("%Y-%m-%d"),
        "updated_at": now.isoformat(timespec="seconds"),
        "headline": "미국 장 마감 이후 매크로, 원자재, 크립토, 글로벌 ETF 아이디어 정리",
        "metrics": [
            metric("미국 증시", "S&P 500", f"{spx:,}", "-0.61%", "down", "관세 우려와 실적 경계"),
            metric("미국 증시", "나스닥", f"{nasdaq:,}", "-0.62%", "down", "AI 서버주 차익 매물"),
            metric("미국 증시", "다우존스", "49,389", "-0.12%", "down", "방어주 상대 강세"),
            metric("원자재", "WTI 원유", "$93.18", "100달러 임박", "warn", "중동 리스크 프리미엄"),
            metric("원자재", "금", "$4,878", "신고점", "up", "안전자산 선호 지속"),
            metric("원자재", "달러/원", "-1,380대", "추정", "neutral", "환율 민감 업종 점검"),
            metric("가상자산", "BTC", "$75,242", "+1.9%", "up", "디지털 금 역할 부각"),
            metric("가상자산", "ETH", "$2,307", "+1.9%", "up", "ATH 대비 할인 구간"),
            metric("가상자산", "Fear&Greed", "26", "공포", "warn", "단기 변동성 유의"),
        ],
        "sector_cards": [
            {
                "title": "외국인 수급",
                "body": "한국 코스피 외국인 순매수 중 반도체 비중이 높아지면 국내 장비주 연동.",
                "tone": "green",
            },
            {
                "title": "원유/에너지",
                "body": "WTI 100달러 접근 시 에너지 ETF와 방산, 조선 기자재까지 파급 가능.",
                "tone": "hot",
            },
            {
                "title": "금/안전자산",
                "body": "금 신고점 랠리는 달러 약세와 지정학 리스크가 겹친 결과.",
                "tone": "warm",
            },
            {
                "title": "크립토",
                "body": "BTC ETF 자금 유입 지속. 단기 조정 시 기관 매수 대기 확인.",
                "tone": "blue",
            },
        ],
        "alerts": [
            {
                "severity": "urgent",
                "title": "긴급 이슈 감지",
                "body": "미-이란 휴전 종료 임박과 원유 변동성 확대. WTI 100달러 돌파 전후 리스크 관리.",
            },
            {
                "severity": "normal",
                "title": "반도체 수급",
                "body": "AI 서버 수요는 견조하지만 실적 발표 전후 차익 실현 가능성도 함께 모니터링.",
            },
        ],
        "ideas": [
            idea(
                1,
                "방산/미사일 방어, 전쟁 경제 최대 수혜",
                "국방산업",
                5,
                "중동과 동유럽 리스크가 동시에 남아 NATO 방위비 확대 압력이 지속.",
                "요격체계와 레이더 기업의 신규 수주 발표가 촉매.",
                ["RTX", "LMT", "NOC"],
                "휴전 장기화 시 단기 테마 약화",
                "RISE 글로벌 방산 ETF",
            ),
            idea(
                2,
                "원유/에너지, 호르무즈 재봉쇄 트리거",
                "에너지",
                4,
                "글로벌 원유 공급 13M배럴/일 차질 우려가 가격 상단을 열어둠.",
                "WTI 100달러 재돌파 여부와 정유 마진 확인.",
                ["GS", "XOM", "CVX"],
                "유가 급반락 시 이벤트 드리븐 포지션 훼손",
                "RISE 에너지 ETF",
            ),
            idea(
                3,
                "HBM/반도체 소부장, AI 인프라 Capex 슈퍼사이클",
                "반도체",
                5,
                "2026년 반도체 시장 성장률과 HBM 수요 전망이 계속 상향.",
                "빅테크 Capex 가이던스와 메모리 가격 상승률 확인.",
                ["SK하이닉스", "한미반도체", "TSM"],
                "빅테크 Capex 가이던스 실망",
                "RISE HBM ETF",
            ),
            idea(
                4,
                "금/안전자산, 불확실성 극대화와 신고점 랠리",
                "귀금속",
                4,
                "지정학 리스크와 달러 약세가 동시에 작동하며 금 가격 지지.",
                "금 5,000달러 돌파 시도와 ETF 자금 유입 확인.",
                ["GLD", "IAU", "금 선물"],
                "금리 반등과 달러 강세",
                "RISE 금현물 ETF",
            ),
        ],
        "events": make_events(now, "overseas"),
    }


def metric(
    group_name: str,
    label: str,
    value: str,
    delta: str,
    tone: str,
    note: str,
) -> dict[str, str]:
    return {
        "group_name": group_name,
        "label": label,
        "value": value,
        "delta": delta,
        "tone": tone,
        "note": note,
    }


def idea(
    rank: int,
    title: str,
    category: str,
    rating: int,
    big_picture: str,
    inflection: str,
    beneficiaries: list[str],
    risk: str,
    rise_etf: str,
) -> dict[str, Any]:
    return {
        "rank": rank,
        "title": title,
        "category": category,
        "rating": rating,
        "big_picture": big_picture,
        "inflection": inflection,
        "beneficiaries": beneficiaries,
        "risk": risk,
        "rise_etf": rise_etf,
    }


def make_events(now: datetime, market: str) -> list[dict[str, str]]:
    first = now.date()
    if market == "domestic":
        return [
            event(first, "한국", "지정학", "미-이란 휴전 만료와 유가 반응 확인"),
            event(first + timedelta(days=1), "한국", "물가", "생산자물가지수 발표"),
            event(first + timedelta(days=2), "한국", "실적", "SK하이닉스 실적 발표와 HBM 가이던스"),
            event(first + timedelta(days=2), "미국", "경기", "신규 실업수당 + PMI 발표"),
        ]
    return [
        event(first, "미국", "지정학", "중동 리스크와 원유 선물 장중 변동성"),
        event(first + timedelta(days=1), "미국", "실적", "빅테크 실적 시즌 본격화"),
        event(first + timedelta(days=2), "영국", "물가", "소비자물가지수 발표"),
        event(first + timedelta(days=2), "일본", "환율", "엔화 변동성 확대 여부 확인"),
    ]


def event(day: Any, region: str, label: str, body: str) -> dict[str, str]:
    return {
        "event_date": str(day),
        "region": region,
        "label": label,
        "body": body,
    }


def update_market(market: str, config: dict[str, Any]) -> Path:
    now = kst_now()
    payload = make_payload(market, now, config)
    output_path = output_file_for(market, config)

    with db.connect(config["database_path"]) as conn:
        db.init_db(conn)
        run_id = db.start_run(conn, market)
        try:
            db.replace_payload(conn, market, payload)
            stored = db.latest_payload(conn, market)
            if stored is None:
                raise RuntimeError("DB 저장 후 payload 조회에 실패했습니다.")
            render_dashboard(market, stored, output_path, config)
            db.finish_run(conn, run_id, "SUCCESS", str(output_path))
        except Exception as exc:
            db.finish_run(conn, run_id, "FAILED", str(exc))
            raise

    return output_path


def output_file_for(market: str, config: dict[str, Any]) -> Path:
    output_dir = Path(config["output_dir"])
    file_name = config["domestic_output"] if market == "domestic" else config["overseas_output"]
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / file_name


def render_dashboard(market: str, payload: dict[str, Any], path: Path, config: dict[str, Any]) -> None:
    theme = "light" if market == "domestic" else "dark"
    title = config["domestic_title"] if market == "domestic" else config["overseas_title"]
    html = build_html(theme, title, payload, config)
    path.write_text(html, encoding="utf-8")


def build_html(theme: str, title: str, payload: dict[str, Any], config: dict[str, Any]) -> str:
    metrics_by_group = group_by(payload["metrics"], "group_name")
    metric_sections = "\n".join(
        f"""
        <section class="panel metric-panel">
          <h2>{esc(group)}</h2>
          <div class="metric-grid">
            {''.join(metric_card(row) for row in rows)}
          </div>
        </section>
        """
        for group, rows in metrics_by_group.items()
    )
    sector_cards = "".join(
        f"""
        <article class="sector-card {esc(row['tone'])}">
          <strong>{esc(row['title'])}</strong>
          <p>{esc(row['body'])}</p>
        </article>
        """
        for row in payload["sector_cards"]
    )
    alerts = "".join(
        f"""
        <article class="alert {esc(row['severity'])}">
          <span>{esc(row['severity'])}</span>
          <div>
            <strong>{esc(row['title'])}</strong>
            <p>{esc(row['body'])}</p>
          </div>
        </article>
        """
        for row in payload["alerts"]
    )
    ideas = "".join(idea_card(row) for row in payload["ideas"])
    events = "".join(event_card(row) for row in payload["events"])
    news_items = payload.get("news", [])
    news = "".join(news_card(row) for row in news_items) or empty_news_card()
    brand = esc(config.get("brand", "RiseETF"))
    updated_at = payload["updated_at"].replace("T", " ")

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{
      --bg: {'#f5f7fb' if theme == 'light' else '#11151d'};
      --paper: {'#ffffff' if theme == 'light' else '#171c26'};
      --paper-2: {'#eef4ff' if theme == 'light' else '#0d1320'};
      --text: {'#1b2638' if theme == 'light' else '#f4f7fb'};
      --muted: {'#617089' if theme == 'light' else '#a7b0c2'};
      --line: {'#dce4ef' if theme == 'light' else '#2a3140'};
      --brand: #175aa8;
      --gold: #d99a28;
      --green: #2e9e62;
      --red: #d44f45;
      --blue: #2b74c7;
      --shadow: {'0 14px 36px rgba(31, 48, 76, .10)' if theme == 'light' else '0 18px 46px rgba(0, 0, 0, .30)'};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      letter-spacing: 0;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 44px;
    }}
    .hero {{
      min-height: 146px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 28px 34px;
      border-radius: 8px;
      background: linear-gradient(135deg, #123c78 0%, #175aa8 62%, #287b9e 100%);
      color: white;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }}
    .brand {{
      font-weight: 800;
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1;
    }}
    .subtitle {{
      margin-top: 12px;
      color: rgba(255, 255, 255, .78);
      font-size: 15px;
    }}
    .hero-meta {{
      min-width: 180px;
      text-align: right;
      font-weight: 700;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      margin-top: 12px;
      padding: 7px 12px;
      border-radius: 8px;
      background: rgba(255, 255, 255, .16);
      color: #fff0d5;
      font-size: 14px;
    }}
    .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 24px;
      margin-bottom: 22px;
    }}
    .panel h2 {{
      margin: 0 0 18px;
      font-size: 20px;
    }}
    .sector-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .sector-card {{
      min-height: 124px;
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--paper-2);
    }}
    .sector-card strong {{ font-size: 16px; }}
    .sector-card p, .alert p, .idea p, .event p {{
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.65;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    .sector-card.hot {{ border-color: rgba(212, 79, 69, .42); background: {'#fff0f2' if theme == 'light' else '#26151a'}; }}
    .sector-card.warm {{ border-color: rgba(217, 154, 40, .42); background: {'#fff7e9' if theme == 'light' else '#251f12'}; }}
    .sector-card.cool {{ border-color: rgba(43, 116, 199, .30); background: {'#eff6ff' if theme == 'light' else '#111d2d'}; }}
    .sector-card.blue {{ border-color: rgba(43, 116, 199, .42); }}
    .sector-card.green {{ border-color: rgba(46, 158, 98, .42); background: {'#eefaf3' if theme == 'light' else '#11251a'}; }}
    .metric-panel {{ padding-bottom: 14px; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric {{
      min-height: 108px;
      border-bottom: 1px solid var(--line);
      padding: 12px 4px 16px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 10px;
    }}
    .metric-value {{
      display: flex;
      align-items: baseline;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 24px;
      font-weight: 800;
    }}
    .metric-note {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .up {{ color: var(--green); }}
    .down {{ color: var(--red); }}
    .warn {{ color: var(--gold); }}
    .neutral {{ color: var(--muted); }}
    .alert-list {{
      display: grid;
      gap: 12px;
    }}
    .alert {{
      display: grid;
      grid-template-columns: 96px 1fr;
      gap: 12px;
      align-items: center;
      min-height: 88px;
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--paper-2);
    }}
    .alert span {{
      display: inline-flex;
      justify-content: center;
      padding: 7px 10px;
      border-radius: 8px;
      background: rgba(217, 154, 40, .16);
      color: var(--gold);
      font-weight: 800;
    }}
    .alert.urgent span, .alert.risk span {{ color: var(--red); background: rgba(212, 79, 69, .14); }}
    .idea-list {{
      display: grid;
      gap: 16px;
    }}
    .idea {{
      border: 1px solid var(--line);
      border-left: 5px solid var(--gold);
      border-radius: 8px;
      background: var(--paper);
      padding: 20px;
    }}
    .idea-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }}
    .idea-rank {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .idea-title {{
      font-size: 21px;
      font-weight: 850;
      line-height: 1.35;
    }}
    .stars {{
      color: var(--gold);
      white-space: nowrap;
      font-size: 18px;
    }}
    .idea-flow {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
      margin-top: 14px;
    }}
    .flow-box {{
      min-height: 142px;
      padding: 14px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--paper-2);
    }}
    .flow-box b {{
      display: block;
      margin-bottom: 8px;
      color: var(--brand);
      font-size: 13px;
    }}
    .tag-line {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
      color: var(--muted);
      font-size: 14px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 5px 9px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper-2);
    }}
    .event-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .news-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .event {{
      min-height: 138px;
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--paper-2);
    }}
    .news-card {{
      display: block;
      min-height: 172px;
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--paper-2);
      color: var(--text);
      text-decoration: none;
    }}
    .news-card:hover {{
      border-color: var(--brand);
      transform: translateY(-1px);
    }}
    .news-meta {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }}
    .news-title {{
      display: block;
      font-weight: 850;
      line-height: 1.45;
      margin-bottom: 8px;
    }}
    .news-summary {{
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    .event-date {{
      color: var(--brand);
      font-weight: 800;
      margin-bottom: 12px;
    }}
    .region {{
      display: inline-flex;
      margin-right: 6px;
      color: var(--green);
      font-weight: 800;
    }}
    @media (max-width: 900px) {{
      main {{ width: min(100% - 20px, 720px); padding-top: 10px; }}
      .hero {{ align-items: flex-start; flex-direction: column; padding: 24px; }}
      .hero-meta {{ text-align: left; }}
      .sector-grid, .metric-grid, .idea-flow, .event-grid, .news-grid {{ grid-template-columns: 1fr; }}
      .alert {{ grid-template-columns: 1fr; }}
      .idea-head {{ flex-direction: column; }}
    }}
  </style>
</head>
<body class="{theme}">
  <main>
    <header class="hero">
      <div>
        <div class="brand">{brand}</div>
        <div class="subtitle">{esc(title)} · {esc(payload['as_of_date'])} · Auto generated by Python</div>
      </div>
      <div class="hero-meta">
        <div>{esc(updated_at)} KST</div>
        <div class="badge">{esc(payload.get('headline', ''))}</div>
      </div>
    </header>

    <section class="panel">
      <h2>섹터 온도계</h2>
      <div class="sector-grid">{sector_cards}</div>
    </section>

    {metric_sections}

    <section class="panel">
      <h2>핵심 이슈</h2>
      <div class="alert-list">{alerts}</div>
    </section>

    <section class="panel">
      <h2>투자 아이디어</h2>
      <div class="idea-list">{ideas}</div>
    </section>

    <section class="panel">
      <h2>텔레그램 뉴스 Top 30</h2>
      <div class="news-grid">{news}</div>
    </section>

    <section class="panel">
      <h2>주요 이벤트</h2>
      <div class="event-grid">{events}</div>
    </section>
  </main>
</body>
</html>
"""


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return grouped


def metric_card(row: dict[str, Any]) -> str:
    tone = esc(row.get("tone", "neutral"))
    return f"""
    <article class="metric">
      <div class="metric-label">{esc(row['label'])}</div>
      <div class="metric-value">
        <span>{esc(row['value'])}</span>
        <small class="{tone}">{esc(row.get('delta') or '')}</small>
      </div>
      <div class="metric-note">{esc(row.get('note') or '')}</div>
    </article>
    """


def idea_card(row: dict[str, Any]) -> str:
    stars = "★" * int(row["rating"]) + "☆" * (5 - int(row["rating"]))
    beneficiaries = "".join(f'<span class="tag">{esc(item)}</span>' for item in row["beneficiaries"])
    return f"""
    <article class="idea">
      <div class="idea-head">
        <div>
          <div class="idea-rank">#{int(row['rank'])} · {esc(row['category'])}</div>
          <div class="idea-title">{esc(row['title'])}</div>
        </div>
        <div class="stars">{stars}</div>
      </div>
      <div class="idea-flow">
        <div class="flow-box"><b>BIG PICTURE</b><p>{esc(row['big_picture'])}</p></div>
        <div class="flow-box"><b>INFLECTION</b><p>{esc(row['inflection'])}</p></div>
        <div class="flow-box"><b>BENEFICIARY</b><p>{beneficiaries}</p></div>
      </div>
      <div class="tag-line">
        <span class="tag">리스크: {esc(row['risk'])}</span>
        <span class="tag">연결 ETF: {esc(row['rise_etf'])}</span>
      </div>
    </article>
    """


def event_card(row: dict[str, Any]) -> str:
    date_text = datetime.strptime(row["event_date"], "%Y-%m-%d").strftime("%m월 %d일")
    return f"""
    <article class="event">
      <div class="event-date">{esc(date_text)}</div>
      <strong><span class="region">{esc(row['region'])}</span>{esc(row['label'])}</strong>
      <p>{esc(row['body'])}</p>
    </article>
    """


def news_card(row: dict[str, Any]) -> str:
    subscribers = row.get("subscribers")
    subscribers_text = f"{int(subscribers):,}명" if subscribers else "구독자 확인 필요"
    url = str(row.get("url") or "").strip()
    source = row.get("source") or "Telegram"
    title = row.get("title") or source
    summary = row.get("summary") or ""
    if url:
        return f"""
        <a class="news-card" href="{esc(url)}" target="_blank" rel="noopener noreferrer">
          <div class="news-meta"><span>{esc(source)}</span><span>{esc(subscribers_text)}</span></div>
          <strong class="news-title">{esc(title)}</strong>
          <div class="news-summary">{esc(summary)}</div>
        </a>
        """
    return f"""
    <article class="news-card">
      <div class="news-meta"><span>{esc(source)}</span><span>{esc(subscribers_text)}</span></div>
      <strong class="news-title">{esc(title)}</strong>
      <div class="news-summary">{esc(summary)}</div>
    </article>
    """


def empty_news_card() -> str:
    return """
    <article class="news-card">
      <div class="news-meta"><span>Telegram</span><span>0명</span></div>
      <strong class="news-title">뉴스 소스 설정 필요</strong>
      <div class="news-summary">sources/telegram_channels.json 파일에 국내/해외 채널을 추가하세요.</div>
    </article>
    """


def esc(value: Any) -> str:
    return escape(str(value), quote=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="국내/해외 ETF 대시보드 DB 업데이트 및 HTML 생성")
    parser.add_argument(
        "market",
        choices=["domestic", "overseas", "all"],
        help="domestic=국내, overseas=해외, all=둘 다 생성",
    )
    parser.add_argument("--config", default="config.json", help="설정 JSON 경로")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)
    targets = sorted(MARKETS) if args.market == "all" else [args.market]
    for market in targets:
        output_path = update_market(market, config)
        print(f"{market}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
