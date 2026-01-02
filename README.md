# Usage Guide

This document explains how to use the tools provided in this repository:

* **PPT slide description generator (`ppt_llm.py`)**
* **Audio transcription client (`audio_llm.py`)**

Both tools run locally and communicate with external model servers defined via environment variables.

---

## 1. Directory Structure

Before running the programs, ensure your project directory is structured as follows:

```
project/
├── ppt_llm.py
├── audio_llm.py
├── .env
├── data/
│   ├── (ZIP files or audio folders)
├── result/
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

### Environment variables

#### `PPT_LLM_URL`

Endpoint of the vision-language model server used by `ppt_llm.py`.

#### `AUDIO_LLM_URL`

Base URL of the FastAPI server exposing the `/whisper` endpoint.

Example:

```
http://localhost:8000
```

The script will internally call:

```
POST {AUDIO_LLM_URL}
```

#### `TOKEN`

Authentication token if required by the server.
If authentication is not used, set this to `EMPTY`.

---

# Part I. PPT Slide Description Generator (`ppt_llm.py`)

This tool generates structured textual descriptions from slide images extracted from PowerPoint files.

---

## 3. Input Format (PPT Slides)

Place ZIP files containing slide images inside the `data/` directory.

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

Each ZIP file should contain only image files.

---

## 4. Running the PPT Tool

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

Select a number to process a specific ZIP file, or choose `a` to process all ZIP files.

---

## 5. Output Format Selection

After selecting a ZIP file, choose one of the following output modes:

```
Output format:
1. Generate one .md file per image
2. Merge all results into a single README.md
```

---

### Option 1: One Markdown File per Image

Output structure:

```
result/lecture1/
├── slide01.md
├── slide02.md
```

Each Markdown file contains:

* Main topic of the slide
* Key points
* Explanation of diagrams or figures
* Detailed academic or technical explanation

---

### Option 2: Single README.md File

Output structure:

```
result/lecture1/
├── README.md
├── slide01.jpg
├── slide02.jpg
```

Example content:

```md
## slide01.jpg

![slide01.jpg](slide01.jpg)

Slide description text...

---

## slide02.jpg

![slide02.jpg](slide02.jpg)

Slide description text...
```

---

# Part II. Audio Transcription Tool (`audio_llm.py`)

This tool uploads audio files to a FastAPI `/whisper` endpoint and saves the returned transcription results.

Unlike a local Whisper setup, this script **does not run Whisper directly**.
Instead, it acts as a client that sends audio files to a server that already hosts the Whisper model.

---

## 6. Input Audio Directory

Place audio files under:

```
data/
└── audio_data/
    ├── sample1.mp3
    ├── sample2.mp3
```

### Supported format

* `.mp3`

---

## 7. Output Directory

Transcription results are written to:

```
result/
└── audio_result/
    ├── sample1.txt
    ├── sample1_with_time.txt
    ├── sample2.txt
    └── sample2_with_time.txt
```

### Output file types

#### `*.txt`

Plain text transcription grouped into readable paragraphs.

#### `*_with_time.txt`

Transcription with timestamped segments in the format:

```
[00:00:01,230 - 00:00:03,840] example sentence
```

---

## 8. Running the Audio Transcription Tool

Run:

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

Specify a language code or enable automatic detection.

Examples:

```
auto   (automatic detection)
ko     (Korean)
en     (English)
ja     (Japanese)
zh     (Chinese)
```

The value is passed to the API as the `language` field.

---

## 9. Processing Flow (Audio)

1. Scan `data/audio_data/` for `.mp3` files.
2. For each file:

   * Send a `POST /whisper` request.
   * Upload audio as multipart form data.
   * Include transcription options as JSON.
3. Receive JSON response from the server.
4. Extract:

   * `text`
   * `text_with_time`
5. Save results into `result/audio_result/`.
6. Display progress using a terminal progress bar.

---

