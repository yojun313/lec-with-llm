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
FORM_DIR = os.path.join(SCRIPT_DIR, "forms")

IMAGE_EXTS = (".png", ".jpg", ".jpeg")

console = Console()


# =============================
# Model auto-select
# =============================
def get_model_id():
    r = requests.get(f"{BASE_URL}/models", headers=HEADERS, timeout=10)
    r.raise_for_status()
    models = r.json().get("data", [])
    if not models:
        raise RuntimeError("No available models")
    return models[0]["id"]


# =============================
# Image → base64
# =============================
def image_to_data_url(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()

    ext = os.path.splitext(path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


# =============================
# PDF → images
# =============================
def extract_pdf_pages(pdf_path: str, output_dir: str):
    pages = convert_from_path(pdf_path, dpi=200)
    results = []

    base = os.path.splitext(os.path.basename(pdf_path))[0]
    for i, img in enumerate(pages, 1):
        name = f"{base}_page_{i:03d}.png"
        out = os.path.join(output_dir, name)
        img.save(out, "PNG")
        results.append(out)

    return results


# =============================
# LLM
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

규칙:
- Markdown 형식
- 제목은 "## {filename}"
- 한국어
- 인사말 / 메타 설명 / 이모지 금지
- 코드 블록 금지

포함 내용:
- 슬라이드 주제
- 그림/도표 설명
- 전공 관점의 자세한 해설
""".strip()
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_url(image_path)}
                    }
                ]
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1600,
    }

    r = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# =============================
# Collect images
# =============================
def collect_images(path: str, tmp: str):
    images = []

    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)

        for root, _, files in os.walk(tmp):
            if "__MACOSX" in root:
                continue
            for f in files:
                if f.startswith("._"):
                    continue
                if f.lower().endswith(IMAGE_EXTS):
                    images.append(os.path.join(root, f))

    elif path.lower().endswith(".pdf"):
        images = extract_pdf_pages(path, tmp)

    return sorted(images)


# =============================
# Export PDFs
# =============================
def export_pdf_both(md_path: str, output_dir: str, base_name: str):
    html_path = os.path.join(output_dir, f"{base_name}.html")

    css_v = os.path.join(FORM_DIR, "pdf_style_vertical.css")
    css_h = os.path.join(FORM_DIR, "pdf_style_horizontal.css")

    subprocess.run(
        [
            "pandoc",
            md_path,
            "-o", html_path,
            "--standalone",
            "--metadata", f"pagetitle={base_name}",
        ],
        check=True,
    )

    pdfkit.from_file(
        html_path,
        os.path.join(output_dir, f"{base_name}_vertical.pdf"),
        options={"enable-local-file-access": None, "user-style-sheet": css_v},
    )

    pdfkit.from_file(
        html_path,
        os.path.join(output_dir, f"{base_name}_horizontal.pdf"),
        options={"enable-local-file-access": None, "user-style-sheet": css_h},
    )


# =============================
# Main processing
# =============================
def process_input_file(path: str, model_id: str, merge_mode: bool, export_pdf_flag: bool):
    base = os.path.splitext(os.path.basename(path))[0]
    out_dir = os.path.join(RESULT_DIR, base)
    os.makedirs(out_dir, exist_ok=True)

    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    console.print(Panel.fit(f"Processing: {base}", title="INPUT"))

    md_path = os.path.join(out_dir, f"{base}.md")
    md = open(md_path, "w", encoding="utf-8") if merge_mode else None

    if merge_mode:
        md.write(f"# {base}\n\n")

    with tempfile.TemporaryDirectory() as tmp:
        images = collect_images(path, tmp)

        if not images:
            console.print("[yellow]No images found.[/yellow]")
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

            for img in images:
                name = os.path.basename(img)

                try:
                    text = describe_image(model_id, img)
                except Exception as e:
                    console.print(f"[red]Failed:[/red] {name} → {e}")
                    progress.advance(task)
                    continue

                dst = os.path.join(img_dir, name)
                with open(img, "rb") as s, open(dst, "wb") as d:
                    d.write(s.read())

                rel = "./images/" + urllib.parse.quote(name)

                if merge_mode:
                    md.write(f"## {name}\n\n")
                    md.write(
                        "<div class=\"slide\">\n"
                        "  <div class=\"slide-img\">\n"
                        f"    <img src=\"{rel}\" />\n"
                        "  </div>\n"
                        "  <div class=\"slide-text\">\n"
                    )

                    stripped = text.strip()
                    if stripped.startswith(f"## {name}"):
                        stripped = stripped[len(f"## {name}"):].lstrip()

                    md.write(stripped + "\n")
                    md.write("  </div>\n</div>\n\n")

                else:
                    with open(os.path.join(out_dir, f"{os.path.splitext(name)[0]}.md"), "w", encoding="utf-8") as f:
                        f.write(text)

                progress.advance(task)

    if md:
        md.close()

        if export_pdf_flag:
            export_pdf_both(md_path, out_dir, base)
            console.print("[green]PDF generated:[/green]")
            console.print(f" - {base}_vertical.pdf")
            console.print(f" - {base}_horizontal.pdf")

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
