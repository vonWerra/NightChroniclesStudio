@echo off
:: ================================================
:: Claude Generator - Launcher
:: ================================================

title Claude Text Generator
color 0A

echo.
echo ========================================
echo     CLAUDE NARRATION GENERATOR
echo ========================================
echo.

:: Set project path
set PROJECT_DIR=D:\NightChronicles\claude_generator
set SCRIPT_NAME=claude_generator_simple.py

:: Change to project directory
echo [1/4] Changing to project directory...
cd /d %PROJECT_DIR%

if errorlevel 1 (
    echo [ERROR] Cannot access project directory!
    echo         Check if exists: %PROJECT_DIR%
    pause
    exit /b 1
)
echo       OK - %CD%
echo.

:: Check virtual environment
echo [2/4] Checking virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo       Virtual environment not found, creating...
    python -m venv venv

    if errorlevel 1 (
        echo [ERROR] Cannot create virtual environment!
        echo         Make sure Python is installed.
        pause
        exit /b 1
    )
    echo       Virtual environment created
)
echo       OK - venv found
echo.

:: Activate virtual environment
echo [3/4] Activating virtual environment...
call venv\Scripts\activate

if errorlevel 1 (
    echo [ERROR] Cannot activate virtual environment!
    pause
    exit /b 1
)
echo       OK - environment activated
echo.

:: Check and install packages
echo [4/4] Checking Python packages...
pip list | find "anthropic" >nul 2>&1
if errorlevel 1 (
    echo       Installing required packages, please wait...
    echo.
    python -m pip install --upgrade pip
    pip install anthropic python-dotenv pyyaml
    echo.
    echo       Installation complete
) else (
    echo       OK - packages already installed
)
echo.

:: Check main script exists
if not exist "%SCRIPT_NAME%" (
    echo [ERROR] Main script not found: %SCRIPT_NAME%
    echo         Check if file exists in: %PROJECT_DIR%
    pause
    exit /b 1
)

:: Check .env file
if not exist ".env" (
    echo [WARNING] File .env not found!
    echo           Creating sample .env file...
    (
        echo # Claude Generator Configuration
        echo ANTHROPIC_API_KEY=sk-ant-api03-xxxxx-insert-your-key-xxxxx
        echo.
        echo # Model settings
        echo CLAUDE_MODEL=claude-opus-4-1-20250805
        echo CLAUDE_TEMPERATURE=0.3
        echo CLAUDE_MAX_TOKENS=8000
        echo.
        echo # Paths - adjust to your structure
        echo OUTPUT_PATH=D:/NightChronicles/B_core/outputs
        echo CLAUDE_OUTPUT=D:/NightChronicles/Claude_vystup/outputs
        echo.
        echo # Other settings
        echo MAX_ATTEMPTS=3
        echo WORD_TOLERANCE=3
        echo RATE_LIMIT_DELAY=1.0
    ) > .env

    echo.
    echo ========================================
    echo    IMPORTANT: SET YOUR API KEY!
    echo ========================================
    echo.
    echo File .env has been created
    echo Open it and insert your Anthropic API key
    echo.
    pause
    exit /b 0
)

:: Run generator
echo ========================================
echo        STARTING GENERATOR
echo ========================================
echo.

python %SCRIPT_NAME%

:: Check result
if errorlevel 1 (
    echo.
    echo ========================================
    echo         PROGRAM ENDED WITH ERROR
    echo ========================================
    echo.
    echo Possible causes:
    echo 1. API key not set in .env file
    echo 2. Wrong paths in .env
    echo 3. Missing input data - prompts
    echo 4. Internet connection problem
    echo.
    echo Check log files in:
    echo D:\NightChronicles\Claude_vystup\logs
) else (
    echo.
    echo ========================================
    echo       GENERATION COMPLETED SUCCESSFULLY
    echo ========================================
)

echo.
pause
