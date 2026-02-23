# app/routes/docs.py

from fastapi import APIRouter, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_manager import AuthManager
from app.services.doc_manager import DocManager
from app.services.job_manager import JobManager
from app.core.config import settings
import shutil
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 의존성 주입
def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    user = AuthManager.get_user_by_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

@router.get("/guide/openai", response_class=HTMLResponse)
async def get_openai_guide(request: Request):
    return templates.TemplateResponse("guide_openai.html", {"request": request})

# --- 페이지 ---
@router.get("/viewer")
async def viewer_page(request: Request):
    session_id = request.cookies.get("session_id")
    user = AuthManager.get_user_by_session(session_id)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("viewer.html", {"request": request, "username": user})

# --- API ---

@router.get("/api/docs/nodes")
async def get_nodes(parent_id: str = None, user: str = Depends(get_current_user)):
    # parent_id가 "root" 문자열로 오면 None으로 처리
    if parent_id == "root":
        parent_id = None
    return DocManager.get_nodes(user, parent_id)

@router.post("/api/docs/folder")
async def create_folder(
    name: str = Form(...), 
    parent_id: str = Form(None), 
    user: str = Depends(get_current_user)
):
    if parent_id == "root": parent_id = None
    return DocManager.create_folder(user, name, parent_id)

@router.post("/api/docs/upload")
async def upload_doc(
    file: UploadFile = File(...), 
    parent_id: str = Form(None), 
    user: str = Depends(get_current_user)
):
    if parent_id == "root": parent_id = None
    
    # 임시 저장
    temp_path = os.path.join(settings.UPLOAD_DIR, f"temp_{file.filename}")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        new_doc = DocManager.upload_zip_doc(user, temp_path, file.filename, parent_id)
        return new_doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.delete("/api/docs/{node_id}")
async def delete_node(node_id: str, user: str = Depends(get_current_user)):
    success = DocManager.delete_node(user, node_id)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "deleted"}

@router.get("/api/docs/content/{doc_id}")
async def get_content(doc_id: str, user: str = Depends(get_current_user)):
    content = DocManager.get_markdown_content(user, doc_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"content": content}

@router.get("/api/docs/download/{doc_id}")
async def download_doc(doc_id: str, user: str = Depends(get_current_user)):
    zip_path = DocManager.get_zip_path(user, doc_id)
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # 원본 파일명을 찾아서 다운로드 파일명으로 설정
    data = DocManager.load_data()
    target = next((n for n in data["nodes"] if n["id"] == doc_id), None)
    display_name = f"{target['name']}.zip" if target else "document.zip"
    
    return FileResponse(
        zip_path, 
        media_type='application/zip', 
        filename=display_name
    )
    
@router.get("/api/docs/history")  # [수정] /history -> /api/docs/history
def get_job_history(user: str = Depends(get_current_user)): # [수정] Depends 추가
    # user 변수는 get_current_user에서 반환된 사용자 객체(또는 ID)
    # JobManager.get_jobs_by_user는 username 문자열을 기대하므로 맞춰줍니다.
    # AuthManager.get_user_by_session이 username 문자열을 반환한다고 가정
    
    username = user # user가 이미 username 문자열임
    jobs = JobManager.get_jobs_by_user(username)
    completed_jobs = [j for j in jobs if j["status"] == "completed"]
    return completed_jobs

@router.post("/api/docs/import/{job_id}") # [수정] /import -> /api/docs/import
def import_job_to_docs(
    job_id: str,
    parent_id: str = Form(None),
    user: str = Depends(get_current_user) # [수정] Depends 추가
):
    username = user
    job = JobManager.get_job(job_id)
    if not job or job["owner"] != username:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    
    zip_path = os.path.join(settings.RESULT_DIR, f"{job_id}.zip")
    
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Result file not found")
    
    try:
        new_doc = DocManager.upload_zip_doc(
            owner=username,
            file_path=zip_path,
            filename=job["filename"], 
            parent_id=parent_id if parent_id != "root" else None
        )
        return new_doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))