from pathlib import Path
from datetime import datetime, timedelta, date
from io import StringIO
import json, re, requests, pandas as pd, yfinance as yf
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
FG_HEADERS = {
    **HEADERS,
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
}
FN_GUIDE_URL = "https://comp.fnguide.com/SVO2/ASP/SVD_Report_Summary.asp?pGB=1&gicode=A005930&cID=&MenuYn=Y&ReportGB=&NewMenuID=901&stkGb=701"
EARNINGS_WATCHLIST = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "NFLX", "AMD",
    "ORCL", "CRM", "COST", "WMT", "JPM", "BAC", "GS", "C", "UNH", "JNJ",
    "PFE", "XOM", "CVX", "NKE", "ADBE", "MU", "UBER", "PLTR", "TSM", "DIS",
    "INTC", "QCOM",
]


def fetch_csv(series_id):
    txt = requests.get(
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
        headers=HEADERS,
        timeout=25,
    ).text
    df = pd.read_csv(StringIO(txt))
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
    return df.dropna().sort_values("DATE")


def pct_text(cur, prev, suffix="vs prev close"):
    try:
        cur = float(cur)
        prev = float(prev)
        if prev == 0:
            return "-"
        pct = (cur / prev - 1) * 100
        return f"{'+' if pct >= 0 else ''}{pct:.2f}% {suffix}"
    except Exception:
        return "-"


def last_quote(ticker):
    hist = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
    if hist.empty:
        return ("NA", "-")
    close = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else close
    return (f"{close:,.2f}", pct_text(close, prev))


def latest_cpi_yoy():
    df = fetch_csv("CPIAUCSL")
    latest = df.iloc[-1]
    prev12 = df.iloc[-13]
    yoy = (latest["CPIAUCSL"] / prev12["CPIAUCSL"] - 1) * 100
    return f"{yoy:.2f}%", latest["DATE"].strftime("%Y-%m")


def latest_nfp_mom():
    df = fetch_csv("PAYEMS")
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = latest["PAYEMS"] - prev["PAYEMS"]
    return f"{'+' if change >= 0 else ''}{change:,.0f}K", latest["DATE"].strftime("%Y-%m")


def latest_yield_spread():
    df = fetch_csv("T10Y2Y")
    latest = float(df["T10Y2Y"].iloc[-1])
    prev = float(df["T10Y2Y"].iloc[-2]) if len(df) > 1 else latest
    delta = latest - prev
    return f"{latest:.2f}%", f"{'+' if delta >= 0 else ''}{delta:.2f}pt vs prior"


def parse_bls_schedule():
    html = requests.get(
        "https://www.bls.gov/schedule/news_release/current_year.asp",
        headers=HEADERS,
        timeout=25,
    ).text
    cpi_date = "-"
    nfp_date = "-"
    try:
        for tbl in pd.read_html(StringIO(html)):
            for _, row in tbl.iterrows():
                text = " | ".join([str(x) for x in row.tolist()])
                if cpi_date == "-" and "Consumer Price Index" in text:
                    m = re.search(r"([A-Za-z]+\s+\d{1,2},\s+\d{4})", text)
                    if m:
                        cpi_date = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
                if nfp_date == "-" and "Employment Situation" in text:
                    m = re.search(r"([A-Za-z]+\s+\d{1,2},\s+\d{4})", text)
                    if m:
                        nfp_date = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
    except Exception:
        pass

    if cpi_date == "-" or nfp_date == "-":
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        current_date = None
        today = date.today()
        date_re = re.compile(
            r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})$"
        )
        for line in lines:
            m = date_re.match(line)
            if m:
                try:
                    current_date = datetime.strptime(
                        f"{m.group(2)} {m.group(3)} {m.group(4)}", "%B %d %Y"
                    ).date()
                except Exception:
                    current_date = None
                continue
            if current_date and current_date >= today:
                if cpi_date == "-" and "Consumer Price Index" in line:
                    cpi_date = current_date.strftime("%Y-%m-%d")
                if nfp_date == "-" and "Employment Situation" in line:
                    nfp_date = current_date.strftime("%Y-%m-%d")
            if cpi_date != "-" and nfp_date != "-":
                break
    return cpi_date, nfp_date


def third_friday(year, month):
    d = date(year, month, 15)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def option_expiry_text():
    today = date.today()
    this_friday = today + timedelta(days=(4 - today.weekday()) % 7)
    monthly = third_friday(today.year, today.month)
    note = "주간 만기"
    if this_friday == monthly:
        note = "월간 만기"
        if today.month in (3, 6, 9, 12):
            note = "쿼드러플 위칭 가능성"
    return this_friday.strftime("%Y-%m-%d"), note


def fear_label(score):
    s = int(round(float(score)))
    if s <= 24:
        return "Extreme Fear"
    if s <= 44:
        return "Fear"
    if s <= 55:
        return "Neutral"
    if s <= 75:
        return "Greed"
    return "Extreme Greed"


def fetch_fear_greed():
    for url in [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/",
    ]:
        try:
            r = requests.get(url, headers=FG_HEADERS, timeout=20)
            if r.ok:
                data = r.json()
                fg = data.get("fear_and_greed") or data.get("fearAndGreed") or {}
                score = fg.get("score")
                label = fg.get("rating") or fg.get("label") or fg.get("status")
                if score is None:
                    hist = data.get("fear_and_greed_historical", {}).get("data", [])
                    if hist:
                        last = hist[-1]
                        score = last.get("y") or last.get("score") or last.get("value")
                if score is not None:
                    return str(int(round(float(score)))), (label or fear_label(score))
        except Exception:
            pass
    return "-", "unavailable"


def parse_single_earnings_date(ticker):
    try:
        obj = yf.Ticker(ticker)
        df = obj.get_earnings_dates(limit=6)
        if df is None or len(df) == 0:
            return None
        reset = df.reset_index()
        date_col = reset.columns[0]
        eps_col = "EPS Estimate" if "EPS Estimate" in reset.columns else None
        try:
            info = obj.info
        except Exception:
            info = {}
        for _, row in reset.iterrows():
            dt = pd.to_datetime(row[date_col], errors="coerce")
            if pd.isna(dt):
                continue
            d = dt.date()
            today = date.today()
            if today <= d <= (today + timedelta(days=7)):
                hour = dt.hour
                tm = "BMO" if hour < 11 else ("AMC" if hour >= 16 else dt.strftime("%H:%M"))
                name = info.get("shortName") or info.get("longName") or ticker
                return {
                    "date": d.isoformat(),
                    "symbol": ticker,
                    "company": str(name)[:80],
                    "eps_estimate": "-" if not eps_col else str(row.get(eps_col, "-")),
                    "time": tm,
                }
    except Exception:
        return None
    return None


def weekly_earnings_from_watchlist():
    rows = []
    for ticker in EARNINGS_WATCHLIST:
        item = parse_single_earnings_date(ticker)
        if item:
            rows.append(item)
    rows.sort(key=lambda x: (x["date"], x["symbol"]))
    return rows[:20]


def fetch_nextrade_premarket():
    url = "https://www.nextrade.co.kr/main.do"
    r = requests.get(url, headers=HEADERS, timeout=25)
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [x.strip() for x in text.splitlines() if x.strip()]

    basis = "기준 정보 -"
    session = "08:00~08:50"
    change = "-"
    issues = "-"
    volume = "-"
    value = "-"
    note = "* 등락률은 기준시점 대비 시가총액의 증감률임"

    m_basis = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+기준 정보\s+NXT 정규시장 체결기준)", text)
    if m_basis:
        basis = m_basis.group(1)

    try:
        idx = lines.index("프리마켓 08:00~08:50")
        session = "08:00~08:50"
        for i in range(idx, min(idx + 20, len(lines))):
            if lines[i] == "프리마켓 08:00~08:50":
                continue
            if lines[i] == "등락률(기준가 대비)" and i + 1 < len(lines):
                change = lines[i + 1]
            elif lines[i] == "거래종목 수" and i + 1 < len(lines):
                issues = lines[i + 1]
            elif lines[i] == "거래량(주)" and i + 1 < len(lines):
                volume = lines[i + 1]
            elif lines[i] == "거래대금(원)" and i + 1 < len(lines):
                value = lines[i + 1]
            elif lines[i].startswith("메인마켓"):
                break
        if idx + 1 < len(lines) and re.match(r"^프리마켓\s+", lines[idx]):
            session = lines[idx].replace("프리마켓", "").strip() or session
    except ValueError:
        m = re.search(
            r"프리마켓\s*([0-9:~]+).*?등락률\(기준가 대비\)\s*([+\-]?[0-9.]+%).*?거래종목 수\s*([0-9,]+).*?거래량\(주\)\s*([0-9,]+).*?거래대금\(원\)\s*([0-9,]+)",
            text,
            re.S,
        )
        if m:
            session, change, issues, volume, value = m.groups()

    return {
        "nextrade_basis": basis,
        "nextrade_session": session,
        "nextrade_change": change,
        "nextrade_issues": issues,
        "nextrade_volume": volume,
        "nextrade_value": value,
        "nextrade_note": note,
    }


def fetch_fedwatch_unofficial():
    """
    비공식 방식:
    growbeansprout의 FedWatch 요약 페이지에서
    다음 FOMC 회의일과 동결 확률을 읽고,
    나머지는 '변경' 확률로 계산한다.
    """
    url = "https://growbeansprout.com/tools/fedwatch"
    html = requests.get(url, headers=HEADERS, timeout=25).text
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)

    meeting = "-"
    hold_pct = None
    data_as_of = "-"

    m_meeting = re.search(
        r"next Federal Open Market Committee \(FOMC\) meeting will be on ([0-9]{1,2} [A-Za-z]+ [0-9]{4})",
        text,
        re.I,
    )
    if m_meeting:
        try:
            meeting = datetime.strptime(m_meeting.group(1), "%d %b %Y").strftime("%Y-%m-%d")
        except Exception:
            meeting = m_meeting.group(1)

    m_hold = re.search(
        r"there is a ([0-9]+(?:\.[0-9]+)?)% probability .*?maintain interest rates",
        text,
        re.I | re.S,
    )
    if m_hold:
        hold_pct = float(m_hold.group(1))

    m_asof = re.search(r"Data as of ([0-9]{1,2} [A-Za-z]+ [0-9]{4})", text, re.I)
    if m_asof:
        data_as_of = m_asof.group(1)

    if hold_pct is None:
        return {
            "fedwatch_hold": "동결 -",
            "fedwatch_hike": "변경 -",
            "fedwatch_date": "클릭 시 CME FedWatch 열기",
        }

    change_pct = max(0.0, 100.0 - hold_pct)
    return {
        "fedwatch_hold": f"동결 {hold_pct:.1f}%",
        "fedwatch_hike": f"변경 {change_pct:.1f}%",
        "fedwatch_date": f"{meeting} · 기준 {data_as_of}",
    }


def fetch_doughcon_status():
    url = "https://www.pizzint.watch/?utm_source=chatgpt.com"
    html = requests.get(url, headers=HEADERS, timeout=25).text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    compact = re.sub(r"\s+", " ", text)

    level = None
    location = None
    status = None

    m = re.search(r"DOUGHCON\s*(\d)", compact, re.I)
    if m:
        level = f"DOUGHCON {m.group(1)}"

    m_loc = re.search(
        r"DOUGHCON\s*\d\s*([A-Z][A-Z\s]{2,40}?)\s*[•·]\s*([A-Z][A-Z\s]{5,80}?)($| DOUGHCON| Pentagon| About| FAQ)",
        compact,
    )
    if m_loc:
        location = m_loc.group(1).strip()
        status = m_loc.group(2).strip()

    if not location:
        for candidate in ["ROUND HOUSE", "WATCH OFFICE", "HOT SLICE"]:
            if candidate in compact.upper():
                location = candidate
                break

    if not status:
        m_status = re.search(
            r"(INCREASE IN FORCE READINESS|ELEVATED WATCH|ACTIVE MONITORING|HEIGHTENED ALERT)",
            compact,
            re.I,
        )
        if m_status:
            status = m_status.group(1).upper()

    if not level:
        level = "DOUGHCON 3"
    if not location:
        location = "ROUND HOUSE"
    if not status:
        status = "INCREASE IN FORCE READINESS"

    return {
        "doughcon_level": level,
        "doughcon_location": location,
        "doughcon_status": status,
        "doughcon_note": "클릭 시 PizzINT 열기",
    }


def fetch_fnguide_report_summary(url=FN_GUIDE_URL, limit=8):
    html = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://comp.fnguide.com/"},
        timeout=20,
    ).text
    tables = pd.read_html(StringIO(html))
    target = None
    for tbl in tables:
        cols = [str(c).strip() for c in tbl.columns]
        joined = " | ".join(cols)
        if ("일자" in joined or "날짜" in joined) and ("투자의견" in joined) and ("목표주가" in joined):
            target = tbl.copy()
            break
    if target is None:
        return []
    target.columns = [str(c).strip() for c in target.columns]

    def pick(row, candidates):
        for c in candidates:
            if c in row.index:
                return str(row.get(c, "-"))
        return "-"

    rows = []
    for _, row in target.head(limit).iterrows():
        rows.append(
            {
                "date": pick(row, ["일자", "날짜"]),
                "title": pick(row, ["종목명 - 리포트 요약", "종목명-리포트 요약", "리포트 요약", "제목"]),
                "opinion": pick(row, ["투자의견"]),
                "target_price": pick(row, ["목표주가"]),
                "close_price": pick(row, ["전일종가"]),
                "author": pick(row, ["제공처/작성자", "작성자"]),
            }
        )
    return rows


data = {}
for key, ticker in {
    "sp500": "^GSPC",
    "vix": "^VIX",
    "gold": "GC=F",
    "oil": "CL=F",
    "btc": "BTC-USD",
    "usdkrw": "KRW=X",
}.items():
    try:
        q, chg = last_quote(ticker)
        data[key] = q
        data[f"{key}_chg"] = chg
    except Exception:
        data[key] = "NA"
        data[f"{key}_chg"] = "-"

for func, keys in [
    (latest_yield_spread, ("yield_spread", "yield_spread_chg")),
    (fetch_fear_greed, ("fear_greed", "fear_greed_label")),
    (option_expiry_text, ("options_expiry", "options_note")),
    (latest_cpi_yoy, ("cpi_yoy", "cpi_date")),
    (latest_nfp_mom, ("nfp_mom", "nfp_date")),
    (parse_bls_schedule, ("next_cpi", "next_nfp")),
]:
    try:
        a, b = func()
        data[keys[0]] = a
        data[keys[1]] = b
    except Exception:
        data[keys[0]] = "-"
        data[keys[1]] = "-"

try:
    data.update(fetch_nextrade_premarket())
except Exception:
    data["nextrade_basis"] = "기준 정보 -"
    data["nextrade_session"] = "08:00~08:50"
    data["nextrade_change"] = "-"
    data["nextrade_issues"] = "-"
    data["nextrade_volume"] = "-"
    data["nextrade_value"] = "-"
    data["nextrade_note"] = "클릭 시 넥스트레이드 열기"

try:
    data.update(fetch_fedwatch_unofficial())
except Exception:
    data["fedwatch_hold"] = "동결 -"
    data["fedwatch_hike"] = "변경 -"
    data["fedwatch_date"] = "클릭 시 CME FedWatch 열기"

try:
    data.update(fetch_doughcon_status())
except Exception:
    data["doughcon_level"] = "DOUGHCON 3"
    data["doughcon_location"] = "ROUND HOUSE"
    data["doughcon_status"] = "INCREASE IN FORCE READINESS"
    data["doughcon_note"] = "클릭 시 PizzINT 열기"

try:
    data["earnings"] = weekly_earnings_from_watchlist()
except Exception:
    data["earnings"] = []

try:
    data["fnguide_reports"] = fetch_fnguide_report_summary()
except Exception:
    data["fnguide_reports"] = []

data["fnguide_url"] = FN_GUIDE_URL
data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
(BASE_DIR / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
(BASE_DIR / "data.js").write_text(
    "window.dashboardData = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
    encoding="utf-8",
)
print("Dashboard updated.")
