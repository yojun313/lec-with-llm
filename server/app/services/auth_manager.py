# app/services/auth_manager.py

import json
import os
import uuid
import hashlib
import bcrypt
import random
from app.core.config import settings
from app.services.email_service import send_verification_email

# 메모리 상의 활성 세션 저장소
sessions = {}

verification_codes = {}

class AuthManager:
    
    def request_signup(username, password, email):
        users = AuthManager.load_users()
        if username in users:
            return "username_exists"
        
        # 이메일 중복 체크
        for user in users.values():
            if user.get("email") == email:
                return "email_exists"
        
        # 인증 코드 생성 (6자리 숫자)
        code = str(random.randint(100000, 999999))
        
        # 메일 발송
        if send_verification_email(email, code):
            # 임시 저장 (검증용)
            verification_codes[email] = {
                "username": username,
                "password": password, # 아직 해싱 전 (실제로는 보안상 해싱해서 임시저장하는게 좋음)
                "code": code
            }
            return "success"
        else:
            return "mail_failed"

    # [추가됨] 회원가입 완료 (2단계: 코드 검증 및 생성)
    @staticmethod
    def verify_and_create_user(email, code):
        data = verification_codes.get(email)
        if not data:
            return False # 요청 내역 없음
        
        if data["code"] != code:
            return False # 코드 불일치
        
        # 검증 완료 -> 실제 계정 생성
        username = data["username"]
        password = data["password"]
        
        users = AuthManager.load_users()
        
        # 비밀번호 해싱
        safe_pw = AuthManager._pre_hash(password)
        hashed_pw = bcrypt.hashpw(safe_pw, bcrypt.gensalt()).decode('utf-8')
        
        users[username] = {
            "password": hashed_pw,
            "email": email,
            "verified": True
        }
        AuthManager.save_users(users)
        
        # 임시 데이터 삭제
        del verification_codes[email]
        return True
    
    @staticmethod
    def load_sessions():
        if not os.path.exists(settings.SESSIONS_FILE):
            return {}
        try:
            with open(settings.SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    def save_sessions(sessions_data):
        with open(settings.SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions_data, f, indent=4, ensure_ascii=False)
            
    @staticmethod
    def _pre_hash(password: str) -> bytes:
        """
        bcrypt의 72바이트 제한을 우회하기 위해 
        SHA-256으로 먼저 해싱하여 64글자(bytes)로 고정합니다.
        """
        # SHA-256 해시 생성 (64글자) -> bytes로 변환
        return hashlib.sha256(password.encode('utf-8')).hexdigest().encode('utf-8')

    @staticmethod
    def load_users():
        if not os.path.exists(settings.USERS_FILE):
            return {}
        try:
            with open(settings.USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    def save_users(users_data):
        with open(settings.USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def create_user(username, password):
        users = AuthManager.load_users()
        if username in users:
            return False
        
        # 1. SHA-256 전처리 (72바이트 제한 회피)
        safe_pw = AuthManager._pre_hash(password)
        
        # 2. Bcrypt 해싱 (bytes 반환되므로 decode하여 문자열 저장)
        hashed_pw = bcrypt.hashpw(safe_pw, bcrypt.gensalt()).decode('utf-8')
        
        users[username] = {"password": hashed_pw}
        AuthManager.save_users(users)
        return True

    @staticmethod
    def authenticate_user(username, password):
        users = AuthManager.load_users()
        user = users.get(username)
        if not user:
            return None
        
        stored_hash = user["password"].encode('utf-8')
        safe_pw = AuthManager._pre_hash(password)
        
        # 비밀번호 검증
        if bcrypt.checkpw(safe_pw, stored_hash):
            session_id = str(uuid.uuid4())
            sessions[session_id] = username
            return session_id
        return None

    @staticmethod
    def get_user_by_session(session_id):
        return sessions.get(session_id)

    @staticmethod
    def logout(session_id):
        if session_id in sessions:
            del sessions[session_id]
            
    @staticmethod
    def update_user_settings(username, api_key, model_choice):
        users = AuthManager.load_users()
        if username in users:
            users[username]["openai_api_key"] = api_key
            users[username]["preferred_model"] = model_choice
            AuthManager.save_users(users)
            return True
        return False

    @staticmethod
    def get_user_settings(username):
        users = AuthManager.load_users()
        user = users.get(username, {})
        return {
            "openai_api_key": user.get("openai_api_key", ""),
            "preferred_model": user.get("preferred_model", "local") # 기본값: local
        }