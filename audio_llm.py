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
# Main processing
# ======================
def transcribe_folder(folder: str, model_level: int, language: str):
    if not os.path.isdir(folder):
        console.print(f"[red]audio_data folder not found:[/] {folder}")
        return

    mp3_files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".mp3"))

    if not mp3_files:
        console.print("[yellow]No mp3 files found in audio_data[/]")
        return

    console.print(Panel.fit(
        f"Input folder: audio_data\n"
        f"Output folder: audio_result\n"
        f"Files: {len(mp3_files)}\n"
        f"Model level: {model_level}\n"
        f"Language: {language}",
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

        task = progress.add_task("Transcribing...", total=len(mp3_files))

        for fname in mp3_files:
            audio_path = os.path.join(folder, fname)
            base = os.path.splitext(fname)[0]

            out_txt = os.path.join(RESULT_DIR, f"{base}_text.txt")
            out_ts = os.path.join(RESULT_DIR, f"{base}_text_with_time.txt")

            console.log(f"Uploading: {fname}")

            with open(audio_path, "rb") as f:
                files = {
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
                    files=files,
                    data=payload,
                    timeout=60 * 60,
                )

            if response.status_code != 200:
                console.print(f"[red]Failed: {fname} ({response.status_code})[/]")
                console.print(response.text)
                progress.advance(task)
                continue

            result = response.json()

            with open(out_txt, "w", encoding="utf-8") as f:
                f.write(result.get("text", ""))

            with open(out_ts, "w", encoding="utf-8") as f:
                f.write(result.get("text_with_time", ""))

            progress.advance(task)

    console.print("\n[bold green]All audio files processed successfully.[/]")
    gc.collect()


# ======================
# Entry
# ======================
def main():
    console.print(Panel.fit("Whisper API Client", style="bold cyan"))

    model_level = IntPrompt.ask(
        "Model level (1=small, 2=medium, 3=large)",
        choices=["1", "2", "3"],
        default=2,
    )

    language = Prompt.ask(
        "Language code (auto / ko / en / ja ...)",
        default="auto",
    )

    transcribe_folder(AUDIO_DIR, model_level, language)


if __name__ == "__main__":
    main()
