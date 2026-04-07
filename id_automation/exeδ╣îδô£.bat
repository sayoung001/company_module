@echo off
chcp 65001 > nul
echo ========================================
echo   exe 파일 빌드
echo ========================================
echo.

cd /d "%~dp0"

REM PyInstaller 확인
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    echo PyInstaller 설치 중...
    pip install pyinstaller
)

echo.
echo exe 파일 생성 중... (약 1-2분 소요)
echo.

cd src
pyinstaller --onefile --windowed ^
    --name "신분증자동화" ^
    --add-data "excel_handler.py;." ^
    --collect-all customtkinter ^
    main.py

echo.
echo ========================================
if exist "dist\신분증자동화.exe" (
    echo [완료] exe 파일이 생성되었습니다!
    echo 위치: src\dist\신분증자동화.exe
) else (
    echo [오류] exe 파일 생성에 실패했습니다.
)
echo ========================================
echo.
pause
