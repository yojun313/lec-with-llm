# Lecture Note & Audio Processing Tools (LLM-based)

This repository provides two command-line tools for lecture processing:

1. **Lecture Note Slide Description Generator**
   - Converts lecture slides from **ZIP / PDF / PPT / PPTX** into structured Markdown descriptions
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
- `LibreOffice` (PPT -> PDF) 

---

### Install system dependencies

#### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y \
  pandoc \
  wkhtmltopdf \
  poppler-utils \
  libreoffice
````

#### macOS (Homebrew)

```bash
brew install pandoc wkhtmltopdf poppler libreoffice
```

Verify required binaries:

```bash
pandoc --version
wkhtmltopdf --version
soffice --version
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

Create a `.env` file in the project root.
Refer to `.env.example` if provided.

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

## OpenAI Configuration (`LLM_PROVIDER=openai`)

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o
```

Supported model examples:

* `gpt-4o`
* `gpt-4o-mini`
* `gpt-4.1`

---

## Custom Server Configuration (`LLM_PROVIDER=custom`)

```env
PPT_LLM_URL=http://localhost:8000/v1
CUSTOM_TOKEN=your_custom_token_here
```

Requirements for custom server:

* OpenAI-compatible API
* Must support `/v1/chat/completions`
* Should accept `Authorization: Bearer <token>`

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
│   ├── *.pdf
│   ├── *.ppt
│   └── *.pptx
├── audio_data/
│   └── *.mp3
├── ppt_result/
├── audio_result/
├── .env
├── requirements.txt
└── README.md
```

---

# Part 1. Lecture Slide Description Tool

This tool analyzes lecture slides and generates detailed Markdown explanations using an LLM.

---

## Supported Input Formats

Place input files inside `ppt_data/`.

### Supported file types

| Type             | Description                                    |
| ---------------- | ---------------------------------------------- |
| `.zip`           | ZIP archive containing slide images            |
| `.pdf`           | Multi-page PDF (each page becomes one slide)   |
| `.ppt` / `.pptx` | PowerPoint files (converted to PDF internally) |

### Supported image formats (inside ZIP / PDF conversion)

* `.png`
* `.jpg`
* `.jpeg`

---

## PPT / PPTX Processing Flow

When a PowerPoint file is provided:

```
.ppt / .pptx
   ↓ (LibreOffice / soffice)
PDF
   ↓ (poppler + pdf2image)
PNG images (one per slide)
   ↓
LLM-based slide description
```

* Animations and transitions are flattened
* Only the final visual state of each slide is analyzed

---

## Running the Tool

```bash
python ppt_llm.py
```

---

## Step 1: Select Input Files

Example:

```
Available input files
1. lecture1.zip
2. lecture2.pdf
3. lecture3.pptx
a. Process all
```

Options:

* Enter a number → process a single file
* Enter `a` → process all files

---

## Step 2: Choose Output Mode

```
1. Merge into one markdown (default)
2. One .md per image
```

---

### Option 1 — Merge into One Markdown (Recommended)

Creates:

```
ppt_result/lecture1/
├── lecture1.md
├── images/
│   ├── slide_001.png
│   ├── slide_002.png
```

Markdown structure:

```md
## slide_001.png

![slide_001.png](./images/slide_001.png)

(detailed description)

---
```

---

### Option 2 — One Markdown per Slide

Creates:

```
ppt_result/lecture1/
├── slide_001.md
├── slide_002.md
```

---

## Optional: Export PDF

Available only in **merge mode**.

Prompt:

```
Export PDF as well? (Y/n)
```

If enabled, **two PDF files are generated**.

---

### Output Files

```
ppt_result/lecture1/
├── lecture1_v.pdf   # vertical layout
├── lecture1_h.pdf   # horizontal layout
```

---

### Layout Explanation

#### Vertical PDF (`*_v.pdf`)

* Image on top
* Description below
* Suitable for reading or printing

#### Horizontal PDF (`*_h.pdf`)

* A4 landscape
* Image on the left
* Description on the right
* Optimized for slide review

Layout behavior is controlled via:

```
forms/
├── pdf_style_vertical.css
└── pdf_style_landscape.css
```

---

## PDF Generation Notes

* Markdown → HTML via **pandoc**
* HTML → PDF via **wkhtmltopdf**
* Local image access enabled
* Temporary HTML files are deleted automatically

---

# Part 2. Audio Transcription Tool

This tool sends audio files to a Whisper-compatible API and saves transcription results.

---

## Input Directory

Place audio files inside:

```
audio_data/
```

Supported formats:

* `.mp3`

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

This value is forwarded directly to the Whisper-compatible server.

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

### Text Only

```
audio_result/lecture1.txt
```

### With Timestamps

```
audio_result/lecture1_with_time.txt
```

---

## Notes

* Both tools are CLI-based
* Designed for offline batch processing
* Custom LLM / ASR servers must be OpenAI-compatible
* Suitable for lecture archiving, study notes, and review materials

---