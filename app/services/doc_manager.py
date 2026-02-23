# app/services/doc_manager.py

import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime
from app.core.config import settings

class DocManager:
    
    @staticmethod
    def get_zip_path(owner: str, doc_id: str):
        data = DocManager.load_data()
        target = next((n for n in data["nodes"] if n["id"] == doc_id and n["owner"] == owner), None)
        if not target or target["type"] != "file":
            return None
        
        # 실제 파일들이 저장된 경로
        source_dir = os.path.join(settings.DOCS_STATIC_DIR, doc_id)
        # 임시로 생성할 압축 파일 경로 (static/uploads 등을 활용)
        zip_output_base = os.path.join(settings.UPLOAD_DIR, f"download_{doc_id}")
        
        # 폴더를 zip으로 압축
        zip_path = shutil.make_archive(zip_output_base, 'zip', source_dir)
        return zip_path
    
    @staticmethod
    def load_data():
        if not os.path.exists(settings.DOCS_DATA_FILE):
            return {"nodes": []} # flat list structure with parent_id
        try:
            with open(settings.DOCS_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"nodes": []}

    @staticmethod
    def save_data(data):
        with open(settings.DOCS_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def get_nodes(owner: str, parent_id: str = None):
        """특정 사용자의 특정 폴더(parent_id)에 있는 파일/폴더 목록 반환"""
        data = DocManager.load_data()
        result = []
        for node in data["nodes"]:
            if node["owner"] == owner and node.get("parent_id") == parent_id:
                result.append(node)
        
        # 폴더 우선, 그 다음 파일 순으로 정렬
        return sorted(result, key=lambda x: (x["type"] != "folder", x["name"]))

    @staticmethod
    def create_folder(owner: str, name: str, parent_id: str = None):
        data = DocManager.load_data()
        new_folder = {
            "id": str(uuid.uuid4()),
            "type": "folder",
            "name": name,
            "owner": owner,
            "parent_id": parent_id,
            "created_at": datetime.now().isoformat()
        }
        data["nodes"].append(new_folder)
        DocManager.save_data(data)
        return new_folder

    @staticmethod
    def upload_zip_doc(owner: str, file_path: str, filename: str, parent_id: str = None):
        """ZIP 파일을 받아 압축을 풀고 문서 노드를 생성"""
        doc_id = str(uuid.uuid4())
        extract_path = os.path.join(settings.DOCS_STATIC_DIR, doc_id)
        os.makedirs(extract_path, exist_ok=True)

        # 1. 압축 해제
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
        except Exception as e:
            shutil.rmtree(extract_path)
            raise e

        # 2. 메타데이터 저장
        # 파일명에서 확장자(.zip) 제거하여 문서 제목으로 사용
        doc_name = os.path.splitext(filename)[0]
        
        data = DocManager.load_data()
        new_doc = {
            "id": doc_id,
            "type": "file",
            "name": doc_name,
            "owner": owner,
            "parent_id": parent_id,
            "path": f"/static/docs/{doc_id}", # 정적 경로
            "created_at": datetime.now().isoformat()
        }
        data["nodes"].append(new_doc)
        DocManager.save_data(data)
        return new_doc

    @staticmethod
    def delete_node(owner: str, node_id: str):
        data = DocManager.load_data()
        
        # 삭제할 노드 찾기
        target = next((n for n in data["nodes"] if n["id"] == node_id and n["owner"] == owner), None)
        if not target:
            return False

        # 하위 요소 재귀 삭제 (폴더일 경우)
        children = [n for n in data["nodes"] if n.get("parent_id") == node_id]
        for child in children:
            DocManager.delete_node(owner, child["id"])

        # 실제 파일 삭제 (파일일 경우)
        if target["type"] == "file":
            full_path = os.path.join(settings.DOCS_STATIC_DIR, target["id"])
            if os.path.exists(full_path):
                shutil.rmtree(full_path)

        # 리스트에서 제거
        data["nodes"] = [n for n in data["nodes"] if n["id"] != node_id]
        DocManager.save_data(data)
        return True

    @staticmethod
    def get_markdown_content(owner: str, doc_id: str):
        data = DocManager.load_data()
        target = next((n for n in data["nodes"] if n["id"] == doc_id and n["owner"] == owner), None)
        if not target:
            return None
        
        md_path = os.path.join(settings.DOCS_STATIC_DIR, doc_id, "result.md")
        if not os.path.exists(md_path):
            return "# Error: Markdown file not found."
        
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # [중요] 이미지 경로 보정
        # result.md 안에는 "./images/abc.png"로 되어 있음 -> "/static/docs/{id}/images/abc.png"로 변경
        content = content.replace("./images/", f"{target['path']}/images/")
        return content