# Lecture note & Audio Processing Tools (LLM-based)

This repository provides two command-line tools for lecture processing:

1. **Lecture note Slide Description Generator**

   - Converts slide images inside ZIP files or PDF files into Markdown descriptions
   - Optionally exports formatted PDF files (vertical & horizontal layouts)

2. **Audio Transcription Tool**
   - Sends audio files to a Whisper-compatible API
   - Saves transcriptions as text files

Both tools support **OpenAI APIs** or **OpenAI-compatible custom servers**, selectable via environment variables.

---

## Requirements

### System Requirements

- Python **3.9+**
- `pandoc` (Markdown → HTML)
- `wkhtmltopdf` (HTML → PDF)
- `poppler` (PDF → images)

### Install system dependencies

#### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y pandoc wkhtmltopdf poppler-utils
```

#### macOS (Homebrew)

```bash
brew install pandoc wkhtmltopdf poppler
```

Make sure `wkhtmltopdf` is available in your PATH:

```bash
wkhtmltopdf --version
```

---

## Python Dependencies

Install required Python packages:

```bash
pip install -r requirements.txt
```

### `requirements.txt`

```txt
requests
python-dotenv
rich
pdf2image
pdfkit
Pillow
```

---

## Environment Configuration

Create a `.env` file in the project root. (Check .env.example)

---

### LLM Provider Selection

```env
LLM_PROVIDER=openai
```

or

```env
LLM_PROVIDER=custom
```

---

## OpenAI Configuration (when `LLM_PROVIDER=openai`)

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o
```

- `OPENAI_MODEL` examples:

  - `gpt-4o`
  - `gpt-4o-mini`
  - `gpt-4.1`

---

## Custom Server Configuration (when `LLM_PROVIDER=custom`)

```env
PPT_LLM_URL=http://localhost:8000/v1
CUSTOM_TOKEN=your_custom_token_here
```

- Server must be **OpenAI-compatible**
- Must support `/v1/chat/completions`
- Optionally accept `Authorization: Bearer <token>`

---

## Project Structure

```
project/
├── ppt_llm.py
├── audio_llm.py
├── forms/
│   ├── pdf_style_vertical.css
│   └── pdf_style_landscape.css
├── ppt_data/
│   ├── *.zip
│   └── *.pdf
├── audio_data/
│   └── *.mp3
├── ppt_result/
├── audio_result/
├── .env
├── requirements.txt
└── README.md
```

---

# Part 1. PPT Slide Description Tool

This tool processes slide images (ZIP or PDF) and generates structured Markdown descriptions using an LLM.

---

## Input Formats

Supported input types inside `ppt_data/`:

- `.zip` → archive containing slide images
- `.pdf` → multipage PDF (each page converted to image)

Supported image formats:

- `.png`
- `.jpg`
- `.jpeg`

---

## Running the Tool

```bash
python ppt_llm.py
```

---

## Step 1: Select Input Files

You will see:

```
Available input files
1. lecture1.zip
2. lecture2.pdf
a. Process all
```

Options:

- Enter a number → process one file
- Enter `a` → process all files

---

## Step 2: Choose Output Mode

```
1. Merge into one markdown
2. One .md per image
```

### Option 1 — Merge into one Markdown (recommended)

Creates:

```
ppt_result/lecture1/
├── lecture1.md
├── images/
│   ├── slide01.png
│   ├── slide02.png
```

Markdown layout:

```md
## slide01.png

![slide01.png](./images/slide01.png)

(description)

---
```

---

### Option 2 — One Markdown per image

Creates:

```
ppt_result/lecture1/
├── slide01.md
├── slide02.md
```

---

## Optional: Export PDF

When merge mode is selected, you will be prompted:

```
Export PDF as well? (Y/n)
```

If enabled, **two PDFs are generated**:

### Output files

```
ppt_result/lecture1/
├── lecture1_v.pdf   # vertical layout
├── lecture1_h.pdf   # horizontal layout
```

### Layout explanation

#### Vertical PDF (`*_v.pdf`)

- Image on top
- Description below
- Suitable for reading or printing

#### Horizontal PDF (`*_h.pdf`)

- A4 landscape
- Image on the left
- Description on the right
- Ideal for slide review

Layout behavior is controlled via:

```
forms/pdf_style_vertical.css
forms/pdf_style_landscape.css
```

---

## PDF Generation Notes

- Markdown → HTML via **pandoc**
- HTML → PDF via **wkhtmltopdf**
- Local image access enabled automatically
- Temporary HTML files are deleted after PDF generation

---

# Part 2. Audio Transcription Tool

This tool sends audio files to a Whisper-compatible API and saves transcription results.

---

## Input Directory

Place audio files in:

```
audio_data/
```

Supported formats:

- `.mp3`

---

## Run the Tool

```bash
python audio_llm.py
```

---

## Step 1: Select Audio Files

```
1. lecture1.mp3
2. lecture2.mp3
a. Process all
```

---

## Step 2: Choose Model Size

```
1 = small
2 = medium
3 = large
```

This value is forwarded to the Whisper-compatible server.

---

## Step 3: Select Language

Examples:

```
auto
ko
en
ja
```

---

## Step 4: Output Format

```
1 = text only
2 = text with timestamps
```

---

## Output Files

### Text only

```
audio_result/lecture1.txt
```

### With timestamps

```
audio_result/lecture1_with_time.txt
```
