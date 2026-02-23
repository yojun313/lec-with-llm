# app/routes/api.py

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Request, Depends, Form
from fastapi.responses import JSONResponse
from app.services.job_manager import JobManager
from app.services.auth_manager import AuthManager
from app.services.processor import process_file_task
from app.core.config import settings
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
    user: str = Depends(get_current_user) # 로그인 필수
):
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 작업 생성 시 user(소유자) 전달
    job_id = JobManager.create_job(file.filename, user)
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

# [추가됨] 설정 저장 API
@router.post("/settings")
async def save_settings(
    model: str = Form(...), 
    api_key: str = Form(None), 
    user: str = Depends(get_current_user)
):
    if api_key is None:
        api_key = ""
        
    AuthManager.update_user_settings(user, api_key, model)
    return {"message": "Settings saved successfully"}