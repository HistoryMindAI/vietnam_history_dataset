from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from app.api.chat import router

app = FastAPI(title="Vietnam History AI")

origins = [
    "http://localhost:3000",    
    "http://localhost:8080",    
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)