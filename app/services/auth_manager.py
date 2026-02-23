# app/services/auth_manager.py

import uuid
import hashlib
import bcrypt
import random
from app.services.email_service import send_verification_email
from app.db import users_col, sessions_col

# 이메일 인증 코드는 임시 데이터이므로 메모리에 유지 (서버 재시작 시 초기화됨)
# 운영 환경에서는 Redis나 MongoDB TTL Collection 사용을 권장
verification_codes = {}

class AuthManager:
    
    @staticmethod
    def _pre_hash(password: str) -> bytes:
        """
        bcrypt의 72바이트 제한을 우회하기 위해 
        SHA-256으로 먼저 해싱하여 64글자(bytes)로 고정합니다.
        """
        return hashlib.sha256(password.encode('utf-8')).hexdigest().encode('utf-8')

    @staticmethod
    def request_signup(username, password, email):
        # 1. 사용자명 중복 체크 (MongoDB)
        if users_col.find_one({"username": username}):
            return "username_exists"
        
        # 2. 이메일 중복 체크 (MongoDB)
        if users_col.find_one({"email": email}):
            return "email_exists"
        
        # 인증 코드 생성
        code = str(random.randint(100000, 999999))
        
        # 메일 발송
        if send_verification_email(email, code):
            # 임시 저장 (검증용)
            verification_codes[email] = {
                "username": username,
                "password": password, 
                "code": code
            }
            return "success"
        else:
            return "mail_failed"

    @staticmethod
    def verify_and_create_user(email, code):
        data = verification_codes.get(email)
        if not data:
            return False # 요청 내역 없음
        
        if data["code"] != code:
            return False # 코드 불일치
        
        # 검증 완료 -> 실제 계정 생성 준비
        username = data["username"]
        password = data["password"]
        
        # 비밀번호 해싱
        safe_pw = AuthManager._pre_hash(password)
        hashed_pw = bcrypt.hashpw(safe_pw, bcrypt.gensalt()).decode('utf-8')
        
        # MongoDB에 저장할 문서 구조
        new_user = {
            "username": username,
            "password": hashed_pw,
            "email": email,
            "verified": True,
            # 기본 설정값 초기화
            "openai_api_key": "",
            "preferred_model": "local",
            "audio_language": "auto",
            "audio_model_level": 2
        }
        
        # DB 저장
        users_col.insert_one(new_user)
        
        # 임시 데이터 삭제
        del verification_codes[email]
        return True

    @staticmethod
    def create_user(username, password):
        """
        (관리자용 등) 이메일 인증 없이 바로 유저 생성 시 사용
        """
        if users_col.find_one({"username": username}):
            return False
        
        safe_pw = AuthManager._pre_hash(password)
        hashed_pw = bcrypt.hashpw(safe_pw, bcrypt.gensalt()).decode('utf-8')
        
        new_user = {
            "username": username,
            "password": hashed_pw,
            "email": "", # 이메일 없음
            "verified": False, # 인증 안됨
            "openai_api_key": "",
            "preferred_model": "local",
            "audio_language": "auto",
            "audio_model_level": 2
        }
        
        users_col.insert_one(new_user)
        return True

    @staticmethod
    def authenticate_user(username, password):
        # DB에서 유저 조회
        user = users_col.find_one({"username": username})
        if not user:
            return None
        
        stored_hash = user["password"].encode('utf-8')
        safe_pw = AuthManager._pre_hash(password)
        
        # 비밀번호 검증
        if bcrypt.checkpw(safe_pw, stored_hash):
            session_id = str(uuid.uuid4())
            
            # 세션 DB에 저장
            sessions_col.insert_one({
                "session_id": session_id,
                "username": username
            })
            return session_id
        return None

    @staticmethod
    def get_user_by_session(session_id):
        # DB에서 세션 조회
        session = sessions_col.find_one({"session_id": session_id})
        if session:
            return session["username"]
        return None

    @staticmethod
    def logout(session_id):
        # DB에서 세션 삭제
        sessions_col.delete_one({"session_id": session_id})

    @staticmethod
    def update_user_settings(username, api_key, model_choice, audio_lang="auto", audio_model=2, custom_prompt=None):
        # DB 업데이트 ($set 연산자 사용)
        update_data = {
            "openai_api_key": api_key,
            "preferred_model": model_choice,
            "audio_language": audio_lang,
            "audio_model_level": int(audio_model)
        }
        
        # 프롬프트가 None이 아닐 때만 업데이트 (빈 문자열이어도 업데이트)
        if custom_prompt is not None:
            update_data["custom_prompt"] = custom_prompt

        result = users_col.update_one(
            {"username": username},
            {"$set": update_data}
        )
        return result.matched_count > 0

    @staticmethod
    def get_user_settings(username):
        user = users_col.find_one({"username": username})
        
        # 기본 프롬프트 정의
        default_prompt = """당신은 전공 강의 자료를 분석하고 요약하는 전문 AI 조교입니다.
[출력 규칙]
1. **반드시 Markdown 형식**으로 작성
2. **한국어** 사용
3. 서론 없이 본론만 바로 작성"""

        if user:
            return {
                "openai_api_key": user.get("openai_api_key", ""),
                "preferred_model": user.get("preferred_model", "local"),
                "audio_language": user.get("audio_language", "auto"),
                "audio_model_level": user.get("audio_model_level", 2),
                # 저장된 프롬프트가 없으면 기본값 반환
                "custom_prompt": user.get("custom_prompt", default_prompt)
            }
        
        return {
            "openai_api_key": "",
            "preferred_model": "local",
            "audio_language": "auto",
            "audio_model_level": 2,
            "custom_prompt": default_prompt
        }
    
    @staticmethod
    def update_user_cumulative_usage(username: str, cost_usd: float):
        users_col.update_one(
            {"username": username},
            {"$inc": {"total_spent_usd": cost_usd}}
        )

    @staticmethod
    def get_user_usage(username: str):
        user = users_col.find_one({"username": username}, {"total_spent_usd": 1})
        if user and "total_spent_usd" in user:
            return user["total_spent_usd"]
        return 0.0