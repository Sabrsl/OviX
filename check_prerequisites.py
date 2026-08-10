#!/usr/bin/env python3
"""
Syns Operator Bot - Prerequisites Check Script
This script verifies that all necessary dependencies and configurations are in place.
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Tuple, List

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*50}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*50}{Colors.RESET}\n")

def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")

def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

def check_python_version() -> Tuple[bool, str]:
    """Check if Python 3.10+ is installed."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} is installed")
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    else:
        print_error(f"Python 3.10+ required. Current version: {version.major}.{version.minor}.{version.micro}")
        return False, f"Python {version.major}.{version.minor}.{version.micro}"

def check_pip() -> Tuple[bool, str]:
    """Check if pip is installed."""
    print("\nChecking pip...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print_success(f"pip is installed: {version}")
            return True, version
        else:
            print_error("pip is not installed")
            return False, "pip not found"
    except Exception as e:
        print_error(f"Error checking pip: {e}")
        return False, str(e)

def check_git() -> Tuple[bool, str]:
    """Check if git is installed."""
    print("\nChecking git...")
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print_success(f"git is installed: {version}")
            return True, version
        else:
            print_error("git is not installed")
            return False, "git not found"
    except Exception as e:
        print_error(f"Error checking git: {e}")
        return False, str(e)

def check_dependencies() -> List[Tuple[str, bool]]:
    """Check if required Python packages are installed."""
    print("\nChecking Python dependencies...")
    
    # Map package names to import names
    package_map = {
        "pywikibot": "pywikibot",
        "requests": "requests",
        "streamlit": "streamlit",
        "pyyaml": "yaml",
        "python-dotenv": "dotenv",
        "ratelimit": "ratelimit",
    }
    
    results = []
    for package, import_name in package_map.items():
        try:
            __import__(import_name)
            # Try to get version
            try:
                module = sys.modules[import_name]
                version = getattr(module, '__version__', 'unknown')
                print_success(f"{package} is installed (v{version})")
            except:
                print_success(f"{package} is installed")
            results.append((package, True))
        except ImportError:
            print_error(f"{package} is not installed")
            results.append((package, False))
        except Exception as e:
            print_error(f"Error checking {package}: {e}")
            results.append((package, False))
    
    return results

def check_directories() -> List[Tuple[str, bool]]:
    """Check if required directories exist."""
    print("\nChecking required directories...")
    required_dirs = ["logs", "data", "config"]
    
    results = []
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists() and dir_path.is_dir():
            print_success(f"Directory '{dir_name}' exists")
            results.append((dir_name, True))
        else:
            print_warning(f"Directory '{dir_name}' does not exist (will be created)")
            results.append((dir_name, False))
    
    return results

def check_config_files() -> List[Tuple[str, bool]]:
    """Check if configuration files exist."""
    print("\nChecking configuration files...")
    config_files = [
        ("config/config.yaml", True),  # Required
        (".env", False),  # Optional but recommended
        ("user-config.py", False),  # Optional
        ("passwords.py", False),  # Optional
    ]
    
    results = []
    for file_name, required in config_files:
        file_path = Path(file_name)
        if file_path.exists():
            print_success(f"File '{file_name}' exists")
            results.append((file_name, True))
        else:
            if required:
                print_error(f"Required file '{file_name}' is missing")
                results.append((file_name, False))
            else:
                print_warning(f"Optional file '{file_name}' is missing")
                results.append((file_name, False))
    
    return results

def check_env_variables() -> List[Tuple[str, bool]]:
    """Check if recommended environment variables are set."""
    print("\nChecking environment variables...")
    env_vars = [
        ("GEMINI_API_KEY", False),
        ("GEMINI_PROJECT_ID", False),
        ("OLLAMA_URL", False),
        ("TELEGRAM_BOT_TOKEN", False),
    ]
    
    results = []
    for var_name, required in env_vars:
        value = os.environ.get(var_name)
        if value:
            print_success(f"Environment variable '{var_name}' is set")
            results.append((var_name, True))
        else:
            if required:
                print_error(f"Required environment variable '{var_name}' is not set")
                results.append((var_name, False))
            else:
                print_warning(f"Optional environment variable '{var_name}' is not set")
                results.append((var_name, False))
    
    return results

def main():
    """Run all prerequisite checks."""
    print_header("Syns Operator Bot - Prerequisites Check")
    
    all_passed = True
    
    # Check Python version
    python_ok, python_version = check_python_version()
    all_passed = all_passed and python_ok
    
    # Check pip
    pip_ok, pip_info = check_pip()
    all_passed = all_passed and pip_ok
    
    # Check git
    git_ok, git_info = check_git()
    all_passed = all_passed and git_ok
    
    # Check dependencies
    dep_results = check_dependencies()
    dep_ok = all(result[1] for result in dep_results)
    all_passed = all_passed and dep_ok
    
    # Check directories
    dir_results = check_directories()
    
    # Check config files
    config_results = check_config_files()
    config_ok = all(result[1] for result in config_results if result[0] == "config/config.yaml")
    all_passed = all_passed and config_ok
    
    # Check environment variables
    env_results = check_env_variables()
    
    # Summary
    print_header("Summary")
    
    if all_passed:
        print_success("All critical prerequisites are met!")
        print_info("You can proceed with running the application.")
        print("\nTo start the application:")
        print("  1. Activate virtual environment (if using one)")
        print("  2. Run: streamlit run app.py")
        return 0
    else:
        print_error("Some prerequisites are missing or incorrect.")
        print("\nPlease fix the issues above before running the application.")
        print("\nTo install dependencies:")
        print("  pip install -r requirements.txt")
        print("\nTo create missing directories:")
        print("  mkdir logs data config")
        print("\nFor more information, see docs/INSTALLATION.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
