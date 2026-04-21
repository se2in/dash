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

기본값인 `data_source: "sample"`은 샘플 데이터를 생성합니다. 실제 뉴스/API 결과를 연결하려면 `config.json`의 `data_source`를 바꿉니다.

- `json`: `data_json_path`의 JSON 파일을 읽습니다. 형식 예시는 `sources/dashboard_payload.example.json`입니다.
- `api`: `domestic_api_url`, `overseas_api_url`에서 JSON payload를 받아옵니다.
- `auto`: JSON 파일이 있으면 JSON을 먼저 쓰고, 없으면 API URL을 시도하며, 둘 다 없으면 샘플을 씁니다.

API 인증이 필요하면 토큰을 환경변수에 넣고 `api_auth_env`에 환경변수 이름을 설정합니다. 예를 들어 `MARKET_API_TOKEN`을 쓰면 API 요청에 `Authorization: Bearer <token>` 헤더가 붙습니다.
