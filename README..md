# Usage Guide

This document explains how to use the PPT slide description generator.

---

## 1. Directory Structure

Before running the program, make sure your project directory is structured as follows:

```

project/
├── main.py
├── .env
├── data/
└── result/

```

- `data/`  
  Place ZIP files containing slide images here.

- `result/`  
  Output files will be automatically created in this directory.

---

## 2. Preparing ZIP Files

Each ZIP file should contain only image files extracted from PPT slides.

Supported image formats:
- `.png`
- `.jpg`
- `.jpeg`

Example:

```

data/
└── lecture1.zip
├── slide01.jpg
├── slide02.jpg

````

---

## 3. Environment Configuration

Create a `.env` file in the project root directory:

```env
URL=http://localhost:8000/v1
TOKEN=EMPTY
````

* `URL` is the endpoint of the running vLLM server.
* `TOKEN` can be left as `EMPTY` if authentication is not required.

---

## 4. Running the Program

Execute the script using:

```bash
python generate_from_zip.py
```

After running, you will see a list of ZIP files found in the `data` directory:

```
Available ZIP files:
1. lecture1.zip
2. lecture2.zip
a. Process all
```

Select a ZIP file by entering its number, or choose `a` to process all ZIP files.

---

## 5. Choosing Output Format

After selecting a ZIP file, you will be prompted to choose an output format:

```
Output format:
1. Generate one .md file per image
2. Merge all results into a single README.md
```

### Option 1: One Markdown File per Image

Each slide image will produce its own Markdown file.

Output structure:

```
result/lecture1/
├── slide01.md
├── slide02.md
```

Each file contains a textual explanation of the corresponding slide.

---

### Option 2: Single README.md File

All slide descriptions are merged into a single Markdown file.

Output structure:

```
result/lecture1/
├── README.md
├── slide01.jpg
├── slide02.jpg
```

The `README.md` file follows this format:

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

## 6. Output Description Content

Each generated description includes:

* The main topic of the slide
* A summary of key points
* Explanation of diagrams or figures
* Detailed explanation suitable for academic or technical slides

All output is written in Markdown format.

---

## 7. Notes and Limitations

* The ZIP file must contain image files only.
* Duplicate image names may overwrite files.
* Processing time depends on the number of images and model speed.
* The vLLM server must be running before execution.
* If an error occurs during processing, some slides may be skipped.

---

## 8. Recommended Workflow

1. Export PPT slides as images
2. Compress images into a ZIP file
3. Place the ZIP file in the `data/` directory
4. Run the script
5. Select the desired output mode
6. Review results in the `result/` directory

---

This tool is designed to help convert presentation slides into structured, readable documentation using a local vision-language model.
