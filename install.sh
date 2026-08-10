#!/bin/bash

# Syns Operator Bot - Installation Script for Linux/macOS
# This script automates the installation process

set -e

echo "=========================================="
echo "Syns Operator Bot - Installation"
echo "=========================================="
echo ""

# Check if Python 3.10+ is installed
echo "🔍 Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Found Python $PYTHON_VERSION"

# Check Python version is >= 3.10
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo "❌ Python 3.10 or higher is required. Current version: $PYTHON_VERSION"
    exit 1
fi

# Check if pip is installed
echo ""
echo "🔍 Checking pip..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3."
    exit 1
fi
echo "✅ pip3 is installed"

# Check if git is installed
echo ""
echo "🔍 Checking git..."
if ! command -v git &> /dev/null; then
    echo "❌ git is not installed. Please install git."
    exit 1
fi
echo "✅ git is installed"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo ""
echo "📁 Creating necessary directories..."
mkdir -p logs data config

# Copy example files if they don't exist
echo ""
echo "📋 Setting up configuration files..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env from .env.example"
    else
        echo "⚠️  .env.example not found, creating empty .env"
        touch .env
    fi
else
    echo "ℹ️  .env already exists, skipping"
fi

if [ ! -f user-config.py ]; then
    if [ -f user-config.py.example ]; then
        cp user-config.py.example user-config.py
        echo "✅ Created user-config.py from user-config.py.example"
    else
        echo "⚠️  user-config.py.example not found, creating empty user-config.py"
        touch user-config.py
    fi
else
    echo "ℹ️  user-config.py already exists, skipping"
fi

if [ ! -f passwords.py ]; then
    if [ -f passwords.py.example ]; then
        cp passwords.py.example passwords.py
        echo "✅ Created passwords.py from passwords.py.example"
    else
        echo "⚠️  passwords.py.example not found, creating empty passwords.py"
        touch passwords.py
    fi
else
    echo "ℹ️  passwords.py already exists, skipping"
fi

# Installation complete
echo ""
echo "=========================================="
echo "✅ Installation completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys and configuration"
echo "2. Configure user-config.py for Pywikibot settings"
echo "3. Configure passwords.py with Wikipedia credentials"
echo "4. Activate the virtual environment: source venv/bin/activate"
echo "5. Run the application: streamlit run app.py"
echo ""
echo "For more information, see docs/INSTALLATION.md"
