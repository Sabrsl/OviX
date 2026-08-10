# Google Gemini API Setup Guide

This guide explains how to set up Google Gemini API for AI-powered article analysis in the Wikipedia Maintenance Tool.

## What is Google Gemini?

Google Gemini (formerly Google Bard) is Google's AI model that can be used for text analysis, correction, and generation. This tool uses Gemini for intelligent article correction and maintenance.

## Prerequisites

- A Google account
- A Google Cloud project
- A credit card or payment method (for billing, though free tier is available)

## Step 1: Create a Google Cloud Project

### 1.1 Go to Google Cloud Console

1. Visit [https://console.cloud.google.com](https://console.cloud.google.com)
2. Sign in with your Google account
3. If prompted, accept the Terms of Service

### 1.2 Create a New Project

1. In the top navigation bar, click the project selector dropdown
2. Click "New Project"
3. Enter a project name (e.g., "wikipedia-maintenance-tool")
4. Click "Create"
5. Wait for the project to be created (usually a few seconds)
6. Select your new project from the dropdown

## Step 2: Enable Gemini API

### 2.1 Enable the API

1. In the Google Cloud Console, go to the **APIs & Services** section
2. Click **Library** in the left sidebar
3. Search for "Generative Language API" or "Gemini API"
4. Click on the result
5. Click the **Enable** button
6. Wait for the API to be enabled

### 2.2 Verify API is Enabled

1. Go to **APIs & Services** → **Enabled APIs & services**
2. You should see "Generative Language API" in the list

## Step 3: Set Up Billing

### 3.1 Billing Setup

Google Cloud requires billing setup, but offers a free tier:

1. Go to **Billing** in the left sidebar
2. Click **Link a billing account**
3. Create a new billing account or select an existing one
4. Follow the prompts to add a payment method
5. **Free tier**: Google provides a free tier with generous limits for testing

### 3.2 Free Tier Limits

As of 2024, the free tier includes:
- **60 requests per minute** for Gemini Flash models
- **1,500 requests per day** for Gemini Flash models
- Generous token limits for text generation

Check the [Google AI Pricing](https://ai.google.dev/pricing) page for current limits.

## Step 4: Create API Key

### 4.1 Create Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **API Key**
3. A dialog will appear with your new API key
4. **Copy this key immediately** - you won't see it again!

### 4.2 Restrict API Key (Recommended)

For security, restrict your API key:

1. Click the API key you just created
2. Under **Application restrictions**, choose one:
   - **None**: Allows any application (not recommended for production)
   - **IP addresses**: Restrict to specific IP addresses
   - **HTTP referrers**: Restrict to specific websites
   - **Android apps**: Restrict to specific Android apps
   - **iOS apps**: Restrict to specific iOS apps
3. Under **API restrictions**, choose:
   - **Restrict key**: Select only "Generative Language API"
4. Click **Save**

## Step 5: Get Your Project ID

### 5.1 Find Project ID

1. In the Google Cloud Console, your project ID is displayed in the project selector dropdown
2. Alternatively, go to **IAM & Admin** → **Settings**
3. Your **Project ID** is listed there

### 5.2 Note the Project ID

Copy your project ID - you'll need it for configuration:
- Example: `804175778135` (this is a numeric ID)
- Or: `wikipedia-maintenance-tool` (this is a custom ID)

## Step 6: Configure the Tool

### 6.1 Method 1: Environment Variables

Set the environment variables:

```bash
export GEMINI_API_KEY="your_api_key_here"
export GEMINI_PROJECT_ID="your_project_id_here"
export GEMINI_MODEL="gemini-flash-lite-latest"
export GEMINI_LIMIT=10800
```

### 6.2 Method 2: .env File

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_PROJECT_ID=your_project_id_here
GEMINI_MODEL=gemini-flash-lite-latest
GEMINI_LIMIT=10800
```

### 6.3 Method 3: config.yaml

Edit `config/config.yaml`:

```yaml
ai:
  gemini:
    project_id: "your_project_id_here"
    model: "gemini-flash-lite-latest"
    limit: 10800
```

**Note**: You still need to set `GEMINI_API_KEY` via environment variable or UI.

### 6.4 Method 4: UI Configuration

1. Start the application: `streamlit run app.py`
2. In the sidebar, expand "🔑 Configuration des Secrets"
3. Enter your API key and project ID
4. The values will be stored in your browser session

## Step 7: Test Your Configuration

### 7.1 Test API Connection

Start the application and enable AI mode:

1. In the sidebar, expand "🤖 Mode IA"
2. Click "Activer le mode IA"
3. If successful, you'll see: "✅ Client Gemini initialisé automatiquement"
4. If failed, check the error message

### 7.2 Test Article Analysis

1. Connect to Wikipedia
2. Retrieve an article
3. Click "🔍 Analyser l'article" with AI mode enabled
4. Review the AI-generated corrections

## Available Models

### Gemini Flash Models (Fast, Cost-Effective)

- **gemini-flash-lite-latest**: Fastest, good for simple corrections
- **gemini-flash-1.5**: Balanced speed and quality
- **gemini-flash-2.0**: Latest flash model

### Gemini Pro Models (Higher Quality)

- **gemini-pro-latest**: Higher quality, slower
- **gemini-pro-1.5**: Balanced quality and speed
- **gemini-pro-vision**: For multimodal (image + text)

### Recommended Model

For Wikipedia maintenance, **gemini-flash-lite-latest** is recommended because:
- Fast response times
- Cost-effective
- Sufficient quality for text corrections
- Lower token usage

## Character Limits

The `GEMINI_LIMIT` parameter controls the maximum character limit for AI analysis:

- **10800 characters**: Default, good for most articles
- **5000 characters**: Faster processing, for shorter articles
- **30000 characters**: For very long articles (may hit rate limits)

Adjust based on your needs and rate limits.

## Troubleshooting

### API Key Errors

**Error**: `API key not valid`
- **Solution**: 
  - Verify the API key is correct
  - Check that the API key is not restricted (or properly restricted)
  - Ensure the Generative Language API is enabled

**Error**: `API key expired`
- **Solution**: Create a new API key

### Project ID Errors

**Error**: `Project not found`
- **Solution**: 
  - Verify the project ID is correct
  - Ensure you're using the correct Google Cloud project
  - Check that the project is not deleted

### Rate Limit Errors

**Error**: `Quota exceeded`
- **Solution**: 
  - Wait before making more requests
  - Upgrade to a paid plan for higher limits
  - Reduce the character limit to process smaller chunks
  - Use a different model with lower token usage

### Billing Errors

**Error**: `Billing account not configured`
- **Solution**: 
  - Set up billing in Google Cloud Console
  - Even with free tier, billing setup is required

### Connection Errors

**Error**: `Could not connect to Gemini API`
- **Solution**: 
  - Check your internet connection
  - Verify the API endpoint is accessible
  - Check if Google Cloud services are down

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for sensitive data
3. **Restrict API keys** to specific applications/IPs
4. **Rotate API keys** regularly
5. **Monitor usage** in Google Cloud Console
6. **Set up alerts** for unusual activity
7. **Use separate projects** for development and production

## Cost Optimization

### Free Tier Usage

To stay within free tier limits:
- Use **gemini-flash-lite** models
- Set reasonable **character limits**
- Process articles in batches
- Monitor usage in Google Cloud Console

### Monitoring Usage

1. Go to **APIs & Services** → **Dashboard**
2. View request counts and quota usage
3. Set up budget alerts

### Reducing Costs

- Use **Ollama** (local AI) as an alternative
- Process only articles that need AI analysis
- Increase the character limit threshold
- Use regex analyzers for simple corrections

## Alternative: Ollama (Local AI)

If you prefer not to use Google Gemini, you can use Ollama:

1. Install Ollama from [https://ollama.ai](https://ollama.ai)
2. Download a model: `ollama pull mistral:instruct`
3. Configure in `config/config.yaml`:
   ```yaml
   ai:
     ollama:
       url: "http://localhost:11434"
       model: "mistral:instruct"
       fallback: "llama3:instruct"
   ```
4. Select Ollama as the AI provider in the tool

## Additional Resources

- [Google AI Documentation](https://ai.google.dev/docs)
- [Gemini API Reference](https://ai.google.dev/api)
- [Google Cloud Console](https://console.cloud.google.com)
- [Google AI Pricing](https://ai.google.dev/pricing)
- [Ollama Documentation](https://ollama.ai/docs)

## Support

If you encounter issues:
1. Check the [Google AI Documentation](https://ai.google.dev/docs)
2. Review the [troubleshooting section](#troubleshooting)
3. Check the [Google Cloud Status Dashboard](https://status.cloud.google.com)
4. Contact the tool maintainer
