@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 연수 이수증 정리기 - 실행파일(EXE) 만들기

echo ==========================================================
echo   연수 이수증 정리기 - 실행파일(.exe) 생성
echo ----------------------------------------------------------
echo   이 작업은 '내 PC' 에서만 이루어지며, 만들어진 exe 역시
echo   인터넷으로 아무것도 전송하지 않습니다.
echo ==========================================================
echo.

echo [1/3] 필요한 도구를 설치합니다... (pdfplumber, openpyxl, OCR, pyinstaller)
python -m pip install --disable-pip-version-check -q --upgrade pip
python -m pip install --disable-pip-version-check -q pdfplumber openpyxl pypdfium2 pillow pytesseract pyinstaller
if errorlevel 1 (
  echo.
  echo [오류] 설치 실패. 인터넷 연결 또는 Python 설치를 확인하세요.
  pause
  exit /b 1
)

echo [2/3] 실행파일을 생성합니다... (수 분 정도 걸릴 수 있습니다)
pyinstaller --noconfirm --onefile --windowed ^
  --name 이수ON ^
  --collect-all pdfminer ^
  --collect-all pdfplumber ^
  --collect-all pypdfium2 ^
  --add-data "tessdata;tessdata" ^
  cert_organizer.py
if errorlevel 1 (
  echo.
  echo [오류] 실행파일 생성에 실패했습니다.
  pause
  exit /b 1
)

echo [3/3] 완료!
echo.
echo  생성 위치:  "%~dp0dist\이수ON.exe"
echo  이 exe 파일만 복사해서 어디서든 더블클릭으로 사용할 수 있습니다.
echo.
explorer "%~dp0dist"
pause
