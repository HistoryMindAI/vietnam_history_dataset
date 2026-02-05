from fastapi import FastAPI
from app.api.chat import router

app = FastAPI(title="Vietnam History AI")

app.include_router(router)
