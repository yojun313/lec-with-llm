# app/routes/doc_routes.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from app.services.doc_manager import DocManager
from app.services.job_manager import JobManager
from app.services.auth_manager import AuthManager
from app.core.config import settings
from app.db import docs_col
from app.routes.deps import get_current_user
import shutil
import os

router = APIRouter()

# 기존 api.py의 /docs/folders -> /api/docs/folders (Main에서 prefix 설정 예정)
@router.get("/docs/folders")
async def get_folders(user: str = Depends(get_current_user)):
    try:
        folders = list(docs_col.find({"owner": user, "type": "folder"}, {"_id": 0}))
        return folders
    except Exception as e:
        print(f"[Error] get_folders: {e}")
        raise HTTPException(status_code=500, detail="폴더 목록을 불러오지 못했습니다.")

# 기존 docs.py의 /api/docs/nodes -> Main에서 prefix 처리로 /api/docs/nodes 유지
@router.get("/docs/nodes")
async def get_nodes(parent_id: str = None, user: str = Depends(get_current_user)):
    if parent_id == "root":
        parent_id = None
    return DocManager.get_nodes(user, parent_id)

@router.post("/docs/folder")
async def create_folder(
    name: str = Form(...), 
    parent_id: str = Form(None), 
    user: str = Depends(get_current_user)
):
    if parent_id == "root": parent_id = None
    return DocManager.create_folder(user, name, parent_id)

@router.post("/docs/upload")
async def upload_doc(
    file: UploadFile = File(...), 
    parent_id: str = Form(None), 
    user: str = Depends(get_current_user)
):
    if parent_id == "root": parent_id = None
    
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

@router.delete("/docs/{node_id}")
async def delete_node(node_id: str, user: str = Depends(get_current_user)):
    success = DocManager.delete_node(user, node_id)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "deleted"}

@router.get("/docs/content/{doc_id}")
async def get_content(doc_id: str, user: str = Depends(get_current_user)):
    content = DocManager.get_markdown_content(user, doc_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"content": content}

@router.get("/docs/download/{doc_id}")
async def download_doc(doc_id: str, user: str = Depends(get_current_user)):
    zip_path = DocManager.get_zip_path(user, doc_id)
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    data = DocManager.load_data()
    target = next((n for n in data["nodes"] if n["id"] == doc_id), None)
    display_name = f"{target['name']}.zip" if target else "document.zip"
    
    return FileResponse(
        zip_path, 
        media_type='application/zip', 
        filename=display_name
    )

@router.get("/docs/history") 
def get_job_history(user: str = Depends(get_current_user)):
    jobs = JobManager.get_jobs_by_user(user)
    completed_jobs = [j for j in jobs if j["status"] == "completed"]
    return completed_jobs

# 기존 api.py와 docs.py 양쪽에 있던 로직 통합
@router.post("/docs/import/{job_id}")
async def import_job_to_docs(
    job_id: str,
    parent_id: str = Form(None),
    user: str = Depends(get_current_user)
):
    job = JobManager.get_job(job_id)
    if not job or job["owner"] != user:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="완료된 작업만 가져올 수 있습니다.")
    
    zip_path = os.path.join(settings.RESULT_DIR, f"{job_id}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="결과 파일이 존재하지 않습니다.")
    
    try:
        real_parent_id = None if parent_id == "root" else parent_id
        
        new_doc = DocManager.upload_zip_doc(
            owner=user,
            file_path=zip_path,
            filename=job["filename"], 
            parent_id=real_parent_id
        )
        return new_doc
    except Exception as e:
        print(f"[Error] import_job: {e}")
        raise HTTPException(status_code=500, detail=str(e))