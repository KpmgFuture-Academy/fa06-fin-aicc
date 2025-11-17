from fastapi import FastAPI
from app.api.v1 import chat, handover

app = FastAPI(title="Bank AICC Dev Server")

# 라우터 등록 (부품 조립)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(handover.router, prefix="/api/v1/handover", tags=["Handover"])

@app.get("/")
def root():
    return {"status": "Server is running properly!"}