import os
import gc
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.prompt import IntPrompt
from faster_whisper import WhisperModel

# ======================
# 환경 설정
# ======================
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

console = Console()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio_data")
RESULT_DIR = os.path.join(BASE_DIR, "audio_result")
MODEL_DIR = os.getenv("MODEL_PATH", os.path.join(BASE_DIR, "models"))

os.makedirs(RESULT_DIR, exist_ok=True)

WHISPER_MODEL_MAP = {
    1: {"name": "faster-whisper-small", "compute": "int8_float16"},
    2: {"name": "faster-whisper-medium", "compute": "int8_float16"},
    3: {"name": "faster-whisper-large-v3", "compute": "float16"},
}

_whisper_models = {}

# ======================
# Whisper 모델 로딩
# ======================
def get_whisper_model(level: int):
    if level not in WHISPER_MODEL_MAP:
        level = 2

    cfg = WHISPER_MODEL_MAP[level]
    key = f"{cfg['name']}::{cfg['compute']}"

    if key not in _whisper_models:
        console.print(f"[cyan]모델 로딩:[/] {cfg['name']} ({cfg['compute']})")
        _whisper_models[key] = WhisperModel(
            os.path.join(MODEL_DIR, cfg["name"]),
            device="cuda",
            compute_type=cfg["compute"],
            local_files_only=True,
        )

    return _whisper_models[key]


# ======================
# 텍스트 포맷
# ======================
def format_paragraphs(segments, max_len=120):
    paragraphs = []
    buf = ""

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        if len(buf) + len(text) <= max_len:
            buf += " " + text
        else:
            paragraphs.append(buf.strip())
            buf = text

    if buf:
        paragraphs.append(buf.strip())

    return "\n\n".join(paragraphs)


def format_with_timestamps(segments):
    def ts(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    return "\n".join(
        f"[{ts(seg.start)} - {ts(seg.end)}] {seg.text.strip()}"
        for seg in segments
    )


# ======================
# 메인 처리
# ======================
def transcribe_folder(folder: str, model_level: int):
    if not os.path.isdir(folder):
        console.print(f"[red]audio_data 폴더가 없습니다:[/] {folder}")
        return

    mp3_files = sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith(".mp3")
    )

    if not mp3_files:
        console.print("[yellow]audio_data 안에 mp3 파일이 없습니다.[/]")
        return

    model = get_whisper_model(model_level)

    console.print(Panel.fit(
        f"입력 폴더: audio_data\n"
        f"출력 폴더: audio_result\n"
        f"파일 수: {len(mp3_files)}\n"
        f"모델: {WHISPER_MODEL_MAP[model_level]['name']}",
        title="Whisper Batch",
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

        task = progress.add_task("음성 변환 중...", total=len(mp3_files))

        for fname in mp3_files:
            audio_path = os.path.join(folder, fname)
            base = os.path.splitext(fname)[0]

            out_txt = os.path.join(RESULT_DIR, f"{base}.txt")
            out_ts = os.path.join(RESULT_DIR, f"{base}_with_time.txt")

            console.log(f"🎧 처리 중: {fname}")

            segments, info = model.transcribe(
                audio_path,
                language="ko",
                beam_size=1 if model_level < 3 else 5,
                vad_filter=True,
            )

            segments = list(segments)

            with open(out_txt, "w", encoding="utf-8") as f:
                f.write(format_paragraphs(segments))

            with open(out_ts, "w", encoding="utf-8") as f:
                f.write(format_with_timestamps(segments))

            progress.advance(task)

    console.print("\n[bold green]✅ 모든 파일 처리 완료[/]")
    gc.collect()


# ======================
# Entry
# ======================
def main():
    console.print(Panel.fit("Whisper Batch Transcriber", style="bold cyan"))

    model_level = IntPrompt.ask(
        "모델 선택 (1=small, 2=medium, 3=large)",
        choices=["1", "2", "3"],
        default=2,
    )

    transcribe_folder(AUDIO_DIR, model_level)


if __name__ == "__main__":
    main()
