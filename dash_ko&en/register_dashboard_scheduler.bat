@echo off
setlocal

set "ROOT=%~dp0"
set "DASH_ROOT=%ROOT%"
set "TASK_DOMESTIC=ETF Domestic Dashboard Update"
set "TASK_OVERSEAS=ETF Overseas Dashboard Update"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python or add it to PATH, then run again.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=$env:DASH_ROOT; $python=(Get-Command python).Source; $domesticAction=New-ScheduledTaskAction -Execute $python -Argument 'update_dashboard.py domestic --config config.json' -WorkingDirectory $root; $overseasAction=New-ScheduledTaskAction -Execute $python -Argument 'update_dashboard.py overseas --config config.json' -WorkingDirectory $root; $domesticTrigger=New-ScheduledTaskTrigger -Daily -At 15:00; $overseasTrigger=New-ScheduledTaskTrigger -Daily -At 03:00; Register-ScheduledTask -TaskName $env:TASK_DOMESTIC -Action $domesticAction -Trigger $domesticTrigger -Description 'Update domestic ETF dashboard at 15:00 KST' -Force | Out-Null; Register-ScheduledTask -TaskName $env:TASK_OVERSEAS -Action $overseasAction -Trigger $overseasTrigger -Description 'Update overseas ETF dashboard at 03:00 KST' -Force | Out-Null"
if errorlevel 1 (
  echo Scheduler registration failed.
  pause
  exit /b 1
)

echo Scheduler registration complete:
echo - Domestic dashboard: daily 15:00
echo - Overseas dashboard: daily 03:00
pause
