@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
for /f %%i in ('powershell -nologo -command "Get-Date -Format yyyy-MM-dd"') do set D=%%i
"C:\Python314\python.exe" run_all.py > "logs\run_%D%.log" 2>&1

