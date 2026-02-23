# app/services/job_manager.py

import uuid
import json
import os
import shutil
from datetime import datetime
from app.core.config import settings

# 전역 변수 jobs
jobs = {}

class JobManager:
    @staticmethod
    def load_history():
        global jobs
        if os.path.exists(settings.HISTORY_FILE):
            try:
                with open(settings.HISTORY_FILE, "r", encoding="utf-8") as f:
                    saved_jobs = json.load(f)
                for jid, job in saved_jobs.items():
                    if job["status"] in ["processing", "pending"]:
                        job["status"] = "failed"
                        job["error"] = "Server restarted during processing"
                        job["logs"].append("서버 재시작으로 인해 작업이 중단되었습니다.")
                jobs = saved_jobs
            except Exception as e:
                print(f"[ERROR] 히스토리 로드 실패: {e}")
                jobs = {}

    @staticmethod
    def save_history():
        try:
            with open(settings.HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] 히스토리 저장 실패: {e}")

    @staticmethod
    def create_job(filename: str, owner: str):
        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "id": job_id,
            "filename": filename,
            "owner": owner,
            "status": "pending",
            "progress": 0,
            "total_pages": 0,
            "current_page": 0,
            "logs": [],
            "created_at": datetime.now().isoformat(),
            "result_url": None,
            "error": None
        }
        JobManager.save_history()
        return job_id
    
    # [추가됨] 작업을 실제로 시작할 때 호출하는 메서드
    @staticmethod
    def start_processing(job_id: str):
        if job_id in jobs:
            jobs[job_id]["status"] = "processing"

    @staticmethod
    def get_jobs_by_user(username: str):
        user_jobs = []
        for job in jobs.values():
            if job.get("owner") == username:
                user_jobs.append(job)
        return sorted(user_jobs, key=lambda x: x['created_at'], reverse=True)
    
    @staticmethod
    def get_job(job_id: str):
        return jobs.get(job_id)

    @staticmethod
    def get_all_jobs():
        return sorted(jobs.values(), key=lambda x: x['created_at'], reverse=True)

    @staticmethod
    def update_progress(job_id: str, current: int, total: int, message: str = None):
        if job_id in jobs:
            # [삭제됨] 여기서 status를 자동으로 processing으로 바꾸던 코드를 제거했습니다.
            # 이제 대기열 로그를 남겨도 상태가 바뀌지 않습니다.
            
            jobs[job_id]["current_page"] = current
            jobs[job_id]["total_pages"] = total
            if total > 0:
                jobs[job_id]["progress"] = int((current / total) * 100)
            if message:
                jobs[job_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    @staticmethod
    def mark_completed(job_id: str, result_path: str):
        if job_id in jobs:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["result_url"] = result_path
            jobs[job_id]["logs"].append("작업 완료! 다운로드 가능합니다.")
            JobManager.save_history()

    @staticmethod
    def mark_failed(job_id: str, error_msg: str):
        if job_id in jobs:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = error_msg
            jobs[job_id]["logs"].append(f"에러 발생: {error_msg}")
            JobManager.save_history()

    @staticmethod
    def delete_job(job_id: str, username: str):
        if job_id in jobs:
            if jobs[job_id].get("owner") != username:
                return False
            del jobs[job_id]
            JobManager.save_history()
            try:
                result_path = os.path.join(settings.RESULT_DIR, job_id)
                if os.path.exists(result_path):
                    shutil.rmtree(result_path)
                zip_path = os.path.join(settings.RESULT_DIR, f"{job_id}.zip")
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                upload_path = os.path.join(settings.UPLOAD_DIR, job_id)
                if os.path.exists(upload_path):
                    shutil.rmtree(upload_path)
            except Exception as e:
                print(f"[WARN] 파일 삭제 중 오류: {e}")
            return True
        return False

    @staticmethod
    def get_queue_position(job_id: str) -> int:
        if job_id not in jobs:
            return 0
        target_created_at = jobs[job_id]['created_at']
        count = 0
        for job in jobs.values():
            if job['created_at'] < target_created_at:
                if job['status'] in ['pending', 'processing']:
                    count += 1
        return count

JobManager.load_history()