import os
import shutil
import base64
import requests
import subprocess
import zipfile
import pdfkit
import threading
from pdf2image import convert_from_path
from app.core.config import settings
from app.services.job_manager import JobManager
from app.services.auth_manager import AuthManager

# ==========================================
# Global Lock
# ==========================================
# 한 번에 하나의 작업만 처리하기 위한 Lock 객체
task_lock = threading.Lock()

# ==========================================
# Helper Functions
# ==========================================

def get_headers(api_key=None):
    """
    api_key가 있으면(사용자 설정) 그것을 사용하고,
    없으면 서버 기본 설정(Local Server 토큰)을 사용합니다.
    """
    if api_key:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    # 로컬 서버용 토큰
    return {
        "Authorization": f"Bearer {settings.CUSTOM_TOKEN}",
        "Content-Type": "application/json",
    }

def get_target_model(user_settings):
    """
    사용자 설정에 따라 모델 ID와 Base URL, API Key를 결정합니다.
    OpenAI의 gpt-5.2, gpt-4o 등 다양한 모델명을 지원합니다.
    """
    pref = user_settings.get("preferred_model", "local")
    user_key = user_settings.get("openai_api_key", "")

    # 1. OpenAI 모드 (gpt-4o, gpt-5.2 등)
    if pref.startswith("gpt"):
        if not user_key:
            raise ValueError("OpenAI 모델이 선택되었으나 API Key가 설정되지 않았습니다.")
        
        return {
            "provider": "openai",
            "model_id": pref, 
            "base_url": "https://api.openai.com/v1",
            "api_key": user_key
        }

    # 2. Local Server 모드
    else:
        # 로컬 서버에서 모델 ID 조회
        try:
            url = f"{settings.CUSTOM_BASE_URL}/models"
            resp = requests.get(url, headers=get_headers(), timeout=5)
            resp.raise_for_status()
            models = resp.json().get("data", [])
            if not models:
                raise RuntimeError("로컬 서버에 사용 가능한 모델이 없습니다.")
            found_id = models[0]["id"]
            
            return {
                "provider": "local",
                "model_id": found_id,
                "base_url": settings.CUSTOM_BASE_URL,
                "api_key": None # 로컬은 헤더 생성시 CUSTOM_TOKEN 사용
            }
        except Exception as e:
            print(f"[WARN] Local model fetch failed: {e}")
            # 실패 시 기본값 (환경변수 fallback)
            return {
                "provider": "local",
                "model_id": "gpt-4o",
                "base_url": settings.CUSTOM_BASE_URL,
                "api_key": None
            }

# [수정됨] job_id, current, total 인자 추가 (로그 기록용)
def describe_image(image_path: str, model_config: dict, job_id: str = None, current: int = 0, total: int = 0):
    filename = os.path.basename(image_path)
    
    # 설정된 URL과 Key 사용
    url = f"{model_config['base_url']}/chat/completions"
    headers = get_headers(model_config['api_key'])

    def image_to_data_url(path):
        with open(path, "rb") as f:
            raw = f.read()
        encoded = base64.b64encode(raw).decode("utf-8")
        ext = os.path.splitext(path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        return f"data:{mime};base64,{encoded}"

    # [CACHING STRATEGY]
    # OpenAI Prompt Caching을 위해 'System Message'를 고정된 긴 텍스트로 분리합니다.
    system_instruction = """
    당신은 전공 강의 자료를 분석하고 요약하는 전문 AI 조교입니다.
    제공되는 이미지는 강의 PPT 슬라이드입니다.

    [분석 및 출력 규칙]
    1. **반드시 Markdown 형식**으로 작성하십시오.
    2. 언어는 **한국어**를 사용하십시오.
    3. 인삿말, 서론, 메타 설명("이 슬라이드는...", "분석 결과입니다")은 생략하고 바로 본론만 작성하십시오.
    4. 코드 블록(```)으로 감싸지 말고 순수 마크다운 텍스트만 출력하십시오.

    [포함해야 할 내용]
    1. **슬라이드 주제**: 슬라이드의 핵심 주제를 파악하여 요약하십시오.
    2. **시각 자료 설명**: 그림, 도표, 그래프가 있다면 그 의미와 수치를 상세히 설명하십시오.
    3. **상세 설명**: 전공자의 관점에서 텍스트 내용을 논리적으로 재구성하여 매우 자세하게 설명하십시오.
    """

    user_instruction = f"""
    이 슬라이드의 파일명은 "{filename}"입니다.
    위의 규칙에 따라 이 슬라이드를 분석해 주세요.
    제목은 "## {filename}" 형식을 사용해 주세요.
    """

    payload = {
        "model": model_config['model_id'],
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_instruction.strip()
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_instruction.strip()
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_to_data_url(image_path)
                        }
                    }
                ],
            }
        ],
        "max_completion_tokens": 1600,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if resp.status_code != 200:
        print(f"[ERROR] LLM Request Failed: {resp.text}")
        raise RuntimeError(f"LLM Error: {resp.text}")
    
    result = resp.json()
    content = result["choices"][0]["message"]["content"]

    # [추가됨] 토큰 사용량 로깅 (OpenAI인 경우 Cached Token 확인)
    if job_id and model_config['provider'] == 'openai':
        try:
            usage = result.get('usage', {})
            p_tokens = usage.get('prompt_tokens', 0)
            c_tokens = usage.get('completion_tokens', 0)
            t_tokens = usage.get('total_tokens', 0)
            
            # OpenAI Prompt Caching 정보 확인
            # prompt_tokens_details 안에 cached_tokens가 존재함
            p_details = usage.get('prompt_tokens_details', {})
            cached = p_details.get('cached_tokens', 0)

            # 로그 메시지 생성
            log_msg = f"[Token] In: {p_tokens} (Cached: {cached}) | Out: {c_tokens} | Total: {t_tokens}"
            
            # JobManager에 로그 기록 (진행률은 유지)
            JobManager.update_progress(job_id, current, total, log_msg)
            print(log_msg)

        except Exception as e:
            print(f"[WARN] Token logging failed: {e}")

    return content

def convert_ppt_to_pdf(ppt_path: str, output_dir: str):
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, ppt_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    base = os.path.splitext(os.path.basename(ppt_path))[0]
    return os.path.join(output_dir, f"{base}.pdf")

# ==========================================
# Main Task (With Lock)
# ==========================================

def process_file_task(job_id: str, file_path: str):
    
    # 0. 작업 소유자 확인 및 설정 로드
    job = JobManager.get_job(job_id)
    if not job:
        return
    
    owner = job.get("owner")
    user_settings = AuthManager.get_user_settings(owner)
    
    # 대기열 로깅
    try:
        queue_pos = JobManager.get_queue_position(job_id)
        if queue_pos > 0:
            JobManager.update_progress(job_id, 0, 0, f"대기열 진입: 앞선 작업 {queue_pos}개 대기 중")
        else:
            JobManager.update_progress(job_id, 0, 0, "작업 준비 중...")
    except: pass

    # 1. Lock 획득 시도 (여기서 대기 발생)
    with task_lock:
        work_dir = os.path.join(settings.UPLOAD_DIR, job_id)
        os.makedirs(work_dir, exist_ok=True)
        
        try:
            # [상태 변경] 락을 얻었으므로 Processing으로 변경
            JobManager.start_processing(job_id)
            JobManager.update_progress(job_id, 0, 0, "작업 시작! (리소스 할당됨)")
            
            # [모델 결정] 사용자 설정에 따라
            try:
                model_config = get_target_model(user_settings)
                JobManager.update_progress(job_id, 0, 0, f"모델 연결: {model_config['model_id']} ({model_config['provider']})")
            except Exception as e:
                raise RuntimeError(f"모델 설정 오류: {str(e)}")

            # 2. 파일 변환
            images = []
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == ".pdf":
                JobManager.update_progress(job_id, 0, 0, "PDF 페이지 추출 중...")
                raw_images = convert_from_path(file_path, fmt="png", dpi=150)
                for i, img in enumerate(raw_images):
                    p = os.path.join(work_dir, f"page_{i:03d}.png")
                    img.save(p)
                    images.append(p)

            elif ext in [".ppt", ".pptx"]:
                JobManager.update_progress(job_id, 0, 0, "PPT -> PDF 변환 중...")
                pdf_path = convert_ppt_to_pdf(file_path, work_dir)
                raw_images = convert_from_path(pdf_path, fmt="png", dpi=150)
                for i, img in enumerate(raw_images):
                    p = os.path.join(work_dir, f"page_{i:03d}.png")
                    img.save(p)
                    images.append(p)
            
            else:
                raise ValueError("지원하지 않는 파일 형식입니다.")

            # 3. 결과 폴더 준비
            result_base = os.path.join(settings.RESULT_DIR, job_id)
            result_images_dir = os.path.join(result_base, "images")
            os.makedirs(result_images_dir, exist_ok=True)

            total_pages = len(images)
            JobManager.update_progress(job_id, 0, total_pages, f"총 {total_pages}장 이미지 분석 시작")

            md_content = f""
            
            # 4. LLM 분석 루프
            for idx, img_path in enumerate(images, 1):
                JobManager.update_progress(job_id, idx, total_pages, f"슬라이드 {idx}/{total_pages} 분석 중...")
                
                img_filename = os.path.basename(img_path)
                dst_img_path = os.path.join(result_images_dir, img_filename)
                shutil.copy2(img_path, dst_img_path)

                # [수정됨] describe_image에 job_id와 진행률 정보를 넘겨서 내부에서 토큰 로그를 남기도록 함
                desc = describe_image(img_path, model_config, job_id, idx, total_pages)
                
                md_content += f"## Slide {idx-1}\n\n"
                md_content += f"![{img_filename}](./images/{img_filename})\n\n"
                md_content += f"{desc}\n\n---\n\n"

            # 5. 문서 생성
            JobManager.update_progress(job_id, total_pages, total_pages, "PDF 문서 생성 중...")
            
            md_file = os.path.join(result_base, "result.md")
            pdf_file = os.path.join(result_base, "result.pdf")
            
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_content)
                
            import markdown
            html = markdown.markdown(md_content)
            
            abs_result_base = os.path.abspath(result_base)
            if os.name == 'nt':
                 base_href = f"file:///{abs_result_base.replace(os.sep, '/')}/"
            else:
                 base_href = f"file://{abs_result_base}/"

            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <base href="{base_href}">
                <style>
                    body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; }}
                    img {{ max-width: 100%; height: auto; display: block; margin: 20px 0; border: 1px solid #ccc; }}
                    h1, h2 {{ color: #333; page-break-before: always; }}
                    h1:first-child {{ page-break-before: auto; }}
                </style>
            </head>
            <body>
            {html}
            </body>
            </html>
            """
            
            options = {"quiet": "", "encoding": "UTF-8", "enable-local-file-access": ""}
            pdfkit.from_string(html_content, pdf_file, options=options)

            # 6. 압축 및 완료 처리
            JobManager.update_progress(job_id, total_pages, total_pages, "결과물 압축 중...")
            
            zip_output_path = os.path.join(settings.RESULT_DIR, job_id)
            shutil.make_archive(zip_output_path, 'zip', result_base)

            rel_path = f"/static/results/{job_id}.zip"
            JobManager.mark_completed(job_id, rel_path)

        except Exception as e:
            print(f"[CRITICAL ERROR] {e}")
            JobManager.mark_failed(job_id, str(e))
        finally:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)