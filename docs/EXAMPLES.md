# Usage Examples

This document provides practical examples of using the Wikipedia Maintenance Tool.

## Example 1: Basic Category Maintenance

### Scenario
You want to fix common issues in articles from the "France" category.

### Steps

1. **Launch the application**
   ```bash
   streamlit run app.py
   ```

2. **Connect to Wikipedia**
   - Language: `fr`
   - Family: `wikipedia`
   - Click "Se connecter"

3. **Retrieve articles from category**
   - Select "Catégorie" in the sidebar
   - Enter category name: `France`
   - Set max articles: `50`
   - Uncheck "Inclure sous-catégories" (to limit scope)
   - Click "Récupérer"

4. **Process articles**
   - For each article:
     - Click "🔍 Analyser l'article"
     - Review detected issues
     - Select corrections to apply
     - Click "✅ Valider et publier" (or "⏭️ Ignorer et passer")

### Expected Results
- Articles with typos, double spaces, and formatting issues are corrected
- All changes are logged in the local database
- Edit summaries are automatically generated

## Example 2: Manual Article Review

### Scenario
You have a specific list of articles to review.

### Steps

1. **Create a text file** (`articles.txt`):
   ```
   Paris
   Lyon
   Marseille
   Toulouse
   Nice
   ```

2. **Launch and connect** (as in Example 1)

3. **Retrieve articles manually**
   - Select "Manuel" in the sidebar
   - Paste the article titles (one per line)
   - Click "Récupérer"

4. **Process each article** as in Example 1

### Alternative: Use File Retrieval

1. **Launch and connect**

2. **Use file retrieval**
   - Select "Fichier" in the sidebar
   - Enter path: `articles.txt`
   - Click "Récupérer"

## Example 3: User Contribution Review

### Scenario
Review and fix issues in articles recently edited by a specific user.

### Steps

1. **Launch and connect**

2. **Retrieve user contributions**
   - Select "Contributions" in the sidebar
   - Enter username: `ExampleUser`
   - Set max articles: `25`
   - Click "Récupérer"

3. **Process articles**
   - Analyze each article
   - Review changes made by the user
   - Fix any issues introduced

## Example 4: PetScan Query

### Scenario
Use a complex PetScan query to find articles needing maintenance.

### Steps

1. **Create PetScan query**
   - Go to https://petscan.wmflabs.org/
   - Configure your query (e.g., articles with few watchers)
   - Save the query
   - Note the PetScan ID (e.g., `12345678`)

2. **Launch and connect**

3. **Retrieve from PetScan**
   - Select "PetScan" in the sidebar
   - Enter PetScan ID: `12345678`
   - Click "Récupérer"

4. **Process articles** as usual

## Example 5: Dry-Run Testing

### Scenario
Test the tool on a category without making actual edits.

### Steps

1. **Launch and connect**

2. **Ensure dry-run mode is enabled**
   - Check "Mode test (dry-run)" in sidebar (should be checked by default)

3. **Retrieve and analyze articles**
   - Retrieve articles from any source
   - Analyze and review corrections
   - Click "✅ Valider et publier"

4. **Review results**
   - Check that no actual edits were made
   - Review the simulated results
   - Verify the tool's behavior

### Expected Results
- No actual edits are published to Wikipedia
- The tool simulates the entire process
- You can review what would be changed

## Example 6: Custom Configuration

### Scenario
Customize the tool for specific needs.

### Steps

1. **Edit configuration file** (`config/config.yaml`):
   ```yaml
   wikipedia:
     lang: fr
     family: wikipedia
   
   rate_limiting:
     min_edit_delay: 2.0  # Slower rate
     max_edits_per_minute: 5
   
   analysis:
     enabled_analyzers:
       - WhitespaceAnalyzer
       - TypographyAnalyzer
       # Disable other analyzers
   
   safety:
     dry_run_default: false  # Enable actual edits by default
   ```

2. **Restart the application**
   ```bash
   streamlit run app.py
   ```

3. **Use with new settings**

## Example 7: Programmatic Usage

### Scenario
Use the tool's modules programmatically in a Python script.

### Example Script

```python
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import pywikibot
from wikipedia_maintenance.retrievers import CategoryRetriever
from wikipedia_maintenance.analyzers import WhitespaceAnalyzer, TypographyAnalyzer
from wikipedia_maintenance.utils import DatabaseManager, Corrector, Publisher

# Connect to Wikipedia
site = pywikibot.Site('fr', 'wikipedia')

# Retrieve articles
retriever = CategoryRetriever(site)
articles = retriever.retrieve(category_name='France', max_articles=10)

# Initialize database
db = DatabaseManager()

# Process each article
for article in articles:
    print(f"Processing: {article.title}")
    
    # Get article content
    page = pywikibot.Page(site, article.title)
    content = page.get()
    article.content = content
    
    # Analyze
    analyzers = [WhitespaceAnalyzer(), TypographyAnalyzer()]
    all_issues = []
    for analyzer in analyzers:
        issues = analyzer.analyze(content)
        all_issues.extend(issues)
    
    if not all_issues:
        print(f"  No issues found")
        continue
    
    print(f"  Found {len(all_issues)} issues")
    
    # Generate corrections
    corrector = Corrector(content)
    corrected = corrector.apply_corrections(all_issues)
    
    # Show diff
    diff = corrector.get_diff()
    print(f"  Diff:\n{diff}")
    
    # Store in database
    article_id = db.add_article(article.title, article.page_id, 'category')
    for issue in all_issues:
        db.add_issue(article_id, issue.issue_type, issue.description,
                    issue.position, issue.original_text, issue.suggested_text)
    
    # Publish (with dry-run for safety)
    publisher = Publisher(site, dry_run=True)
    result = publisher.publish(article.title, corrected, 
                             "Maintenance: corrections automatiques")
    print(f"  Result: {result}")

# Close database
db.close()
```

### Running the script

```bash
python script.py
```

## Example 8: Batch Processing with Statistics

### Scenario
Process a batch of articles and generate statistics.

### Example Script

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import pywikibot
from wikipedia_maintenance.retrievers import CategoryRetriever
from wikipedia_maintenance.analyzers import WhitespaceAnalyzer
from wikipedia_maintenance.utils import DatabaseManager

# Connect
site = pywikibot.Site('fr', 'wikipedia')
db = DatabaseManager()

# Start session
session_id = db.start_session('category', 'Test batch processing')

# Retrieve and process
retriever = CategoryRetriever(site)
articles = retriever.retrieve(category_name='France', max_articles=20)

analyzed = 0
total_issues = 0

for article in articles:
    page = pywikibot.Page(site, article.title)
    if not page.exists():
        continue
    
    content = page.get()
    analyzer = WhitespaceAnalyzer()
    issues = analyzer.analyze(content)
    
    analyzed += 1
    total_issues += len(issues)
    
    # Store in database
    article_id = db.add_article(article.title, article.page_id, 'category')
    for issue in issues:
        db.add_issue(article_id, issue.issue_type, issue.description)

# End session with statistics
db.end_session(session_id, analyzed, 0, 0)

# Print statistics
stats = db.get_statistics()
print(f"Articles analyzed: {analyzed}")
print(f"Total issues found: {total_issues}")
print(f"Issues by type: {stats['issue_types']}")

db.close()
```

## Example 9: Handling Specific Issue Types

### Scenario
Focus on fixing only specific types of issues.

### Example Script

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import pywikibot
from wikipedia_maintenance.retrievers import ManualRetriever
from wikipedia_maintenance.analyzers import LinkAnalyzer, TemplateAnalyzer
from wikipedia_maintenance.utils import Publisher

# Connect
site = pywikibot.Site('fr', 'wikipedia')

# Define articles to check
titles = ["Article1", "Article2", "Article3"]

# Retrieve
retriever = ManualRetriever(site)
articles = retriever.retrieve(titles)

# Use only specific analyzers
analyzers = [
    LinkAnalyzer(),      # Only check links
    TemplateAnalyzer()   # Only check templates
]

publisher = Publisher(site, dry_run=True)

for article in articles:
    page = pywikibot.Page(site, article.title)
    content = page.get()
    
    all_issues = []
    for analyzer in analyzers:
        issues = analyzer.analyze(content)
        all_issues.extend(issues)
    
    if all_issues:
        print(f"{article.title}: {len(all_issues)} issues")
        for issue in all_issues:
            print(f"  - {issue.issue_type}: {issue.description}")
```

## Example 10: Error Handling and Logging

### Scenario
Implement robust error handling and logging.

### Example Script

```python
import sys
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import pywikibot
from wikipedia_maintenance.retrievers import CategoryRetriever
from wikipedia_maintenance.analyzers import WhitespaceAnalyzer
from wikipedia_maintenance.utils import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('maintenance.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

try:
    # Connect
    logger.info("Connecting to Wikipedia...")
    site = pywikibot.Site('fr', 'wikipedia')
    logger.info("Connected successfully")
    
    # Initialize database
    db = DatabaseManager()
    logger.info("Database initialized")
    
    # Retrieve articles
    logger.info("Retrieving articles...")
    retriever = CategoryRetriever(site)
    articles = retriever.retrieve(category_name='France', max_articles=5)
    logger.info(f"Retrieved {len(articles)} articles")
    
    # Process
    analyzer = WhitespaceAnalyzer()
    for article in articles:
        try:
            logger.info(f"Processing {article.title}...")
            page = pywikibot.Page(site, article.title)
            
            if not page.exists():
                logger.warning(f"Page {article.title} does not exist")
                continue
            
            content = page.get()
            issues = analyzer.analyze(content)
            
            logger.info(f"Found {len(issues)} issues in {article.title}")
            
            # Store in database
            article_id = db.add_article(article.title, article.page_id, 'category')
            for issue in issues:
                db.add_issue(article_id, issue.issue_type, issue.description)
                
        except Exception as e:
            logger.error(f"Error processing {article.title}: {e}")
            continue
    
    db.close()
    logger.info("Processing complete")
    
except Exception as e:
    logger.error(f"Fatal error: {e}")
    sys.exit(1)
```

## Tips and Best Practices

1. **Always start with dry-run mode** to understand the tool's behavior
2. **Process small batches** (10-20 articles) initially
3. **Review each correction** before publishing
4. **Use descriptive edit summaries** for transparency
5. **Monitor the database** to track your activities
6. **Check logs regularly** for errors or issues
7. **Test on non-controversial articles** first
8. **Communicate with the community** for significant changes
9. **Back up the database** regularly
10. **Keep the tool updated** with the latest dependencies

## Common Workflows

### Workflow 1: Category Cleanup
1. Retrieve from category
2. Analyze all articles
3. Review and approve corrections
4. Publish in batches

### Workflow 2: New Article Patrol
1. Retrieve from user contributions or recent changes
2. Analyze for common issues
3. Fix formatting and typos
4. Leave constructive edit summaries

### Workflow 3: Maintenance Project
1. Define project scope (specific issue type)
2. Use PetScan to find affected articles
3. Process systematically
4. Document results

### Workflow 4: Quality Assurance
1. Retrieve articles from a category
2. Analyze with all analyzers
3. Review high-severity issues
4. Fix critical problems only
