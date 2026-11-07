@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 이수ON - 배포용 exe 만들기
echo 배포용 실행파일(.exe)을 만듭니다. (먼저 1_설치_최초1회.bat 을 돌려두세요)
python -m pip install --disable-pip-version-check pyinstaller
pyinstaller --noconfirm --onefile --windowed --name 이수ON ^
  --collect-all rapidocr ^
  --collect-all onnxruntime ^
  --collect-all pypdfium2 ^
  --add-data "web;web" ^
  --add-data "models;models" ^
  serve.py
if errorlevel 1 ( echo [오류] 생성 실패. ^& pause ^& exit /b 1 )
echo 완료! dist\이수ON.exe 를 배포하세요. (받는 사람은 더블클릭만)
explorer "%~dp0dist"
pause
