# OVIX Statistics Architecture

## Overview

This module provides a centralized, single-source-of-truth architecture for all statistics in the OVIX application. The database is the only source of truth for persistent data, and this module provides a clean, maintainable interface for accessing and aggregating statistics.

## Architecture

```
Database (SQLite)
    ↓
StatsRepository (database access layer)
    ↓
StatsService (business logic & aggregations)
    ↓
API Endpoints (/api/stats/v2/*)
    ↓
Frontend Components
```

## Components

### 1. StatsRepository (`repository.py`)
**Responsibility**: Database access only

- All SQL queries for statistics are centralized here
- No business logic
- Direct database operations only
- Methods:
  - `get_article_stats()` - Article counts by status
  - `get_analysis_stats()` - Analysis statistics
  - `get_publication_stats()` - Publication statistics with time-based counts
  - `get_database_stats()` - Database content statistics
  - `get_issues_by_severity()` - Issues grouped by severity
  - `get_all_stats()` - All statistics in one call

### 2. StatsService (`service.py`)
**Responsibility**: Business logic and aggregations

- Uses StatsRepository for data access
- Applies business rules
- Provides standardized data contracts
- Methods:
  - `get_article_stats()` - Returns ArticleStats object
  - `get_analysis_stats()` - Returns AnalysisStats object
  - `get_publication_stats()` - Returns PublicationStats object
  - `get_database_stats()` - Returns DatabaseStats object
  - `get_system_stats()` - Returns complete SystemStats object
  - `get_stats_response()` - Returns StatsResponse for API
  - `get_legacy_format()` - Returns legacy format for backward compatibility

### 3. Schemas (`schemas.py`)
**Responsibility**: Data contracts

- Pydantic models for type safety
- Standardized data structures
- Documentation via field descriptions
- Models:
  - `ArticleStats` - Article statistics
  - `AnalysisStats` - Analysis statistics
  - `PublicationStats` - Publication statistics
  - `DatabaseStats` - Database statistics
  - `SystemStats` - Complete system statistics
  - `StatsResponse` - Standard API response
  - `ComparisonResult` - Comparison between old and new stats

## API Endpoints

### New V2 Endpoints (Recommended)

- `GET /api/stats/v2/system` - Complete system statistics
- `GET /api/stats/v2/articles` - Article statistics
- `GET /api/stats/v2/analysis` - Analysis statistics
- `GET /api/stats/v2/publication` - Publication statistics
- `GET /api/stats/v2/database` - Database statistics
- `GET /api/stats/v2/legacy` - Legacy format for backward compatibility

### Comparison Endpoints

- `GET /api/stats/compare` - Compare old vs new statistics
- `GET /api/stats/compare/summary` - Summary of comparison

## Migration Guide

### Phase 1: Validation Current
- Old endpoints still work (`/api/history/statistics`, `/api/system/status`)
- New V2 endpoints available for testing
- Use `/api/stats/compare` to validate consistency

### Phase 2: Frontend Migration
1. Update Dashboard to use `/api/stats/v2/legacy` (drop-in replacement)
2. Update other components to use specific V2 endpoints
3. Test thoroughly
4. Monitor `/api/stats/compare` for discrepancies

### Phase 3: Deprecation
1. Add deprecation warnings to old endpoints
2. Monitor usage of old endpoints
3. Plan removal timeline

### Phase 4: Cleanup
1. Remove old endpoints
2. Remove fallback logic from old code
3. Remove JSON trackers (analyzed_articles.json, published_articles.json)
4. Clean up unused code

## Testing

Run unit tests:
```bash
python -m backend.stats.test_stats
```

Test API endpoints:
```bash
# Test V2 system stats
curl http://localhost:8000/api/stats/v2/system

# Test comparison
curl http://localhost:8000/api/stats/compare

# Test legacy format
curl http://localhost:8000/api/stats/v2/legacy
```

## Benefits

1. **Single Source of Truth**: Database is the only source of truth
2. **No Duplication**: Eliminates multiple counting mechanisms
3. **Type Safety**: Pydantic schemas ensure data consistency
4. **Maintainability**: Centralized logic, easy to update
5. **Testability**: Clean separation of concerns
6. **Scalability**: Database-centric, can handle large volumes
7. **Backward Compatibility**: Legacy format ensures smooth migration

## Key Principles

1. **Database First**: All persistent data comes from the database
2. **No JSON Counters**: JSON files are deprecated for statistics
3. **Centralized Logic**: All statistics logic in one place
4. **Type Safety**: Use schemas for all data contracts
5. **Gradual Migration**: Support old endpoints during transition
6. **Validation**: Compare old vs new to ensure consistency

## Future Improvements

1. **Caching**: Add Redis/in-memory cache for expensive queries
2. **Indexing**: Add database indexes for performance
3. **Materialized Views**: For complex aggregations
4. **Real-time Updates**: WebSocket for live statistics
5. **Historical Data**: Time-series statistics tracking
