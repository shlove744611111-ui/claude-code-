@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 이수ON - 웹UI 실행파일(EXE) 만들기

echo ==========================================================
echo   이수ON (웹 화면) - 실행파일(.exe) 생성
echo ----------------------------------------------------------
echo   더블클릭하면 브라우저에 '이수ON' 화면이 뜹니다.
echo   인터넷 없이 동작하고 OCR 엔진도 내장되어 있습니다.
echo ==========================================================
echo.

echo [1/2] 빌드 도구(pyinstaller) 설치...
python -m pip install --disable-pip-version-check -q --upgrade pip
python -m pip install --disable-pip-version-check -q pyinstaller
if errorlevel 1 (
  echo.
  echo [오류] 설치 실패. 인터넷 연결 또는 Python 설치를 확인하세요.
  pause
  exit /b 1
)

echo [2/2] 실행파일 생성 중... (수 분 걸릴 수 있습니다)
pyinstaller --noconfirm --onefile --windowed --name 이수ON --add-data "web;web" serve.py
if errorlevel 1 (
  echo.
  echo [오류] 실행파일 생성 실패.
  pause
  exit /b 1
)

echo.
echo 완료!  dist\이수ON.exe 를 더블클릭하면 브라우저에 화면이 뜹니다.
echo (이 exe 하나만 복사해서 어디서든 사용 가능)
explorer "%~dp0dist"
pause
