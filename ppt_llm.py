import os
import zipfile
import tempfile
import requests
import base64
import urllib.parse
import subprocess
from pdf2image import convert_from_path
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
PDF_EXTS = (".pdf",)

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
# Image → base64
# =============================
def image_to_data_url(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()

    encoded = base64.b64encode(raw).decode("utf-8")

    ext = os.path.splitext(path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"

    return f"data:{mime};base64,{encoded}"


# =============================
# PDF → image pages
# =============================
def extract_pdf_pages(pdf_path: str, output_dir: str) -> list[str]:
    images = convert_from_path(pdf_path, dpi=200)

    paths = []
    base = os.path.splitext(os.path.basename(pdf_path))[0]

    for i, img in enumerate(images, start=1):
        name = f"{base}_page_{i:03d}.png"
        out = os.path.join(output_dir, name)
        img.save(out, "PNG")
        paths.append(out)

    return paths


# =============================
# LLM call
# =============================
def describe_image(model_id: str, image_path: str) -> str:
    filename = os.path.basename(image_path)

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
                            이 이미지는 전공 PPT 슬라이드 한 장이다.

                            이 슬라이드를 분석하여 Markdown 문서에 들어갈 설명을 작성하라.

                            출력 규칙:
                            - 반드시 Markdown 형식
                            - 제목은 "## {filename}" 형식
                            - 한국어
                            - 인사말, 메타 설명, 이모티콘 금지
                            - 코드 블록 금지

                            포함할 내용:
                            - 슬라이드 주제
                            - 그림 / 도표 설명
                            - 전공 관점에서의 매우 자세한 설명
                        """.strip()
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
        "temperature": 0.3,
        "max_tokens": 1600,
    }

    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        json=payload,
        timeout=360,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# =============================
# Image collection
# =============================
def collect_images(input_path: str, tmp_dir: str) -> list[str]:
    images = []

    if input_path.lower().endswith(".zip"):
        with zipfile.ZipFile(input_path) as z:
            z.extractall(tmp_dir)

        for root, _, files in os.walk(tmp_dir):
            if "__MACOSX" in root:
                continue
            for f in files:
                if f.startswith("._"):
                    continue
                if f.lower().endswith(IMAGE_EXTS):
                    images.append(os.path.join(root, f))

    elif input_path.lower().endswith(".pdf"):
        images = extract_pdf_pages(input_path, tmp_dir)

    return sorted(images)


# =============================
# Markdown → PDF
# =============================
def export_pdf(md_path: str, output_pdf: str):
    html_path = md_path.replace(".md", ".html")

    css_path = os.path.join(os.path.dirname(__file__), "pdf_style.css")

    subprocess.run(
        ["pandoc", md_path, "-o", html_path, "--standalone", "--css", css_path],
        check=True,
    )

    import pdfkit
    pdfkit.from_file(
        html_path,
        output_pdf,
        options={"enable-local-file-access": None, "quiet": ""},
    )


# =============================
# Main processing
# =============================
def process_input_file(input_path: str, model_id: str, merge_mode: bool, export_pdf_flag: bool):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_dir = os.path.join(RESULT_DIR, base_name)
    os.makedirs(output_dir, exist_ok=True)

    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    console.print(Panel.fit(f"Processing: {base_name}", title="INPUT"))

    merged_md_path = os.path.join(output_dir, f"{base_name}.md") if merge_mode else None
    md_fp = open(merged_md_path, "w", encoding="utf-8") if merge_mode else None

    if merge_mode:
        md_fp.write(f"# {base_name}\n\n")

    with tempfile.TemporaryDirectory() as tmp:
        images = collect_images(input_path, tmp)

        if not images:
            console.print("[yellow]No images found.[/yellow]")
            if md_fp:
                md_fp.close()
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

                try:
                    text = describe_image(model_id, img_path)
                except Exception as e:
                    console.print(f"[red]Failed:[/red] {fname} → {e}")
                    progress.advance(task)
                    continue

                # copy image
                dst_img = os.path.join(images_dir, fname)
                with open(img_path, "rb") as src, open(dst_img, "wb") as dst:
                    dst.write(src.read())

                rel_img = "./images/" + urllib.parse.quote(fname)

                if merge_mode:
                    md_fp.write(f"## {fname}\n\n")
                    md_fp.write(f"![{fname}]({rel_img})\n\n")

                    stripped = text.strip()
                    if stripped.startswith(f"## {fname}"):
                        stripped = stripped[len(f"## {fname}"):].lstrip()

                    md_fp.write(stripped + "\n\n---\n\n")

                else:
                    md_path = os.path.join(output_dir, f"{os.path.splitext(fname)[0]}.md")
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(text)

                progress.advance(task)

    if md_fp:
        md_fp.close()

        if export_pdf_flag:
            pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
            export_pdf(merged_md_path, pdf_path)
            console.print(f"[green]PDF generated:[/green] {pdf_path}")


# =============================
# CLI
# =============================

def clear_result_dir():
    if not os.path.isdir(RESULT_DIR):
        console.print("[yellow]Result directory does not exist.[/yellow]")
        return

    items = os.listdir(RESULT_DIR)

    if not items:
        console.print("[green]Result directory is already empty.[/green]")
        return

    console.print("\n[bold red]Files in result directory:[/bold red]")
    for name in items:
        console.print(f"  - {name}")

    confirm = console.input("\nDelete ALL files above? (y/N): ").strip().lower()
    if confirm != "y":
        console.print("[yellow]Cancelled.[/yellow]")
        return

    for name in items:
        path = os.path.join(RESULT_DIR, name)
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            console.print(f"[red]Failed to remove {name}: {e}[/red]")

    console.print("[green]Result directory cleared.[/green]")

def main():
    os.makedirs(RESULT_DIR, exist_ok=True)

    while True:
        console.print("\n[bold cyan]Main Menu[/bold cyan]")
        console.print("  [1] Start processing")
        console.print("  [2] Clear result directory")
        console.print("  [q] Quit")

        choice = console.input("\nSelect: ").strip().lower()

        if choice == "q":
            return

        if choice == "2":
            clear_result_dir()
            continue

        if choice != "1":
            console.print("[red]Invalid selection.[/red]")
            continue

        # =============================
        # START PROCESSING
        # =============================

        if not os.path.isdir(DATA_DIR):
            console.print("[red]ppt_data folder not found.[/red]")
            return

        input_files = sorted(
            f for f in os.listdir(DATA_DIR)
            if f.lower().endswith((".zip", ".pdf"))
        )

        if not input_files:
            console.print("[red]No input files found.[/red]")
            continue

        console.print("\n[bold cyan]Available input files[/bold cyan]")
        for i, name in enumerate(input_files, 1):
            console.print(f"  [cyan]{i}[/cyan]. {name}")
        console.print("  [cyan]a[/cyan]. Process all")

        choice = console.input("\nSelect file(s): ").strip().lower()

        if choice != "a" and not choice.isdigit():
            console.print("[red]Invalid selection.[/red]")
            continue

        console.print("\nOutput format:")
        console.print("  [1] Merge into one markdown (default)")
        console.print("  [2] One .md per image")

        mode = console.input("Select [1]: ").strip()
        merge_mode = (mode == "" or mode == "1")

        export_pdf_flag = False
        if merge_mode:
            pdf_choice = console.input("Export PDF as well? (Y/n): ").strip().lower()
            export_pdf_flag = (pdf_choice == "" or pdf_choice == "y")

        model_id = get_model_id()
        console.print(f"\nUsing model: [bold]{model_id}[/bold]\n")

        targets = (
            input_files
            if choice == "a"
            else [input_files[int(choice) - 1]]
        )

        for file in targets:
            process_input_file(
                os.path.join(DATA_DIR, file),
                model_id,
                merge_mode,
                export_pdf_flag,
            )

if __name__ == "__main__":
    main()
