@echo off
chcp 65001 >nul
echo ========================================
echo   신분증 자동화 프로그램 exe 빌드
echo ========================================
echo.

cd /d "%~dp0"

REM 가상환경 확인
if not exist "venv" (
    echo [1/4] 가상환경 생성 중...
    python -m venv venv
)

echo [2/4] 가상환경 활성화...
call venv\Scripts\activate

echo [3/4] 의존성 설치 중...
pip install -r requirements.txt >nul 2>&1
pip install pyinstaller >nul 2>&1

echo [4/4] exe 빌드 중... (1~2분 소요)
cd src
pyinstaller --onefile --windowed ^
    --name "신분증자동화" ^
    --add-data "../requirements.txt;." ^
    --hidden-import=openpyxl ^
    --hidden-import=numpy ^
    --hidden-import=cv2 ^
    --hidden-import=PIL ^
    --hidden-import=PyPDF2 ^
    --hidden-import=requests ^
    --collect-all customtkinter ^
    main.py

echo.
if exist "dist\신분증자동화.exe" (
    echo ========================================
    echo   빌드 성공!
    echo   실행 파일: %cd%\dist\신분증자동화.exe
    echo ========================================
    echo.

    REM dist 폴더를 상위로 복사
    copy "dist\신분증자동화.exe" "..\..\신분증자동화.exe" >nul 2>&1
    echo   복사 완료: %~dp0신분증자동화.exe
) else (
    echo   빌드 실패! 오류를 확인하세요.
)

echo.
pause
