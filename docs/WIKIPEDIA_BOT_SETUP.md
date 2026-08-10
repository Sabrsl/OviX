# Wikipedia Bot Account Setup Guide

This guide explains how to create and configure a Wikipedia bot account for use with the Wikipedia Maintenance Tool.

## Why Create a Bot Account?

A bot account is recommended for automated editing because:
- **Separation of concerns**: Keeps your personal edits separate from automated edits
- **Transparency**: Clearly identifies automated edits to other Wikipedia users
- **Accountability**: Bot accounts are subject to bot approval processes
- **Rate limiting**: Bot accounts have different rate limits than regular accounts

## Step 1: Create a Wikipedia Account

### 1.1 Register a New Account

1. Go to [https://www.wikipedia.org](https://www.wikipedia.org)
2. Click "Create account" in the top right corner
3. Choose the appropriate language (e.g., French Wikipedia: fr.wikipedia.org)
4. Fill in the registration form:
   - **Username**: Choose a username that clearly indicates it's a bot (e.g., "YourNameBot", "MaintenanceBot")
   - **Email**: Use a valid email address
   - **Password**: Use a strong, unique password
5. Complete the CAPTCHA
6. Confirm your email address

### 1.2 Account Requirements

- The account must be **at least 4 days old** before requesting bot status
- The account must have **at least 50 edits** before requesting bot status
- The account should be in **good standing** (no blocks or warnings)

## Step 2: Configure Pywikibot

### 2.1 Install Pywikibot

Pywikibot should already be installed via `requirements.txt`. Verify installation:

```bash
python -c "import pywikibot; print(pywikibot.__version__)"
```

### 2.2 Create `user-config.py`

Copy the example file and customize it:

```bash
cp user-config.py.example user-config.py
```

Edit `user-config.py` with your bot account details:

```python
# Your bot account username
usernames['wikipedia']['fr'] = 'YourBotUsername'

# Default language and family
mylang = 'fr'
family = 'wikipedia'
```

### 2.3 Create `passwords.py`

Copy the example file and customize it:

```bash
cp passwords.py.example passwords.py
```

Edit `passwords.py` with your credentials:

```python
WIKIPEDIA_USERNAME = "YourBotUsername"
WIKIPEDIA_PASSWORD = "YourBotPassword"
```

**⚠️ SECURITY WARNING**: Never commit `passwords.py` to version control. It is already in `.gitignore`.

## Step 3: Test Your Configuration

### 3.1 Test Connection

Run a simple test to verify your configuration:

```bash
python -c "
import pywikibot
site = pywikibot.Site('fr', 'wikipedia')
print(f'Connected as: {site.user()}')
print(f'Site: {site}')
"
```

If successful, you should see your bot username and site information.

### 3.2 Test Edit (Optional)

Before running the full tool, you can test a simple edit:

```bash
python -c "
import pywikibot
site = pywikibot.Site('fr', 'wikipedia')
page = pywikibot.Page(site, 'User talk:YourBotUsername')
page.text = page.text + '\n\nTest edit from pywikibot'
page.save('Test edit from pywikibot')
"
```

## Step 4: Request Bot Status (Optional but Recommended)

### 4.1 When to Request Bot Status

Bot status is required when:
- You plan to make **more than a few edits per day**
- Your edits are **fully automated** without human review
- You want to **edit at a faster rate** than regular users

### 4.2 Bot Approval Process

1. **Gain experience**: Make at least 50 manual edits with your bot account
2. **Document your bot**: Create a user page for your bot explaining its purpose
3. **Request approval**: Go to the appropriate bot approval page:
   - French Wikipedia: [Wikipédia:Demandes de statut de bot](https://fr.wikipedia.org/wiki/Wikip%C3%A9dia:Demandes_de_statut_de_bot)
   - English Wikipedia: [Wikipedia:Bot requests](https://en.wikipedia.org/wiki/Wikipedia:Bot_requests)
4. **Provide details**: Include:
   - Bot username
   - Purpose of the bot
   - Types of edits it will make
   - How often it will run
   - Who will maintain it
5. **Wait for approval**: The community will review and vote on your request

### 4.3 Bot Flags

Once approved, your bot will receive:
- **Bot flag**: Edits are marked as bot edits in recent changes
- **Reduced rate limiting**: Can edit faster than regular users
- **Exemption from some anti-vandalism tools**

## Step 5: Configure the Tool

### 5.1 Alternative: Environment Variables

Instead of using `passwords.py`, you can use environment variables:

```bash
export WIKIPEDIA_USERNAME="YourBotUsername"
export WIKIPEDIA_PASSWORD="YourBotPassword"
```

Or create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 5.2 Verify Tool Configuration

Start the application:

```bash
streamlit run app.py
```

In the sidebar:
1. Select your language (e.g., "fr")
2. Select your family (e.g., "wikipedia")
3. Click "Se connecter"
4. You should see a success message with your bot username

## Troubleshooting

### Connection Errors

**Error**: `No user-agent is set`
- **Solution**: Ensure `user-config.py` is properly configured

**Error**: `Login failed`
- **Solution**: Verify username and password in `passwords.py`

**Error**: `CAPTCHA required`
- **Solution**: Log in manually via web browser once to clear CAPTCHA

### Rate Limiting

**Error**: `You have exceeded your edit rate limit`
- **Solution**: 
  - Wait before making more edits
  - Request bot status for higher limits
  - Adjust rate limiting settings in `config/config.yaml`

### Permission Errors

**Error**: `Permission denied`
- **Solution**: 
  - Ensure your account is not blocked
  - Check if the page is protected
  - Verify you have the necessary user rights

## Best Practices

1. **Start small**: Begin with manual edits to understand Wikipedia's norms
2. **Test thoroughly**: Always test with dry-run mode first
3. **Communicate**: Use talk pages when making significant changes
4. **Monitor**: Watch your bot's edits and respond to feedback
5. **Document**: Keep clear documentation of your bot's purpose and behavior
6. **Respect limits**: Even with bot status, be respectful of Wikipedia's resources
7. **Be responsive**: Respond quickly to any concerns about your bot's edits

## Additional Resources

- [Pywikibot Documentation](https://www.mediawiki.org/wiki/Manual:Pywikibot)
- [Wikipedia Bot Policy](https://en.wikipedia.org/wiki/Wikipedia:Bot_policy)
- [Bot Approval Guidelines](https://en.wikipedia.org/wiki/Wikipedia:Bot_approvals)
- [French Wikipedia Bot Guidelines](https://fr.wikipedia.org/wiki/Wikip%C3%A9dia:Bot)

## Support

If you encounter issues:
1. Check the [Pywikibot documentation](https://www.mediawiki.org/wiki/Manual:Pywikibot)
2. Review the [troubleshooting section](#troubleshooting)
3. Ask for help on the relevant Wikipedia village pump
4. Contact the tool maintainer
