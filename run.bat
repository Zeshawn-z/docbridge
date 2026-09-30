@echo off
rem md2docx drag-and-drop launcher
rem Usage: drag a .md file onto this file, or run:
rem     run.bat report.md
rem     run.bat report.md -c config/thesis.yaml -o out\report.docx
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [!] Python venv not found: %PY%
  echo     Create it first:
  echo       python -m venv .venv
  echo       .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

if "%~1"=="" (
  echo [!] No input file.
  echo     Drag a Markdown file onto this script, or run: run.bat file.md
  pause
  exit /b 1
)

"%PY%" "%ROOT%md2docx.py" %*
echo.
echo [done] exit code = %ERRORLEVEL%
pause
