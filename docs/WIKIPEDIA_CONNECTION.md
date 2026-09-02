# Wikipedia Connection Instructions

## Overview

This tool uses Pywikibot to connect to Wikipedia. Pywikibot requires proper configuration to authenticate and interact with Wikipedia's API.

## Prerequisites

- A Wikipedia account (the account you want to use for edits)
- Your Wikipedia username and password (or bot password)
- Basic understanding of Pywikibot configuration

## Step 1: Install Pywikibot

Pywikibot is included in the requirements.txt, but you can also install it separately:

```bash
pip install pywikibot
```

## Step 2: Create user-config.py

Pywikibot requires a configuration file named `user-config.py`. This file should be placed in one of the following locations (Pywikibot searches in this order):

1. The current working directory
2. Your user's home directory
3. The Pywikibot configuration directory

### Windows
- `C:\Users\<YourUsername>\user-config.py`
- Or in the project directory: `user-config.py`

### Linux/macOS
- `~/.pywikibot/user-config.py`
- Or in the project directory: `user-config.py`

## Step 3: Configure user-config.py

Create the `user-config.py` file with the following content:

```python
# Wikipedia Maintenance Tool Configuration

# Your Wikipedia username
mylang = 'fr'
family = 'wikipedia'
usernames['wikipedia']['fr'] = 'YourWikipediaUsername'

# Optional: Set a custom user agent
user_agent_description = 'WikipediaMaintenanceTool/1.0'
```

Replace `YourWikipediaUsername` with your actual Wikipedia username.

## Step 4: Authentication Methods

Pywikibot supports multiple authentication methods:

### Method 1: Bot Password (Recommended)

1. Log in to Wikipedia
2. Go to Special:BotPasswords (https://fr.wikipedia.org/wiki/Special:BotPasswords)
3. Create a new bot password with appropriate permissions:
   - Read permissions
   - Edit permissions
   - Patrol permissions (if needed)
4. Copy the bot password (format: `Username@BotPasswordName`)
5. Store it securely

Pywikibot will prompt for the bot password on first use, or you can configure it in `user-config.py`:

```python
# Add to user-config.py (optional, not recommended for security)
password = 'YourBotPassword'
```

**Security Note**: It's better to let Pywikibot prompt for the password rather than storing it in plain text.

### Method 2: Standard Password

You can use your regular Wikipedia password, but this is less secure:

```python
# Add to user-config.py (not recommended)
password = 'YourWikipediaPassword'
```

### Method 3: OAuth (Advanced)

For enhanced security, you can use OAuth authentication. This requires additional setup:

1. Register an OAuth consumer on Wikipedia
2. Configure Pywikibot to use OAuth
3. Store OAuth tokens securely

See [Pywikibot OAuth documentation](https://doc.wikimedia.org/pywikibot/master/api_ref/oauth.html) for details.

## Step 5: Test the Connection

Test your Pywikibot configuration:

```python
import pywikibot

site = pywikibot.Site('fr', 'wikipedia')
print(site)
```

If successful, this will print information about the French Wikipedia site.

## Step 6: Configure for Different Wikipedia Projects

To connect to different Wikipedia projects, modify the configuration:

```python
# English Wikipedia
mylang = 'en'
family = 'wikipedia'
usernames['wikipedia']['en'] = 'YourEnglishUsername'

# German Wikipedia
mylang = 'de'
family = 'wikipedia'
usernames['wikipedia']['de'] = 'YourGermanUsername'

# Wiktionary
mylang = 'fr'
family = 'wiktionary'
usernames['wiktionary']['fr'] = 'YourWiktionaryUsername'
```

## Step 7: Verify Permissions

Ensure your Wikipedia account has the necessary permissions:
- Autoconfirmed status (for most edits)
- Bot flag (if running as a bot)
- Appropriate user rights for your intended tasks

## Troubleshooting

### "No user-config.py found" Error

**Solution**: Ensure `user-config.py` exists in one of the expected locations. Check:
- Current directory
- Home directory
- `~/.pywikibot/` directory

### "Authentication Failed" Error

**Possible causes**:
- Incorrect username or password
- Account blocked or locked
- Bot password expired or revoked
- Network connectivity issues

**Solutions**:
- Verify your credentials
- Check if your account is in good standing
- Generate a new bot password
- Check your internet connection

### "Permission Denied" Error

**Possible causes**:
- Insufficient user rights
- Page protected
- Edit restrictions

**Solutions**:
- Verify your account permissions
- Check page protection status
- Use an account with appropriate rights

### Rate Limiting Issues

**Possible causes**:
- Too many requests in short time
- API rate limits exceeded

**Solutions**:
- Wait before retrying
- Adjust rate limiting settings in `config/config.yaml`
- Use bot account with higher rate limits

## Security Best Practices

1. **Never commit credentials to version control**
   - Add `user-config.py` to `.gitignore`
   - Never include passwords in code

2. **Use Bot Passwords**
   - Bot passwords are more secure than regular passwords
   - Can be revoked without affecting your main account
   - Have limited permissions

3. **Limit Permissions**
   - Only grant necessary permissions to bot passwords
   - Review permissions regularly

4. **Monitor Account Activity**
   - Regularly check your account's contribution history
   - Review bot password usage

5. **Use Environment Variables (Optional)**
   - Store sensitive credentials in environment variables
   - Access them in Python using `os.environ`

## Example user-config.py

```python
# Wikipedia Maintenance Tool Configuration
# Place this file in your home directory or project root

# Default language and family
mylang = 'fr'
family = 'wikipedia'

# Usernames for different projects
usernames['wikipedia']['fr'] = 'YourWikipediaUsername'
usernames['wikipedia']['en'] = 'YourEnglishUsername'

# Optional: Set a custom user agent
user_agent_description = 'WikipediaMaintenanceTool/1.0 (https://github.com/Sabrsl/OviX)'

# Optional: Disable console logging (for cleaner output)
console_encoding = 'utf-8'
```

## Additional Resources

- [Pywikibot Documentation](https://doc.wikimedia.org/pywikibot/)
- [Pywikibot Configuration](https://www.mediawiki.org/wiki/Manual:Pywikibot/Configuration)
- [Wikipedia Bot Policy](https://en.wikipedia.org/wiki/Wikipedia:Bot_policy)
- [Wikipedia:Bot passwords](https://en.wikipedia.org/wiki/Wikipedia:Bot_passwords)

## Support

If you encounter connection issues:
1. Verify your Pywikibot installation
2. Check your `user-config.py` syntax
3. Test with a simple Python script
4. Check the Pywikibot documentation
5. Review Wikipedia's API status
