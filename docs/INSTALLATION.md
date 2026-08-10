# Installation Guide

## Prerequisites

- Python 3.12 or higher
- pip (Python package manager)
- Git (optional, for cloning the repository)

## Installation Steps

### 1. Clone or Download the Repository

```bash
git clone <repository-url>
cd synsoperatorbot
```

Or download and extract the ZIP file.

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- pywikibot (Wikipedia API interaction)
- streamlit (Web interface)
- streamlit-option-menu (Navigation menu)
- python-dateutil (Date utilities)
- pytz (Timezone support)
- pyyaml (Configuration management)
- python-dotenv (Environment variables)
- ratelimit (Rate limiting)

### 4. Configure Pywikibot

Pywikibot requires configuration to connect to Wikipedia. See [WIKIPEDIA_CONNECTION.md](WIKIPEDIA_CONNECTION.md) for detailed instructions.

### 5. Configure Secrets and API Keys

The tool requires several secrets and API keys to function properly. You can configure them in multiple ways:

#### Method 1: Using Configuration Files (Recommended)

1. **Wikipedia Credentials**:
   ```bash
   cp passwords.py.example passwords.py
   cp user-config.py.example user-config.py
   ```
   Edit these files with your Wikipedia bot credentials. See [WIKIPEDIA_BOT_SETUP.md](WIKIPEDIA_BOT_SETUP.md) for detailed instructions.

2. **Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your API keys and configuration:
   - `GEMINI_API_KEY`: Google Gemini API key (for AI mode)
   - `GEMINI_PROJECT_ID`: Google Cloud project ID
   - `TELEGRAM_BOT_TOKEN`: Telegram bot token (optional)
   - `TELEGRAM_ADMIN_IDS`: Telegram admin IDs (optional)

   See [GEMINI_SETUP.md](GEMINI_SETUP.md) for instructions on obtaining Gemini API keys.

#### Method 2: Using UI Configuration

You can also configure secrets directly in the application UI:

1. Start the application: `streamlit run app.py`
2. In the sidebar, expand "🔑 Configuration des Secrets"
3. Enter your API keys and credentials
4. Values are stored in your browser session

**Note**: For permanent configuration, use Method 1 (configuration files).

#### Required Configuration

- **Wikipedia credentials**: Required for all operations
- **Gemini API key**: Required for AI-powered analysis mode
- **Telegram credentials**: Optional, for remote bot control

See the following guides for detailed setup:
- [WIKIPEDIA_BOT_SETUP.md](WIKIPEDIA_BOT_SETUP.md) - Wikipedia bot account setup
- [GEMINI_SETUP.md](GEMINI_SETUP.md) - Google Gemini API setup

### 6. Create Required Directories

The following directories will be created automatically on first run:
- `data/` - Database storage
- `logs/` - Log files
- `config/` - Configuration files

### 7. Verify Installation

Run the application to verify installation:

```bash
streamlit run app.py
```

The application should open in your browser at `http://localhost:8501`

## Troubleshooting

### Pywikibot Configuration Issues

If you encounter Pywikibot configuration errors:
1. Ensure you've created the `user-config.py` file
2. Check that the file is in the correct location
3. Verify your Wikipedia credentials

See [WIKIPEDIA_CONNECTION.md](WIKIPEDIA_CONNECTION.md) for detailed troubleshooting.

### Dependency Conflicts

If you encounter dependency conflicts:
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Port Already in Use

If port 8501 is already in use:
```bash
streamlit run app.py --server.port 8502
```

### Database Permissions

Ensure you have write permissions for the `data/` directory. On Linux/macOS:
```bash
chmod +w data/
```

## Development Installation

For development, you may want to install additional tools:

```bash
pip install pytest pytest-cov black flake8
```

## Uninstallation

To uninstall the application:

1. Deactivate the virtual environment:
```bash
deactivate
```

2. Delete the virtual environment directory:
```bash
# On Windows:
rmdir /s venv

# On Linux/macOS:
rm -rf venv
```

3. Optionally delete the project directory and data files:
```bash
rm -rf synsoperatorbot
```

Note: This will delete your database and logs. Back up important data before deletion.
