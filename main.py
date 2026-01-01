import os
import zipfile
import tempfile
import requests
import base64
from dotenv import load_dotenv

# =============================
# 환경 설정
# =============================
load_dotenv()

BASE_URL = os.getenv("URL")
TOKEN = os.getenv("TOKEN", "EMPTY")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULT_DIR = os.path.join(SCRIPT_DIR, "result")

IMAGE_EXTS = (".png", ".jpg", ".jpeg")


# =============================
# 모델 자동 선택
# =============================
def get_model_id():
    resp = requests.get(f"{BASE_URL}/models", headers=HEADERS, timeout=10)
    resp.raise_for_status()

    models = resp.json().get("data", [])
    if not models:
        raise RuntimeError("❌ 사용 가능한 모델이 없습니다.")

    return models[0]["id"]


# =============================
# 이미지 → base64
# =============================
def image_to_data_url(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()

    encoded = base64.b64encode(raw).decode("utf-8")

    ext = os.path.splitext(path)[1].lower()
    mime = "image/jpeg"
    if ext == ".png":
        mime = "image/png"

    return f"data:{mime};base64,{encoded}"


# =============================
# 이미지 설명 생성
# =============================
def describe_image(model_id, image_path):
    filename = os.path.basename(image_path)
    image_data_url = image_to_data_url(image_path)

    prompt = f"""
        이 이미지는 발표용 PPT 슬라이드 한 장이다.

        이 슬라이드를 분석하여 README.md에 들어갈 설명을 작성하라.

        출력 규칙:
        - 반드시 Markdown 형식으로 작성한다.
        - 제목은 "## {filename}" 형식으로 시작한다.
        - 한국어로 작성한다.
        - 불필요한 인사말이나 메타 설명은 쓰지 않는다.
        - 코드 블록은 사용하지 않는다.

        설명에는 다음을 포함한다:
        - 슬라이드의 주제
        - 핵심 내용 요약
        - 도표나 그림의 의미
        - 전달하려는 핵심 메시지
        - 전공 ppt 슬라이드에 대한 자세한 설명
    """

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        }
                    }
                ],
            }
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }

    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        json=payload,
        timeout=180,
    )

    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# =============================
# zip 하나 처리
# =============================
def process_zip(zip_path, model_id):
    zip_name = os.path.splitext(os.path.basename(zip_path))[0]
    output_dir = os.path.join(RESULT_DIR, zip_name)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n📦 처리 시작: {zip_name}")
    print(f"📁 결과 폴더: {output_dir}")

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)

        for root, _, files in os.walk(tmp):
            for fname in sorted(files):
                if not fname.lower().endswith(IMAGE_EXTS):
                    continue

                img_path = os.path.join(root, fname)
                md_path = os.path.join(
                    output_dir,
                    os.path.splitext(fname)[0] + ".md"
                )

                print(f"  🖼 {fname}")

                try:
                    text = describe_image(model_id, img_path)
                except Exception as e:
                    print(f"    ❌ 실패: {e}")
                    continue

                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(text.strip() + "\n")

                print(f"    ✅ 저장됨 → {md_path}")


# =============================
# 메인 진입점
# =============================
def main():
    if not os.path.isdir(DATA_DIR):
        print("❌ data 폴더가 없습니다.")
        return

    os.makedirs(RESULT_DIR, exist_ok=True)

    zip_files = sorted(
        f for f in os.listdir(DATA_DIR)
        if f.lower().endswith(".zip")
    )

    if not zip_files:
        print("❌ data 폴더에 zip 파일이 없습니다.")
        return

    print("\n📦 처리할 ZIP 파일 목록:")
    for i, name in enumerate(zip_files, 1):
        print(f"  [{i}] {name}")
    print("  [a] 전체 처리")

    choice = input("\n선택: ").strip().lower()

    model_id = get_model_id()
    print(f"\n✅ 사용 중인 모델: {model_id}")

    if choice == "a":
        for z in zip_files:
            process_zip(os.path.join(DATA_DIR, z), model_id)
    else:
        if not choice.isdigit():
            print("❌ 잘못된 입력")
            return

        idx = int(choice) - 1
        if idx < 0 or idx >= len(zip_files):
            print("❌ 잘못된 번호")
            return

        process_zip(os.path.join(DATA_DIR, zip_files[idx]), model_id)


if __name__ == "__main__":
    main()
