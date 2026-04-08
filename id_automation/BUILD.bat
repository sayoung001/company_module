@echo off
chcp 65001 >nul
echo ========================================
echo   ID Automation - BUILD EXE
echo   (exe file builder)
echo ========================================
echo.

cd /d "%~dp0"

if not exist "venv" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
)

echo [2/4] Activating venv...
call venv\Scripts\activate

echo [3/4] Installing dependencies...
pip install -r requirements.txt >nul 2>&1
pip install pyinstaller >nul 2>&1

echo [4/4] Building exe... (1-2 min)
cd src
pyinstaller --onefile --windowed ^
    --name "ID_Automation" ^
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
if exist "dist\ID_Automation.exe" (
    echo ========================================
    echo   BUILD SUCCESS!
    echo   File: %cd%\dist\ID_Automation.exe
    echo ========================================
    copy "dist\ID_Automation.exe" "..\..\" >nul 2>&1
) else (
    echo   BUILD FAILED! Check errors above.
)

echo.
pause
