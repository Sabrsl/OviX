# Daily Collection Configuration

This document describes the configuration changes needed for the daily 500-article workflow.

## Required Changes to config.yaml

The following configuration changes are needed in `config/config.yaml` to enable the daily 500-article workflow:

### 1. Update Daily Limit (from 100 to 500)

```yaml
scheduler:
  daily_limit: 500  # Changed from 100 to 500
```

This change is already supported by the existing `TimingManager` class which loads this value from config.yaml.

### 2. Add Daily Collection Configuration (NEW)

Add a new section for daily article collection:

```yaml
daily_collection:
  enabled: true
  category: "Article à wikifier/Liste complète"
  max_articles: 500
  batch_size: 100
  exclude_published: true
  exclude_analyzed: true
```

**Note**: The DailyArticleCollector currently uses default values if these are not present in config.yaml. The defaults are:
- enabled: true
- category: "Article à wikifier/Liste complète"
- max_articles: 500
- batch_size: 100
- exclude_published: true
- exclude_analyzed: true

### 3. Optional: Update TimingManager to Load Daily Collection Config

Currently, the DailyArticleCollector uses hardcoded defaults. To make it fully configurable via config.yaml, you would need to update `src/wikipedia_maintenance/orchestrator/timing_manager.py` to load the daily_collection section and add the following attributes:

```python
self.daily_collection_category = config.get('daily_collection', {}).get('category', "Article à wikifier/Liste complète")
self.daily_collection_max_articles = config.get('daily_collection', {}).get('max_articles', 500)
self.daily_collection_batch_size = config.get('daily_collection', {}).get('batch_size', 100)
```

Then update the scheduler initialization in `scheduler.py` to use these values instead of hardcoded defaults.

## Summary of Changes

1. **daily_limit**: 100 → 500 (scheduler section)
2. **daily_collection**: New section with collection settings

## Verification

After making these changes, verify:
1. The scheduler respects the 500-article daily limit
2. Daily collection happens once per day (idempotent)
3. Articles are collected in batches of 100
4. The Article Scheduler API processes the collected articles automatically
