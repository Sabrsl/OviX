from fastapi import FastAPI
from uvicorn import run

app = FastAPI()

@app.get('/')
async def root():
    return {'test': 'ok'}

print('FastAPI/uvicorn can be imported and configured')
