@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 연수 이수증 정리기

echo ================================================
echo   연수 이수증 정리기 (이 PC 안에서만 동작)
echo ================================================
echo.
echo 필요한 구성요소를 확인/설치합니다...
python -m pip install --disable-pip-version-check -q pdfplumber openpyxl pypdfium2 pillow pytesseract
if errorlevel 1 (
  echo.
  echo [오류] 설치에 실패했습니다. 인터넷 연결 또는 Python 설치를 확인하세요.
  pause
  exit /b 1
)

echo 프로그램을 시작합니다...
echo.
python cert_organizer.py
pause
