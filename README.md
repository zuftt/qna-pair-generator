## QnA Pair Generator (Bahasa Melayu)

A Python web application that automatically generates high-quality Question-Answer pairs in Bahasa Melayu from text documents. Uses a three-stage AI pipeline to filter metadata, generate Q&A pairs, and review quality before exporting to CSV format. 
Minimal instructions to get running locally with **Qwen: `qwen/qwen3-30b-a3b:free`**.

---
Cara nak guna:

## 1) Copy repository dalam IDE
```bash
git clone https://github.com/zuftt/qna-pair-generator.git
```

## 2) Run these commmands dalam root directory
```bash
cd qna-pair-generator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
Create **.env** file and copy from env.example,
```dotenv
OPENAI_API_KEY=YOUR_OPENROUTER_KEY
OPENAI_BASE_URL=https://openrouter.ai/api/v1
QWEN_GEN_MODEL=qwen/qwen3-30b-a3b:free
QWEN_REVIEW_MODEL=qwen/qwen3-30b-a3b:free
```
Then, replace  `YOUR_OPENROUTER_KEY` with OpenRouter API Key.
You can follow this [tutorial](https://www.youtube.com/watch?v=QINOR9fATxY), to get an API Key.

In my case I use OpenRouter to access Qwen's API. You can read more about OpenRouter [here](https://openrouter.ai/).

The model I'm using is qwen/qwen3-30b-a3b:free. [link](https://openrouter.ai/qwen/qwen3-30b-a3b:free/api)

<img width="1470" height="824" alt="Screenshot 2025-10-29 at 4 39 41 PM" src="https://github.com/user-attachments/assets/0a700ee0-d450-4178-afcb-d8ce4bf27a27" />


## 3) Use on Localhost
### Web UI
```bash
python3 web.py #or just run this file via IDE
```
Open **http://localhost:8080** then:
1. Wait for the API connection to verify, if it fails please check your API Key.
2. Upload your `.txt` files (drag & drop or file picker).
3. Click **Generate** to create Q&A pairs.
4. Preview results, then **Download** (CSV).
   
<img width="1322" height="860" alt="Screenshot 2025-10-29 at 11 15 04 AM" src="https://github.com/user-attachments/assets/184bdb4a-1a76-4a69-a1c9-be6e907a1efd" />

---

## Notes
- I'm open to suggestions on improvements, and if you encounter problems do contact me I will try to help.

---

## Three-Stage AI System Architecture

This system uses a sophisticated three-stage pipeline to ensure high-quality, metadata-free Q&A pairs:

### Stage 1: Pre-filter 
- **Purpose**: Filters out chunks containing metadata or inappropriate content
- **Checks for**: File metadata, system information, non-Malay content, text length
- **Output**: Accepts or rejects text chunks before processing

### Stage 2: Generator 
- **Purpose**: Generates Q&A pair candidates from validated text chunks
- **Capabilities**: Creates up to 10 Q&A pairs per chunk across various difficulty levels
- **Format**: Strict JSONL output with question, answer, and source
- **Language**: Bahasa Melayu baku (standard Malay)

### Stage 3: Reviewer 
- **Purpose**: Verifies and filters generated Q&A pairs for quality and accuracy
- **Filters out**: Metadata (author names, journals, emails, references), low-quality pairs
- **Actions**: Accept, edit (auto-correct), or reject pairs
- **Ensures**: Content is supported by source text, no metadata leakage

### Processing Flow
```
Input Text → [Pre-filter] → Valid Chunks → [Generator] → Q&A Candidates → [Reviewer] → Final Q&A Pairs → CSV Output
```

### Performance Optimizations
- **Parallel Processing**: Processes multiple chunks simultaneously (configurable workers)
- **Smart Deduplication**: Fuzzy matching to prevent near-duplicate questions
- **Metadata Stripping**: Automatically removes file headers and metadata before processing 
