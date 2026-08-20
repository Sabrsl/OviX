"""
Minimal FastAPI test - no OVIX imports
"""

from fastapi import FastAPI

app = FastAPI(title="Minimal Test")

@app.get("/")
async def root():
    return {"message": "FastAPI works"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
