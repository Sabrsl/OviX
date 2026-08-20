"""
OVIX Backend API - README

FastAPI backend for OVIX Wikipedia Maintenance Tool.

## Installation

The FastAPI dependencies have been added to requirements.txt:
- fastapi>=0.104.0
- uvicorn[standard]>=0.24.0
- pydantic>=2.0.0

Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the API

### Simple test version:
```bash
python backend/api/main_simple.py
```

### Full version:
```bash
python start_api.py
```

Or directly with uvicorn:
```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation

Once running, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/health

## Architecture

```
React Frontend (Future)
       ↓
FastAPI Backend (This API)
       ↓
OVIX Python Core (Existing)
       ↓
Wikipedia API
```

## Endpoints

### Authentication
- POST /api/auth/login
- POST /api/auth/logout
- GET /api/auth/status
- GET /api/auth/account

### Articles
- POST /api/articles/category
- POST /api/articles/manual
- GET /api/articles/{title}
- GET /api/articles/{title}/exists

### Analysis
- POST /api/analysis/start
- GET /api/analysis/{analysis_id}
- POST /api/analysis/{analysis_id}/cancel
- GET /api/analysis/{analysis_id}/results

### Diff
- POST /api/diff/generate
- GET /api/diff/{diff_id}

### Publication
- POST /api/publication/validate
- POST /api/publication/publish
- GET /api/publication/{publication_id}

### History
- GET /api/history/published
- GET /api/history/analyzed
- GET /api/history/{title}
- GET /api/history/statistics

### Logs
- GET /api/logs/
- GET /api/logs/recent
- GET /api/logs/stats

### Settings
- GET /api/settings/
- PUT /api/settings/

### System
- GET /api/system/kill-switch
- POST /api/system/kill-switch/activate
- POST /api/system/kill-switch/deactivate
- GET /api/system/scheduler
- POST /api/system/scheduler/start
- POST /api/system/scheduler/pause
- POST /api/system/scheduler/resume
- POST /api/system/scheduler/stop
- GET /api/system/automation

## Testing

Run API tests:
```bash
pytest backend/tests/test_api.py -v
```

## Compatibility

This API is designed to work alongside the existing Streamlit frontend.
Both interfaces can use the same Python core services.

## Environment Variables

Add to .env:
```
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
API_HOST=0.0.0.0
API_PORT=8000
```
