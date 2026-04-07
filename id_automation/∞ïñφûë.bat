@echo off
chcp 65001 > nul
echo ========================================
echo   신분증 자동화 프로그램 실행
echo ========================================
echo.

cd /d "%~dp0"

REM Python 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo Python 3.10 이상을 설치해주세요.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 의존성 확인 및 설치
echo 의존성 확인 중...
pip show customtkinter > nul 2>&1
if errorlevel 1 (
    echo 필요한 패키지를 설치합니다...
    pip install -r requirements.txt
)

REM 프로그램 실행
echo.
echo 프로그램을 시작합니다...
cd src
python main.py

pause
