import os
import zipfile
import tempfile
import requests
import base64
from dotenv import load_dotenv
import urllib.parse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel

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

console = Console()


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
이 이미지는 전공 PPT 슬라이드 한 장이다.

이 슬라이드를 분석하여 README.md에 들어갈 설명을 작성하라.

출력 규칙:
- 반드시 Markdown 형식으로 작성한다.
- 제목은 "## {filename}" 형식으로 시작한다.
- 한국어로 작성한다.
- 불필요한 인사말, 메타 설명, 이모티콘은 쓰지 않는다.
- 코드 블록은 사용하지 않는다.

설명에는 다음을 포함한다:
- 슬라이드의 주제
- 도표나 그림의 의미
- 전공 ppt에 대한 자세한 설명
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
                        "image_url": {"url": image_data_url},
                    }
                ],
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1600,
    }

    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        json=payload,
        timeout=360,
    )

    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def md_image_path(filename: str) -> str:
    return "./" + urllib.parse.quote(filename)

# =============================
# zip 처리
# =============================
def process_zip(zip_path, model_id, merge_mode: bool):
    zip_name = os.path.splitext(os.path.basename(zip_path))[0]
    output_dir = os.path.join(RESULT_DIR, zip_name)
    os.makedirs(output_dir, exist_ok=True)

    console.print(
        Panel.fit(
            f"[bold cyan]📦 처리 시작[/bold cyan]\n[white]{zip_name}[/white]",
            title="ZIP",
        )
    )

    readme_path = os.path.join(output_dir, "README.md") if merge_mode else None

    if merge_mode:
        readme_file = open(readme_path, "w", encoding="utf-8")
        readme_file.write(f"# {zip_name}\n\n")

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)

        images = []
        for root, _, files in os.walk(tmp):
            for f in sorted(files):
                if f.lower().endswith(IMAGE_EXTS):
                    images.append(os.path.join(root, f))

        if not images:
            console.print("[yellow]⚠ 이미지가 없습니다.[/yellow]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            task = progress.add_task("이미지 처리 중...", total=len(images))

            for img_path in images:
                fname = os.path.basename(img_path)
                md_name = os.path.splitext(fname)[0] + ".md"
                md_path = os.path.join(output_dir, md_name)

                try:
                    text = describe_image(model_id, img_path)
                except Exception as e:
                    progress.console.print(f"  ❌ [red]{fname} 실패:[/red] {e}")
                    progress.advance(task)
                    continue

                if merge_mode:
                    # 이미지 복사
                    target_img = os.path.join(output_dir, fname)
                    with open(img_path, "rb") as src, open(target_img, "wb") as dst:
                        dst.write(src.read())
                        
                    img_url = md_image_path(fname)
                    readme_file.write(f"## {fname}\n\n")
                    readme_file.write(f"![{fname}]({img_url})\n\n")
                    readme_file.write(text.strip() + "\n\n---\n\n")

                else:
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(text.strip() + "\n")

                progress.console.print(f"  ✅ [green]{fname}[/green] 완료")
                progress.advance(task)

    if merge_mode:
        readme_file.close()
        console.print(f"\n📘 README 생성 완료 → {readme_path}")


# =============================
# 메인
# =============================
def main():
    if not os.path.isdir(DATA_DIR):
        console.print("[red]❌ data 폴더가 없습니다.[/red]")
        return

    os.makedirs(RESULT_DIR, exist_ok=True)

    zip_files = sorted(f for f in os.listdir(DATA_DIR) if f.lower().endswith(".zip"))

    if not zip_files:
        console.print("[red]❌ data 폴더에 zip 파일이 없습니다.[/red]")
        return

    console.print("\n[bold cyan]📦 처리할 ZIP 파일 목록[/bold cyan]")
    for i, name in enumerate(zip_files, 1):
        console.print(f"  [cyan]{i}[/cyan]. {name}")
    console.print("  [cyan]a[/cyan]. 전체 처리")

    choice = console.input("\n👉 ZIP 선택: ").strip().lower()

    console.print("\n📄 출력 방식 선택")
    console.print("  [1] 이미지별 .md 파일")
    console.print("  [2] 하나의 README.md 로 합치기")
    mode = console.input("👉 선택: ").strip()

    merge_mode = mode == "2"

    model_id = get_model_id()
    console.print(f"\n✅ 사용 중인 모델: [bold]{model_id}[/bold]\n")

    if choice == "a":
        for z in zip_files:
            process_zip(os.path.join(DATA_DIR, z), model_id, merge_mode)
    else:
        if not choice.isdigit():
            console.print("[red]❌ 잘못된 입력[/red]")
            return

        idx = int(choice) - 1
        if idx < 0 or idx >= len(zip_files):
            console.print("[red]❌ 잘못된 번호[/red]")
            return

        process_zip(os.path.join(DATA_DIR, zip_files[idx]), model_id, merge_mode)


if __name__ == "__main__":
    main()
