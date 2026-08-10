# User Guide

## Overview

Wikipedia Maintenance Tool is a semi-automated assistance tool for Wikipedia maintenance. It helps you identify and fix common issues in Wikipedia articles while maintaining human control over all modifications.

## Key Features

- **Multiple Article Sources**: Retrieve articles from categories, manual lists, user contributions, PetScan, or text files
- **Automatic Analysis**: Detect common issues like bare links, double spaces, typos, obsolete templates, and more
- **Correction Proposals**: View suggested corrections with before/after diffs
- **Human Validation**: All modifications require explicit approval before publication
- **Safety Features**: Dry-run mode, rate limiting, and edit conflict handling
- **Local Logging**: Track all actions in a local database

## Getting Started

### 1. Launch the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

### 2. Connect to Wikipedia

In the sidebar:
1. Select the language (e.g., "fr" for French Wikipedia)
2. Select the site family (usually "wikipedia")
3. Click "Se connecter" to connect

### 3. Retrieve Articles

Choose a source type from the sidebar:

#### Category
- Enter the category name (with or without "Category:" prefix)
- Set the maximum number of articles to retrieve
- Optionally include subcategories
- Click "Récupérer"

#### Manual
- Enter article titles (one per line)
- Click "Récupérer"

#### User Contributions
- Enter a Wikipedia username
- Set the maximum number of articles
- Click "Récupérer"

#### PetScan
- Enter a PetScan query ID
- Click "Récupérer"

#### File
- Enter the path to a text file containing article titles (one per line)
- Click "Récupérer"

### 4. Analyze Articles

Once articles are loaded:
1. Navigate between articles using the "Précédent" and "Suivant" buttons
2. Click "🔍 Analyser l'article" to analyze the current article
3. Review detected issues in the main area

### 5. Review and Apply Corrections

For each detected issue:
- Expand the issue to see details
- View the original text and suggested correction
- Check/uncheck "Appliquer cette correction" to select/deselect
- Review the diff in the "Diff avant/après" section

### 6. Publish or Skip

Choose an action:

- **✅ Valider et publier**: Apply selected corrections and publish to Wikipedia
- **⏭️ Ignorer et passer**: Skip this article and move to the next
- **✏️ Modifier manuellement**: Manually edit the content (coming soon)
- **🗑️ Réinitialiser**: Reset the analysis and start over

## Issue Types

The tool detects the following types of issues:

### Link Issues
- **bare_external_link**: URLs not properly formatted with brackets
- **suspicious_internal_link**: Internal links with suspicious characters

### Whitespace Issues
- **double_space**: Unnecessary double spaces
- **space_before_punctuation**: Spaces before punctuation marks
- **trailing_whitespace**: Spaces at end of lines

### Typography Issues
- **typo**: Common typos and misspellings
- **missing_accent**: Potentially missing accents

### Template Issues
- **obsolete_template**: Deprecated or obsolete templates
- **empty_parameter**: Empty parameters in templates

### Category Issues
- **duplicate_category**: Duplicate category declarations

### HTML Issues
- **unnecessary_html**: HTML tags that should use wikicode
- **html_comment**: HTML comments (for manual review)

## Safety Features

### Dry-Run Mode
By default, the tool runs in dry-run mode. In this mode:
- No actual edits are published to Wikipedia
- You can review what would be changed
- Useful for testing and learning

To disable dry-run mode:
1. Uncheck "Mode test (dry-run)" in the sidebar
2. Be careful - actual edits will be published!

### Rate Limiting
The tool automatically limits edit frequency to respect Wikipedia's API limits:
- Minimum delay between edits: 1 second (configurable)
- Maximum edits per minute: 10 (configurable)

### Edit Conflicts
If an article is modified by someone else while you're working on it:
- The tool detects the conflict
- Publication is aborted
- You can re-analyze the article to see the current state

## Configuration

Edit `config/config.yaml` to customize:

- Wikipedia connection settings
- Rate limiting parameters
- Enabled analyzers
- Severity thresholds
- UI preferences
- Safety settings

See the configuration file for detailed options.

## Database

The tool maintains a local SQLite database (`data/wikipedia_maintenance.db`) with:
- Article information
- Detected issues
- User actions (approve, ignore, modify)
- Session statistics

You can view statistics in the database to track your maintenance activities.

## Best Practices

1. **Start with Dry-Run**: Always test with dry-run mode enabled first
2. **Review Carefully**: Carefully review each correction before publishing
3. **Use Descriptive Edit Summaries**: The tool generates automatic summaries, but you can customize them
4. **Work in Batches**: Process articles in manageable batches (default max: 50)
5. **Check for False Positives**: Some detections may be false positives - use your judgment
6. **Follow Wikipedia Guidelines**: Always adhere to Wikipedia's policies and guidelines
7. **Communicate**: Use talk pages when making significant changes

## Troubleshooting

### Connection Issues
- Verify your Pywikibot configuration (see WIKIPEDIA_CONNECTION.md)
- Check your internet connection
- Ensure you have valid Wikipedia credentials

### Analysis Errors
- Some articles may have complex structures that cause analysis errors
- Try re-analyzing the article
- Report persistent issues to the maintainer

### Publication Failures
- Check if the article still exists
- Verify you're not in dry-run mode
- Check for edit conflicts
- Review the error message for specific details

## Keyboard Shortcuts

Currently, the tool uses mouse interaction. Keyboard shortcuts may be added in future versions.

## Support

For issues, questions, or suggestions:
- Check the documentation in the `docs/` directory
- Review the configuration options
- Contact the maintainer
