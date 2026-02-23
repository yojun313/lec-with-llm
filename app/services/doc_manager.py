# app/services/doc_manager.py

import os
import shutil
import uuid
import zipfile
from datetime import datetime
from app.core.config import settings
from app.db import docs_col

class DocManager:
    
    @staticmethod
    def get_zip_path(owner: str, doc_id: str):
        # MongoDB에서 문서 정보 조회
        target = docs_col.find_one({"id": doc_id, "owner": owner})
        
        if not target or target["type"] != "file":
            return None
        
        # 실제 파일들이 저장된 경로
        source_dir = os.path.join(settings.DOCS_STATIC_DIR, doc_id)
        # 임시로 생성할 압축 파일 경로
        zip_output_base = os.path.join(settings.UPLOAD_DIR, f"download_{doc_id}")
        
        # 폴더를 zip으로 압축
        zip_path = shutil.make_archive(zip_output_base, 'zip', source_dir)
        return zip_path
    
    # load_data, save_data 제거됨 (DB 사용으로 불필요)

    @staticmethod
    def get_nodes(owner: str, parent_id: str = None):
        """특정 사용자의 특정 폴더(parent_id)에 있는 파일/폴더 목록 반환"""
        
        # MongoDB 조회
        query = {"owner": owner, "parent_id": parent_id}
        
        # _id 필드는 프론트엔드에 필요 없으므로 제외하고 가져옴
        nodes = list(docs_col.find(query, {"_id": 0}))
        
        # 폴더 우선, 그 다음 이름 순으로 정렬 (Python 레벨에서 정렬)
        return sorted(nodes, key=lambda x: (x["type"] != "folder", x["name"]))

    @staticmethod
    def create_folder(owner: str, name: str, parent_id: str = None):
        new_folder = {
            "id": str(uuid.uuid4()),
            "type": "folder",
            "name": name,
            "owner": owner,
            "parent_id": parent_id,
            "created_at": datetime.now().isoformat()
        }
        
        # DB 저장
        docs_col.insert_one(new_folder)
        
        # 반환 시 _id 객체는 제외 (JSON 직렬화 오류 방지)
        new_folder.pop("_id", None)
        return new_folder

    @staticmethod
    def upload_zip_doc(owner: str, file_path: str, filename: str, parent_id: str = None):
        """ZIP 파일을 받아 압축을 풀고 문서 노드를 생성 (폴더 구조 자동 보정 포함)"""
        doc_id = str(uuid.uuid4())
        extract_path = os.path.join(settings.DOCS_STATIC_DIR, doc_id)
        os.makedirs(extract_path, exist_ok=True)

        # 1. 압축 해제
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
        except Exception as e:
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
            raise e

        # =========================================================
        # [추가된 로직] 폴더 구조 자동 보정 (Flatten)
        # =========================================================
        # 만약 최상위에 result.md가 없고, 폴더가 하나만 있다면 그 안으로 들어가서 꺼내옵니다.
        if not os.path.exists(os.path.join(extract_path, "result.md")):
            
            # 숨김 파일(.DS_Store, __MACOSX 등)을 제외한 실제 항목 확인
            items = os.listdir(extract_path)
            visible_items = [i for i in items if not i.startswith('.') and not i.startswith('__')]
            
            # 항목이 딱 하나이고, 그것이 디렉토리라면? (중첩 폴더 상황)
            if len(visible_items) == 1:
                nested_dir = os.path.join(extract_path, visible_items[0])
                
                if os.path.isdir(nested_dir):
                    print(f"[Info] 중첩된 폴더 구조 감지: {visible_items[0]} -> 구조 평탄화 수행")
                    
                    # 내부의 모든 파일/폴더를 상위(extract_path)로 이동
                    for item in os.listdir(nested_dir):
                        src_path = os.path.join(nested_dir, item)
                        dst_path = os.path.join(extract_path, item)
                        
                        # 이름 충돌 방지 (혹시나 같은 이름이 있다면 덮어쓰거나 건너뛰기)
                        if os.path.exists(dst_path):
                            if os.path.isdir(dst_path):
                                shutil.rmtree(dst_path)
                            else:
                                os.remove(dst_path)
                        
                        shutil.move(src_path, extract_path)
                    
                    # 빈 껍데기 폴더 삭제
                    os.rmdir(nested_dir)

        # 2. 메타데이터 DB 저장
        doc_name = os.path.splitext(filename)[0]
        
        new_doc = {
            "id": doc_id,
            "type": "file",
            "name": doc_name,
            "owner": owner,
            "parent_id": parent_id,
            "path": f"/static/docs/{doc_id}", # 정적 경로
            "created_at": datetime.now().isoformat()
        }
        
        docs_col.insert_one(new_doc)
        new_doc.pop("_id", None)
        return new_doc
    @staticmethod
    def delete_node(owner: str, node_id: str):
        # 삭제할 노드 찾기
        target = docs_col.find_one({"id": node_id, "owner": owner})
        if not target:
            return False

        # 하위 요소 재귀 삭제 (폴더일 경우 자식 노드들도 삭제)
        children = docs_col.find({"parent_id": node_id})
        for child in children:
            DocManager.delete_node(owner, child["id"])

        # 실제 파일 삭제 (파일일 경우)
        if target["type"] == "file":
            full_path = os.path.join(settings.DOCS_STATIC_DIR, target["id"])
            if os.path.exists(full_path):
                shutil.rmtree(full_path)

        # DB에서 노드 삭제
        docs_col.delete_one({"id": node_id})
        return True

    @staticmethod
    def get_markdown_content(owner: str, doc_id: str):
        # 문서 정보 확인
        target = docs_col.find_one({"id": doc_id, "owner": owner})
        if not target:
            return None
        
        # 마크다운 파일 읽기 (물리적 파일 시스템에서)
        md_path = os.path.join(settings.DOCS_STATIC_DIR, doc_id, "result.md")
        if not os.path.exists(md_path):
            return "# Error: Markdown file not found."
        
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # [중요] 이미지 경로 보정
        content = content.replace("./images/", f"{target['path']}/images/")
        return content