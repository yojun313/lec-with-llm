# PPT & Audio Processing Tools for lectures

This repository provides two command-line tools:

1. **PPT Slide Description Generator**
   Converts slide images inside ZIP files or PDF file into Markdown descriptions and PDF with description.

2. **Audio Transcription Client**
   Sends audio files to a Whisper-compatible API and saves transcriptions as text files.

Both tools communicate with external model servers defined via environment variables.

---

## Requirements

### System

- Python 3.9+
- `pandoc` (required for PDF export)
- `wkhtmltopdf` (used internally via `pdfkit`)

### Python dependencies

Install required packages:

```bash
pip install -r requirements.txt
```

### System package dependencies

Install required packages:

```bash
sudo apt install -y pandoc wkhtmltopdf poppler-utils (linux)
brew install pandoc wkhtmltopdf poppler (mac)
```

Make sure `wkhtmltopdf` is installed and available in your PATH.

---

## Environment Configuration

Create a `.env` file in the project root:

```env
PPT_LLM_URL=http://localhost:8000/v1 (Compatible with OpenAI API)
AUDIO_LLM_URL=http://localhost:8001
CUSTOM_TOKEN=EMPTY
```

### Variables

- **PPT_LLM_URL**
  Base URL of the vision-language model server.

- **AUDIO_LLM_URL**
  Base URL of the Whisper transcription server.

- **CUSTOM_TOKEN**
  Authorization CUSTOM_TOKEN if required by the server.
  Use `EMPTY` if authentication is not needed.

---

## Directory Structure

```
project/
├── ppt_processor.py
├── audio_transcriber.py
├── ppt_data/
│   └── *.zip
│   └── *.pdf
├── audio_data/
│   └── *.mp3
├── ppt_result/
├── audio_result/
├── pdf_style.css
├── .env
```

---

# Part 1. PPT Slide Description Tool

This tool processes (ZIP files containing slide images or PDF files) and generates Markdown descriptions.
Optionally, the Markdown can be converted into a PDF.

---

## Input Format

Each ZIP or PDF file inside `ppt_data/` should contain slide images:

```
ppt_data/
└── lecture1.zip
│   ├── slide01.jpg
│   ├── slide02.png
└── lecture1.pdf
```

Supported image formats:

- `.jpg`
- `.jpeg`
- `.png`

---

## Running the Tool

```bash
python ppt_llm.py
```

---

## Step 1: Select Input File

You will see a list of available input files found in the `ppt_data` directory:

```
Available input files
1. lecture1.zip
2. lecture2.pdf
3. slides_week3.zip
a. Process all
```

You can choose one of the following options:

- Enter a **number** to process a single file
  (ZIP or PDF)
- Enter **`a`** to process all listed files

### Supported input formats

- `.zip` — archive containing slide images
- `.pdf` — multi-page PDF (each page is automatically converted to an image)

Both formats are processed in the same way:
each page or image is analyzed and converted into structured Markdown content.

---

## Step 2: Choose Output Mode

```
1. One .md file per image
2. Merge into a single markdown file
```

### Option 1 — Per-image Markdown

Each slide generates its own `.md` file.

```
ppt_result/lecture1/
├── slide01.md
├── slide02.md
```

---

### Option 2 — Merged Markdown

All slides are merged into a single file:

```
ppt_result/lecture1/
├── lecture1.md
├── images/
│   ├── slide01.jpg
│   ├── slide02.jpg
```

The markdown layout is:

```md
## slide01.jpg

![slide01.jpg](./images/slide01.jpg)

(description)

---
```

---

## Optional: Export PDF

If merge mode is selected, you will be asked:

```
Export PDF as well? (y/n)
```

When enabled:

- Markdown → HTML (via pandoc)
- HTML → PDF (via wkhtmltopdf)
- Output:

  ```
  ppt_result/lecture1/lecture1.pdf
  ```

### Notes

- Images are embedded using local file access.
- Styling is controlled by `pdf_style.css`.
- Large images may appear scaled depending on CSS.

---

# Part 2. Audio Transcription Tool

This tool uploads audio files to a Whisper-compatible API and saves transcription results.

---

## Input Directory

Place audio files in:

```
audio_data/
```

Supported format:

- `.mp3`

---

## Run the Tool

```bash
python audio_llm.py
```

---

## Step 1: Select Audio Files

The program lists available files:

```
1. lecture1.mp3
2. lecture2.mp3
a. Process all
```

You can:

- Enter a number to process one file
- Enter `a` to process all files

---

## Step 2: Choose Model Level

```
1 = small
2 = medium
3 = large
```

This value is forwarded to the Whisper API.

---

## Step 3: Choose Language

Example inputs:

```
auto
ko
en
ja
```

---

## Step 4: Choose Output Format

```
1 = text only
2 = text with timestamps
```

### Output behavior

#### Option 1 — Text only

Creates:

```
audio_result/filename.txt
```

#### Option 2 — Text with timestamps

Creates:

```
audio_result/filename_with_time.txt
```

If the API does not return timestamped text, the tool automatically falls back to plain text.

---

## Output Example

```
audio_result/
├── lecture1.txt
├── lecture2_with_time.txt
```
