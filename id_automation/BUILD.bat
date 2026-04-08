@echo off
chcp 65001 >nul
echo ========================================
echo   ID Automation - BUILD EXE
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

echo [4/4] Building exe... (2-3 min)
cd src

REM onedir: dist/ID_Automation/ folder with exe + all files
pyinstaller --onedir --windowed ^
    --name "ID_Automation" ^
    --hidden-import=openpyxl ^
    --hidden-import=numpy ^
    --hidden-import=cv2 ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=PyPDF2 ^
    --hidden-import=requests ^
    --collect-all customtkinter ^
    main.py

echo.
if exist "dist\ID_Automation\ID_Automation.exe" (
    echo ========================================
    echo   BUILD SUCCESS!
    echo.
    echo   Location: %cd%\dist\ID_Automation\
    echo   Run: dist\ID_Automation\ID_Automation.exe
    echo.
    echo   To share: copy the entire
    echo   "dist\ID_Automation" folder.
    echo ========================================
) else (
    echo   BUILD FAILED! Check errors above.
)

echo.
pause
