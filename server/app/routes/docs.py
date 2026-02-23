# app/routes/docs.py

from fastapi import APIRouter, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_manager import AuthManager
from app.services.doc_manager import DocManager
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