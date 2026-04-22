# 국내/해외 ETF 대시보드 자동 업데이트

이미지 예시처럼 국내 대시보드는 밝은 화면, 해외 대시보드는 어두운 화면으로 생성합니다.
`db.py`가 SQLite DB를 관리하고, `update_dashboard.py`가 DB 업데이트와 HTML 대시보드 생성을 담당합니다.

## 파일

- `db.py`: SQLite 테이블 생성, 실행 이력 저장, 대시보드 데이터 저장/조회
- `update_dashboard.py`: 국내/해외 데이터 생성, DB 반영, HTML 생성
- `config.json`: DB 경로와 출력 파일명 설정
- `run_dashboard_once.bat`: 국내/해외 대시보드를 한 번에 수동 생성
- `register_dashboard_scheduler.bat`: Windows 작업 스케줄러 등록

## 수동 실행

```powershell
python .\update_dashboard.py all --config .\config.json
```

생성 파일:

- `output/domestic_dashboard.html`
- `output/overseas_dashboard.html`

## 자동 업데이트

`register_dashboard_scheduler.bat`을 우클릭해서 관리자 권한으로 실행하면 아래 작업이 등록됩니다.

- 국내 대시보드: 매일 오후 3시
- 해외 대시보드: 매일 새벽 3시

Windows 작업 스케줄러는 PC의 로컬 시간대를 사용합니다. 현재 사용 환경 기준으로 한국 시간에 맞춰 실행됩니다.

## 실제 데이터 연결

기본값인 `data_source: "live"`는 국내는 네이버금융을 우선 사용하고 KRX/pykrx를 보조로 사용하며, 해외는 yfinance로 가격 데이터를 가져옵니다. 실제 뉴스/API 결과를 직접 넣으려면 `config.json`의 `data_source`를 바꿉니다.

- `live`: 국내 KRX/네이버금융, 해외 yfinance, 텔레그램 뉴스 설정을 사용합니다.
- `sample`: 샘플 데이터를 생성합니다.
- `json`: `data_json_path`의 JSON 파일을 읽습니다. 형식 예시는 `sources/dashboard_payload.example.json`입니다.
- `api`: `domestic_api_url`, `overseas_api_url`에서 JSON payload를 받아옵니다.
- `auto`: JSON 파일이 있으면 JSON을 먼저 쓰고, 없으면 API URL을 시도하며, 둘 다 없으면 샘플을 씁니다.

API 인증이 필요하면 토큰을 환경변수에 넣고 `api_auth_env`에 환경변수 이름을 설정합니다. 예를 들어 `MARKET_API_TOKEN`을 쓰면 API 요청에 `Authorization: Bearer <token>` 헤더가 붙습니다.

## 국내 핵심 이슈

국내 대시보드의 `핵심 이슈`는 `live` 모드에서 네이버 뉴스 검색 결과를 읽어 자동 생성합니다.

- 네이버 뉴스 검색 결과의 제목과 본문 요약을 수집합니다.
- 네이버뉴스 본문 링크가 있으면 본문 영역을 추가로 읽습니다.
- 뉴스 키워드 빈도와 네이버금융 급등락 데이터를 결합합니다.
- 상위 테마 4개를 `핵심 이슈` 카드로 생성합니다.

공식 네이버 검색 API 키가 있으면 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 환경변수를 설정해 API 경로를 우선 사용할 수 있습니다. 키가 없으면 개발자도구에서 확인되는 네이버 검색 HTML 구조를 사용합니다.

## 텔레그램 뉴스

`sources/telegram_channels.json` 파일에 구독 중인 뉴스 채널을 넣으면 구독자 수 기준 상위 30개를 국내/해외 대시보드에 나눠 표시합니다. 형식 예시는 `sources/telegram_channels.example.json`입니다.

개인 채널 목록인 `sources/telegram_channels.json`은 GitHub에 올라가지 않도록 `.gitignore`에 포함되어 있습니다.

Telegram API로 최신 메시지와 구독자 수를 자동 수집하려면 환경변수를 설정합니다.

```powershell
$env:TELEGRAM_API_ID="123456"
$env:TELEGRAM_API_HASH="your_api_hash"
```

API 설정이 없으면 `telegram_channels.json`에 `latest_text`, `subscribers`, `message_id`를 직접 넣은 항목만 표시합니다.

## Python 패키지

```powershell
python -m pip install -r requirements.txt
```

`yfinance`는 해외 지표, `pykrx`는 국내 KRX 지표, `telethon`은 텔레그램 자동 수집에 사용합니다.
