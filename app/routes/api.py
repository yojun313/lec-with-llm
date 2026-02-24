# app/routes/api.py

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Request, Depends, Form
from fastapi.responses import JSONResponse, HTMLResponse
from typing import Optional, Any
from app.services.job_manager import JobManager
from app.services.auth_manager import AuthManager
from app.services.processor import process_file_task
from app.core.config import settings
from app.services.audio_processor import process_audio_task
from app.db import docs_col
import shutil
import os
from pydantic import BaseModel

router = APIRouter()

class VerifyRequest(BaseModel):
    email: str
    code: str


# [수정됨] 회원가입 요청 (인증 메일 발송)
@router.post("/auth/signup/request")
async def api_signup_request(
    username: str = Form(...), 
    password: str = Form(...), 
    email: str = Form(...)
):
    result = AuthManager.request_signup(username, password, email)
    if result == "success":
        return {"message": "Verification email sent"}
    elif result == "username_exists":
        raise HTTPException(status_code=400, detail="Username already exists")
    elif result == "email_exists":
        raise HTTPException(status_code=400, detail="Email already exists")
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")

# [추가됨] 인증 코드 확인 및 가입 완료
@router.post("/auth/signup/verify")
async def api_signup_verify(req: VerifyRequest):
    if AuthManager.verify_and_create_user(req.email, req.code):
        return {"message": "User created successfully"}
    raise HTTPException(status_code=400, detail="Invalid verification code")

# 의존성: 현재 사용자 확인
def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    user = AuthManager.get_user_by_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

# --- Auth APIs ---
@router.post("/auth/signup")
async def api_signup(username: str = Form(...), password: str = Form(...)):
    if AuthManager.create_user(username, password):
        return {"message": "User created"}
    raise HTTPException(status_code=400, detail="User already exists")

@router.post("/auth/login")
async def api_login(username: str = Form(...), password: str = Form(...)):
    session_id = AuthManager.authenticate_user(username, password)
    if session_id:
        response = JSONResponse(content={"message": "Login successful"})
        
        # [수정됨] 쿠키 유효기간 설정 (7일 = 60*60*24*7 초)
        response.set_cookie(
            key="session_id", 
            value=session_id, 
            httponly=True,
            max_age=60*60*24*7,  # 7일간 유지 (자동 로그인 효과)
            expires=60*60*24*7   # IE 등 호환성용
        )
        return response
    raise HTTPException(status_code=401, detail="Invalid credentials")

# --- Job APIs ---
@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    user: str = Depends(get_current_user)
):
    # 파일 저장
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 작업 생성
    job_id = JobManager.create_job(file.filename, user)
    
    # 확장자 확인 및 분기 처리
    ext = os.path.splitext(file.filename)[1].lower()
    
    if ext in ['.mp3', '.wav', '.m4a', '.flac']:
        # 오디오 처리기 호출
        background_tasks.add_task(process_audio_task, job_id, file_path)
    else:
        # 기존 PPT/PDF 처리기 호출
        background_tasks.add_task(process_file_task, job_id, file_path)
    
    return {"job_id": job_id, "message": "Upload successful"}

@router.get("/jobs")
async def get_my_jobs(user: str = Depends(get_current_user)):
    # 내 작업만 조회
    return JobManager.get_jobs_by_user(user)

@router.get("/status/{job_id}")
async def get_status(job_id: str, user: str = Depends(get_current_user)):
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404)
    # 보안: 내 작업이 아니면 상태도 안 보여줌 (선택사항)
    if job.get("owner") != user:
         raise HTTPException(status_code=403, detail="Not your job")
    return job

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: str = Depends(get_current_user)):
    success = JobManager.delete_job(job_id, user)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or permission denied")
    return {"message": "Job deleted"}

@router.post("/settings")
async def save_settings(
    model: str = Form(...),
    api_key: str = Form(""),
    audio_lang: str = Form("ko"),
    audio_model: str = Form("2"),
    custom_prompt: Optional[str] = Form(None),
    custom_user_prompt: Optional[str] = Form(None),  
    profile_img: Optional[UploadFile] = File(None), 
    user: Any = Depends(get_current_user)
):
    try:
        int_audio_model = int(audio_model)
    except:
        int_audio_model = 2

    # 1. 프로필 이미지가 업로드된 경우 먼저 처리
    profile_url = None
    if profile_img and profile_img.filename:
        profile_dir = "static/profiles"
        os.makedirs(profile_dir, exist_ok=True)
        
        ext = os.path.splitext(profile_img.filename)[1]
        file_path = os.path.join(profile_dir, f"{user}{ext}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_img.file, buffer)
        profile_url = f"/{file_path}"

    # 2. 사용자 설정 및 프로필 URL 업데이트
    # AuthManager.update_user_settings에 profile_url 인자를 추가해서 호출
    success = AuthManager.update_user_settings(
        user, api_key, model, audio_lang, int_audio_model, custom_prompt, custom_user_prompt, profile_url
    )
    
    if success:
        return {"status": "success", "profile_url": profile_url}
    else:
        raise HTTPException(status_code=400, detail="설정 저장 실패")

@router.get("/docs/folders")
async def get_folders(user: str = Depends(get_current_user)):
    try:
        # 해당 사용자가 소유한 'folder' 타입의 문서만 모두 가져옴
        folders = list(docs_col.find({"owner": user, "type": "folder"}, {"_id": 0}))
        return folders
    except Exception as e:
        print(f"[Error] get_folders: {e}")
        raise HTTPException(status_code=500, detail="폴더 목록을 불러오지 못했습니다.")

@router.post("/docs/import/{job_id}")
async def import_job_to_docs(
    job_id: str,
    parent_id: str = Form(None),
    user: str = Depends(get_current_user)
):
    # Job 정보 확인
    job = JobManager.get_job(job_id)
    if not job or job["owner"] != user:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="완료된 작업만 가져올 수 있습니다.")
    
    # 결과 ZIP 경로 확인 (JobManager가 결과물을 .zip으로 압축해둔 위치)
    zip_path = os.path.join(settings.RESULT_DIR, f"{job_id}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="결과 파일이 존재하지 않습니다.")
    
    try:
        # DocManager의 업로드 로직 재사용 (ZIP 압축해제 및 DB 등록)
        # 프론트에서 넘어온 parent_id가 'root'이면 None으로 처리
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

@router.get("/settings/usage")
async def get_usage_info(user: str = Depends(get_current_user)):
    # 이제 Job 기록을 전수조사하지 않고, AuthManager가 DB에서 한 줄만 읽어옵니다.
    total_usd = AuthManager.get_user_usage(user)
    return {"total_spent_usd": round(total_usd, 4)}

@router.post("/user/profile-image")
async def upload_profile_image(
    file: UploadFile = File(...), 
    user: str = Depends(get_current_user)
):
    # static/profiles 폴더 생성
    os.makedirs("static/profiles", exist_ok=True)
    
    # 파일 확장자 추출 및 저장 경로 (유저별로 덮어쓰기)
    ext = os.path.splitext(file.filename)[1]
    file_path = f"static/profiles/{user}{ext}"
    profile_url = f"/{file_path}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # DB 업데이트 (AuthManager에 해당 메서드 추가 필요)
    from app.db import users_col
    users_col.update_one({"username": user}, {"$set": {"profile_img": profile_url}})

    return {"status": "success", "url": profile_url}