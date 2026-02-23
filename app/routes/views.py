# app/routes/views.py

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_manager import AuthManager
import os

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/")
async def index(request: Request):
    session_id = request.cookies.get("session_id")
    user = AuthManager.get_user_by_session(session_id)
    
    if not user:
        return RedirectResponse(url="/login")

    user_settings = AuthManager.get_user_settings(user)

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "username": user,
        "settings": user_settings  
    })

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    AuthManager.logout(session_id)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_id")
    return response

@router.get("/settings")
async def settings_page(request: Request):
    session_id = request.cookies.get("session_id")
    user = AuthManager.get_user_by_session(session_id)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # 현재 설정 불러오기
    user_settings = AuthManager.get_user_settings(user)
    
    return templates.TemplateResponse("settings.html", {
        "request": request, 
        "username": user,
        "settings": user_settings
    })