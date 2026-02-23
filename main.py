from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import api, views, docs
from app.core.config import settings

app = FastAPI(title="LecAI")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # static 폴더 안에 있는 favicon.ico 파일을 반환합니다.
    return FileResponse(os.path.join("static", "favicon.ico"))
    
# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# 라우터 등록
app.include_router(views.router)
app.include_router(docs.router)
app.include_router(api.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)