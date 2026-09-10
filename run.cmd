@echo off
setlocal
chcp 65001 >nul
if not exist "%~dp0tools\venv\Scripts\python.exe" (
  echo Runtime missing. Run: py -3.12 setup.py
  exit /b 1
)
"%~dp0tools\venv\Scripts\python.exe" "%~dp0workflow.py" %*
exit /b %errorlevel%
