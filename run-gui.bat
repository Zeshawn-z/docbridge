@echo off
rem Launch DocBridge without a console window.
setlocal
set "ROOT=%~dp0"
set "PYW=%ROOT%.venv\Scripts\pythonw.exe"
set "PY=%ROOT%.venv\Scripts\python.exe"

if exist "%PYW%" (
  start "" "%PYW%" "%ROOT%md2docx_gui.py"
  exit /b 0
)

if exist "%PY%" (
  "%PY%" "%ROOT%md2docx_gui.py"
  exit /b %ERRORLEVEL%
)

echo [!] Python venv not found.
echo     python -m venv .venv
echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
pause
exit /b 1
