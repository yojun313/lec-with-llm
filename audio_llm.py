import os
import json
import gc
import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from dotenv import load_dotenv

load_dotenv()

console = Console()

# ======================
# Paths
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio_data")
RESULT_DIR = os.path.join(BASE_DIR, "audio_result")
os.makedirs(RESULT_DIR, exist_ok=True)

# ======================
# Server config
# ======================
API_URL = os.getenv("AUDIO_LLM_URL", "")
TOKEN = os.getenv("TOKEN", "EMPTY")

HEADERS = {}
if TOKEN and TOKEN != "EMPTY":
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# ======================
# Core logic
# ======================
def transcribe_files(files: list[str], model_level: int, language: str, save_mode: str):
    if not files:
        console.print("[yellow]No audio files selected.[/]")
        return

    console.print(Panel.fit(
        f"Files: {len(files)}\n"
        f"Model level: {model_level}\n"
        f"Language: {language}\n"
        f"Output: {'text only' if save_mode == 'text' else 'text with timestamps'}",
        title="Whisper API Client",
        border_style="cyan"
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        task = progress.add_task("Transcribing...", total=len(files))

        for fname in files:
            audio_path = os.path.join(AUDIO_DIR, fname)
            base = os.path.splitext(fname)[0]

            if save_mode == "text":
                output_path = os.path.join(RESULT_DIR, f"{base}.txt")
            else:
                output_path = os.path.join(RESULT_DIR, f"{base}_with_time.txt")

            console.log(f"Uploading: {fname}")

            with open(audio_path, "rb") as f:
                files_payload = {
                    "file": (fname, f, "audio/mpeg")
                }

                payload = {
                    "option": json.dumps({
                        "language": language,
                        "model": model_level,
                        "pid": None
                    })
                }

                response = requests.post(
                    API_URL,
                    headers=HEADERS,
                    files=files_payload,
                    data=payload,
                    timeout=60 * 60,
                )

            if response.status_code != 200:
                console.print(f"[red]Failed: {fname} ({response.status_code})[/]")
                console.print(response.text)
                progress.advance(task)
                continue

            result = response.json()

            content = (
                result.get("text", "")
                if save_mode == "text"
                else result.get("text_with_time", "")
            )

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            progress.advance(task)

    console.print("\n[bold green]All selected files processed successfully.[/]")
    gc.collect()


# ======================
# Entry
# ======================
def main():
    console.print(Panel.fit("Whisper API Client", style="bold cyan"))

    if not os.path.isdir(AUDIO_DIR):
        console.print("[red]audio_data folder not found.[/red]")
        return

    mp3_files = sorted(f for f in os.listdir(AUDIO_DIR) if f.lower().endswith(".mp3"))

    if not mp3_files:
        console.print("[red]No mp3 files found in audio_data.[/red]")
        return

    # 파일 선택 UI
    console.print("\n[bold cyan]Available audio files[/bold cyan]")
    for i, name in enumerate(mp3_files, 1):
        console.print(f"  [cyan]{i}[/cyan]. {name}")
    console.print("  [cyan]a[/cyan]. Process all")

    choice = console.input("\nSelect file(s): ").strip().lower()

    if choice == "a":
        selected_files = mp3_files
    else:
        if not choice.isdigit():
            console.print("[red]Invalid selection.[/red]")
            return

        idx = int(choice) - 1
        if idx < 0 or idx >= len(mp3_files):
            console.print("[red]Invalid number.[/red]")
            return

        selected_files = [mp3_files[idx]]

    # options
    model_level = IntPrompt.ask(
        "Model level (1=small, 2=medium, 3=large)",
        choices=["1", "2", "3"],
        default=2,
    )

    language = Prompt.ask(
        "Language code (auto / ko / en / ja ...)",
        default="auto",
    )
    
    output_mode = Prompt.ask(
        "Output format (1 = text only, 2 = text with timestamps)",
        choices=["1", "2"],
        default="1"
    )

    save_mode = "text" if output_mode == "1" else "time"

    transcribe_files(selected_files, model_level, language, save_mode)


if __name__ == "__main__":
    main()
