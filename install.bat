@echo off
REM Syns Operator Bot - Installation Script for Windows
REM This script automates the installation process

echo ==========================================
echo Syns Operator Bot - Installation
echo ==========================================
echo.

REM Check if Python is installed
echo 🔍 Checking Python version...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.10 or higher.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Found Python %PYTHON_VERSION%

REM Check if pip is installed
echo.
echo 🔍 Checking pip...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ pip is not installed. Please install pip.
    pause
    exit /b 1
)
echo ✅ pip is installed

REM Check if git is installed
echo.
echo 🔍 Checking git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ git is not installed. Please install git.
    echo Download from: https://git-scm.com/downloads
    pause
    exit /b 1
)
echo ✅ git is installed

REM Create virtual environment
echo.
echo 📦 Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo ✅ Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo ⬆️  Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo 📥 Installing Python dependencies...
pip install -r requirements.txt

REM Create necessary directories
echo.
echo 📁 Creating necessary directories...
if not exist logs mkdir logs
if not exist data mkdir data
if not exist config mkdir config

REM Copy example files if they don't exist
echo.
echo 📋 Setting up configuration files...
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo ✅ Created .env from .env.example
    ) else (
        echo ⚠️  .env.example not found, creating empty .env
        type nul > .env
    )
) else (
    echo ℹ️  .env already exists, skipping
)

if not exist user-config.py (
    if exist user-config.py.example (
        copy user-config.py.example user-config.py >nul
        echo ✅ Created user-config.py from user-config.py.example
    ) else (
        echo ⚠️  user-config.py.example not found, creating empty user-config.py
        type nul > user-config.py
    )
) else (
    echo ℹ️  user-config.py already exists, skipping
)

if not exist passwords.py (
    if exist passwords.py.example (
        copy passwords.py.example passwords.py >nul
        echo ✅ Created passwords.py from passwords.py.example
    ) else (
        echo ⚠️  passwords.py.example not found, creating empty passwords.py
        type nul > passwords.py
    )
) else (
    echo ℹ️  passwords.py already exists, skipping
)

REM Installation complete
echo.
echo ==========================================
echo ✅ Installation completed successfully!
echo ==========================================
echo.
echo Next steps:
echo 1. Edit .env file with your API keys and configuration
echo 2. Configure user-config.py for Pywikibot settings
echo 3. Configure passwords.py with Wikipedia credentials
echo 4. Activate the virtual environment: venv\Scripts\activate.bat
echo 5. Run the application: streamlit run app.py
echo.
echo For more information, see docs\INSTALLATION.md
pause
