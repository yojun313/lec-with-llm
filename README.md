# Usage Guide

This document explains how to use the tools provided in this repository:

* **PPT slide description generator (`ppt_llm.py`)**
* **Audio transcription client (`audio_llm.py`)**

Both tools run locally and communicate with external model servers defined via environment variables.

---

## 1. Directory Structure

Ensure your project directory is structured as follows:

```
project/
├── ppt_llm.py
├── audio_llm.py
├── .env
├── ppt_data/
│   ├── (ZIP files)
├── ppt_result/
├── audio_data/
│   ├── (audio files)
├── audio_result/
└── README.md
```

---

## 2. Environment Configuration

Create a `.env` file in the project root directory.

```env
PPT_LLM_URL=http://localhost:8000/v1
AUDIO_LLM_URL=http://localhost:8000
TOKEN=EMPTY
```

### Environment Variables

#### `PPT_LLM_URL`

Base URL of the vision-language model server used by `ppt_llm.py`.

Example:

```
http://localhost:8000/v1
```

#### `AUDIO_LLM_URL`

Base URL of the FastAPI server exposing the `/whisper` endpoint.

The client will internally send requests to:

```
POST {AUDIO_LLM_URL}/whisper
```

#### `TOKEN`

Authentication token if required by the server.
Set to `EMPTY` if authentication is not used.

---

## 3. Required Python Packages

Install dependencies before running the scripts:

```bash
pip install requests python-dotenv rich
```

### Optional (for PDF export)

To enable Markdown → PDF conversion:

```bash
sudo apt install pandoc texlive-xetex fonts-noto-cjk
```

(Recommended) If you do not want LaTeX, you may alternatively install:

```bash
sudo apt install wkhtmltopdf fonts-noto-cjk
```

---

# Part I. PPT Slide Description Generator (`ppt_llm.py`)

This tool generates structured textual explanations from PPT slide images using a vision-language model.

---

## 4. Input Format (PPT Slides)

Place ZIP files containing extracted slide images into the `data/` directory.

```
data/
└── lecture1.zip
    ├── slide01.jpg
    ├── slide02.jpg
```

### Supported image formats

* `.png`
* `.jpg`
* `.jpeg`

Each ZIP file must contain only image files.

---

## 5. Running the PPT Tool

```bash
python ppt_llm.py
```

After execution, available ZIP files will be listed:

```
Available ZIP files:
1. lecture1.zip
2. lecture2.zip
a. Process all
```

Select a number to process a specific ZIP file, or enter `a` to process all ZIP files.

---

## 6. Output Format Selection

After selecting a ZIP file, choose one of the following output modes:

```
1. Generate one .md file per image
2. Merge all results into a single markdown file
```

---

## 7. Output Structure

### Option 1: One Markdown File per Image

```
result/lecture1/
├── slide01.md
├── slide02.md
```

Each file contains:

* Slide topic
* Key concepts
* Explanation of diagrams or figures
* Detailed academic or technical description

---

### Option 2: Merged Markdown File (Recommended)

When merge mode is selected, output is structured as:

```
result/lecture1/
├── lecture1.md
├── images/
│   ├── slide01.jpg
│   ├── slide02.jpg
```

### Markdown layout

```md
# lecture1

## slide01.jpg

![slide01.jpg](./images/slide01.jpg)

<generated explanation>

---

## slide02.jpg

![slide02.jpg](./images/slide02.jpg)

<generated explanation>
```

Images are always copied into the `images/` subdirectory, and Markdown references use relative paths.

---

## 8. Optional PDF Export

If enabled during execution, the merged Markdown file is automatically converted to PDF:

```
result/lecture1/
├── lecture1.md
├── lecture1.pdf
├── images/
```

### Requirements for PDF export

One of the following must be installed:

#### Recommended (best quality, supports Korean well)

```bash
sudo apt install texlive-xetex
```

#### Alternative

```bash
sudo apt install wkhtmltopdf
```

The script automatically calls `pandoc` with the appropriate engine.

---

# Part II. Audio Transcription Tool (`audio_llm.py`)

This tool uploads audio files to a FastAPI-based Whisper service and saves transcription results locally.

The Whisper model runs **on the server**, not in this script.

---

## 9. Input Audio Directory

Place audio files in:

```
data/
└── audio_data/
    ├── sample1.mp3
    ├── sample2.mp3
```

### Supported format

* `.mp3`

---

## 10. Output Directory

Transcription results are written to:

```
result/
└── audio_result/
    ├── sample_text.txt
    ├── sample_text_with_time.txt
```

### Output files

#### `*_text.txt`

Plain text transcription grouped into readable paragraphs.

#### `*_text_with_time.txt`

Transcription with timestamps per segment:

```
[00:00:01,230 - 00:00:03,840] example sentence
```

---

## 11. Running the Audio Transcription Tool

```bash
python audio_llm.py
```

You will be prompted to choose:

### 1. Whisper model level

```
1 = small
2 = medium
3 = large
```

This value is forwarded to the API as `model`.

---

### 2. Language code

You may specify a language code or enable automatic detection:

```
auto   (automatic detection)
ko     (Korean)
en     (English)
ja     (Japanese)
zh     (Chinese)
```

This value is sent as the `language` field in the request.

---

## 12. Audio Processing Flow

1. Scan `data/audio_data/` for `.mp3` files.
2. Upload each file to `POST /whisper`.
3. Send transcription options as JSON.
4. Receive transcription results.
5. Save:

   * plain text
   * timestamped text
6. Display progress in the terminal.

---