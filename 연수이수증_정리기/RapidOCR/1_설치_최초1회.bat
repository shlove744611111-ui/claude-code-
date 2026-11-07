@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 이수ON(정밀OCR) - 최초 설치
echo ==========================================================
echo   이수ON (RapidOCR 한국어) - 최초 1회 설치
echo   OCR 엔진과 한글 모델을 받습니다. (인터넷 필요)
echo ==========================================================
echo.
echo [1/2] 엔진 설치 중...
python -m pip install --disable-pip-version-check --upgrade pip
python -m pip install --disable-pip-version-check rapidocr onnxruntime pypdfium2 pillow numpy
if errorlevel 1 ( echo [오류] 설치 실패. 인터넷/Python 확인. ^& pause ^& exit /b 1 )
echo [2/2] 한글 OCR 모델 내려받는 중... (수십 MB)
python _setup_model.py
if errorlevel 1 ( echo [오류] 모델 다운로드 실패. 인터넷 확인. ^& pause ^& exit /b 1 )
echo.
echo 설치 완료! "2_실행.bat" 더블클릭해서 사용하세요.
echo (배포용 exe를 만들려면 "EXE만들기.bat")
pause
