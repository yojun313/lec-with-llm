import os
import zipfile
import tempfile
import requests
import base64
import urllib.parse
import subprocess
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel

# =============================
# Environment
# =============================
load_dotenv()

BASE_URL = os.getenv("PPT_LLM_URL", "").rstrip("/")
TOKEN = os.getenv("TOKEN", "EMPTY")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "ppt_data")
RESULT_DIR = os.path.join(SCRIPT_DIR, "ppt_result")

IMAGE_EXTS = (".png", ".jpg", ".jpeg")

console = Console()


# =============================
# Model auto-select
# =============================
def get_model_id():
    resp = requests.get(f"{BASE_URL}/models", headers=HEADERS, timeout=10)
    resp.raise_for_status()

    models = resp.json().get("data", [])
    if not models:
        raise RuntimeError("No available models.")

    return models[0]["id"]


# =============================
# Image -> base64 data URL
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
# Generate slide description
# =============================
def describe_image(model_id: str, image_path: str) -> str:
    filename = os.path.basename(image_path)
    image_data_url = image_to_data_url(image_path)

    prompt = f"""
        이 이미지는 전공 PPT 슬라이드 한 장이다.

        이 슬라이드를 분석하여 Markdown 문서에 들어갈 설명을 작성하라.

        출력 규칙:
        - 반드시 Markdown 형식으로 작성한다.
        - 제목은 "## {filename}" 형식으로 시작한다.
        - 한국어로 작성한다.
        - 불필요한 인사말, 메타 설명, 이모티콘은 쓰지 않는다.
        - 코드 블록은 사용하지 않는다.

        설명에는 다음을 포함한다:
        - 슬라이드의 주제
        - 도표나 그림의 의미
        - 전공 PPT에 대한 자세한 설명
    """.strip()

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
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


def md_image_path_in_images_dir(filename: str) -> str:
    # README/markdown is in output_dir; images will be in output_dir/images/
    return "./images/" + urllib.parse.quote(filename)


# =============================
# Markdown -> PDF (Pandoc)
# =============================
def export_pdf(md_path: str, output_pdf: str, resource_dir: str):
    cmd = [
        "pandoc",
        md_path,
        "-o", output_pdf,
        "--pdf-engine=wkhtmltopdf",
        "--resource-path", resource_dir,
        "--enable-local-file-access",
        "--metadata", "pagetitle=",
    ]
    subprocess.run(cmd, check=True)

# =============================
# Process ZIP
# =============================
def process_zip(zip_path: str, model_id: str, merge_mode: bool, export_pdf_flag: bool):
    zip_name = os.path.splitext(os.path.basename(zip_path))[0]
    output_dir = os.path.join(RESULT_DIR, zip_name)
    os.makedirs(output_dir, exist_ok=True)

    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    console.print(
        Panel.fit(
            f"Processing ZIP: {zip_name}",
            title="ZIP",
        )
    )

    # In merge mode, write a single markdown file named after the ppt directory (zip_name)
    merged_md_path = os.path.join(output_dir, f"{zip_name}.md") if merge_mode else None

    if merge_mode:
        md_file = open(merged_md_path, "w", encoding="utf-8")
        md_file.write(f"# {zip_name}\n\n")

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)

        images = []
        for root, _, files in os.walk(tmp):
            for f in sorted(files):
                if f.lower().endswith(IMAGE_EXTS):
                    images.append(os.path.join(root, f))

        if not images:
            console.print("[yellow]No images found in the ZIP.[/yellow]")
            if merge_mode:
                md_file.close()
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            task = progress.add_task("Processing images...", total=len(images))

            for img_path in images:
                fname = os.path.basename(img_path)
                md_name = os.path.splitext(fname)[0] + ".md"
                md_path = os.path.join(output_dir, md_name)

                try:
                    text = describe_image(model_id, img_path)
                except Exception as e:
                    progress.console.print(f"[red]Failed:[/red] {fname} -> {e}")
                    progress.advance(task)
                    continue

                if merge_mode:
                    # Copy image into output_dir/images/
                    target_img = os.path.join(images_dir, fname)
                    with open(img_path, "rb") as src, open(target_img, "wb") as dst:
                        dst.write(src.read())

                    img_url = md_image_path_in_images_dir(fname)

                    md_file.write(f"## {fname}\n\n")
                    md_file.write(f"![{fname}]({img_url})\n\n")

                    # The model output already starts with "## {filename}" per prompt.
                    # To avoid duplicated headings, strip the first heading if present.
                    stripped = text.strip()
                    if stripped.startswith(f"## {fname}"):
                        stripped = stripped[len(f"## {fname}"):].lstrip()
                    md_file.write(stripped + "\n\n---\n\n")

                else:
                    # Per-image markdown mode (no merged md). Keep original behavior.
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(text.strip() + "\n")

                progress.console.print(f"[green]Done:[/green] {fname}")
                progress.advance(task)

    if merge_mode:
        md_file.close()
        console.print(f"Markdown generated: {merged_md_path}")

        if export_pdf_flag:
            pdf_path = os.path.join(output_dir, f"{zip_name}.pdf")
            try:
                export_pdf(merged_md_path, pdf_path, output_dir)
                console.print(f"PDF generated: {pdf_path}")
            except FileNotFoundError:
                console.print("[red]pandoc not found. Install pandoc to export PDF.[/red]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]PDF export failed:[/red] {e}")


# =============================
# Main
# =============================
def main():
    if not os.path.isdir(DATA_DIR):
        console.print("[red]ppt_data folder not found.[/red]")
        return

    os.makedirs(RESULT_DIR, exist_ok=True)

    zip_files = sorted(f for f in os.listdir(DATA_DIR) if f.lower().endswith(".zip"))

    if not zip_files:
        console.print("[red]No zip files found in ppt_data.[/red]")
        return

    console.print("\n[bold cyan]Available ZIP files[/bold cyan]")
    for i, name in enumerate(zip_files, 1):
        console.print(f"  [cyan]{i}[/cyan]. {name}")
    console.print("  [cyan]a[/cyan]. Process all")

    choice = console.input("\nSelect ZIP: ").strip().lower()

    console.print("\nOutput format:")
    console.print("  [1] One .md file per image")
    console.print("  [2] Merge into a single markdown file")
    mode = console.input("Select: ").strip()

    merge_mode = mode == "2"

    export_pdf_flag = False
    if merge_mode:
        pdf_choice = console.input("\nExport PDF as well? (y/n) [n]: ").strip().lower()
        export_pdf_flag = pdf_choice == "y"

    try:
        model_id = get_model_id()
    except Exception as e:
        console.print(f"[red]Failed to load model list:[/red] {e}")
        return

    console.print(f"\nUsing model: [bold]{model_id}[/bold]\n")

    if choice == "a":
        for z in zip_files:
            process_zip(os.path.join(DATA_DIR, z), model_id, merge_mode, export_pdf_flag)
    else:
        if not choice.isdigit():
            console.print("[red]Invalid input.[/red]")
            return

        idx = int(choice) - 1
        if idx < 0 or idx >= len(zip_files):
            console.print("[red]Invalid selection.[/red]")
            return

        process_zip(os.path.join(DATA_DIR, zip_files[idx]), model_id, merge_mode, export_pdf_flag)


if __name__ == "__main__":
    main()
