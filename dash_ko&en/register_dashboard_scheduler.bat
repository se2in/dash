@echo off
setlocal

set "ROOT=%~dp0"
set "TASK_DOMESTIC=ETF Domestic Dashboard Update"
set "TASK_OVERSEAS=ETF Overseas Dashboard Update"

where python >nul 2>nul
if errorlevel 1 (
  echo Python을 찾지 못했습니다. Python 설치 후 다시 실행해 주세요.
  pause
  exit /b 1
)

schtasks /Create /F /TN "%TASK_DOMESTIC%" /SC DAILY /ST 15:00 /TR "cmd /c cd /d ""%ROOT%"" && python update_dashboard.py domestic --config config.json"
if errorlevel 1 (
  echo 국내 대시보드 작업 등록 실패
  pause
  exit /b 1
)

schtasks /Create /F /TN "%TASK_OVERSEAS%" /SC DAILY /ST 03:00 /TR "cmd /c cd /d ""%ROOT%"" && python update_dashboard.py overseas --config config.json"
if errorlevel 1 (
  echo 해외 대시보드 작업 등록 실패
  pause
  exit /b 1
)

echo 등록 완료:
echo - 국내 대시보드: 매일 오후 3시
echo - 해외 대시보드: 매일 새벽 3시
pause
