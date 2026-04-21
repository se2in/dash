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

현재 `data_source`는 `sample`입니다. 증권사 API, 크롤링 데이터, 텔레그램/뉴스 요약 파일, 기존 ETF 모니터 DB를 연결하려면 `update_dashboard.py`의 `make_domestic_payload`, `make_overseas_payload` 함수만 실제 수집 함수로 교체하면 됩니다.
