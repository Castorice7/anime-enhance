@echo off
setlocal
chcp 65001 >nul
if not exist "%~dp0tools\venv\Scripts\python.exe" (
  echo Runtime missing. Run: py -3.12 setup.py
  pause
  exit /b 1
)
if "%~1"=="" (
  echo Drag PNG, JPG, JPEG or WebP files onto this file. Default: faithful 2x.
  pause
  exit /b 1
)
"%~dp0tools\venv\Scripts\python.exe" "%~dp0workflow.py" image %*
pause
