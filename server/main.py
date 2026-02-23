from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import api, views
from app.core.config import settings

app = FastAPI(title="LecAI")

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# 라우터 등록
app.include_router(views.router)
app.include_router(api.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)