# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.routes import view_routes, auth_routes, job_routes, user_routes, doc_routes
import os

app = FastAPI(title="LecAI")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join("static", "favicon.ico"))
    
# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# View 라우터 (HTML 페이지) - Root 레벨
app.include_router(view_routes.router)

# API 라우터 그룹 - /api 프리픽스 아래로 통합
app.include_router(auth_routes.router, prefix="/api", tags=["Auth"])
app.include_router(job_routes.router, prefix="/api", tags=["Jobs"])
app.include_router(user_routes.router, prefix="/api", tags=["User"])
app.include_router(doc_routes.router, prefix="/api", tags=["Docs"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)