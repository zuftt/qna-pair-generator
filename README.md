# qna-pair-generator

## QnA Pair Generator (Bahasa Melayu)

Minimal instructions to get running locally with **Qwen: `qwen/qwen3-next-80b-a3b-instruct`** — **Web UI only (no CLI)**.

---

## 1) Set Up
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Edit **.env** (OpenRouter recommended):
```dotenv
OPENAI_API_KEY=YOUR_OPENROUTER_KEY
OPENAI_BASE_URL=https://openrouter.ai/api/v1
QWEN_GEN_MODEL=qwen/qwen3-next-80b-a3b-instruct
QWEN_REVIEW_MODEL=qwen/qwen3-next-80b-a3b-instruct
```
Add your source files:
```bash
mkdir -p data
# put your .txt files into ./data/
```

---

## 2) Use on Localhost
### Web UI
```bash
python qna_bm_web.py
```
Open **http://localhost:8080** then:
1. Upload your `.txt` files (drag & drop or file picker).
2. Click **Generate** to create Q&A pairs.
3. Preview results, then **Download** (CSV/JSONL).

---

## Notes
- No tuning needed—defaults use the specified Qwen model for both Generator and Reviewer.
- If you prefer DashScope later, just replace `OPENAI_BASE_URL` and keep the same model or `qwen-plus`.

---

## Three-Stage AI System Architecture

This system uses a sophisticated three-stage pipeline to ensure high-quality, metadata-free Q&A pairs:

### Stage 1: Pre-filter (Penyaring Awal)
- **Purpose**: Filters out chunks containing metadata or inappropriate content
- **Checks for**: File metadata, system information, non-Malay content, text length
- **Output**: Accepts or rejects text chunks before processing

### Stage 2: Generator (Penjana)
- **Purpose**: Generates Q&A pair candidates from validated text chunks
- **Capabilities**: Creates up to 10 Q&A pairs per chunk across various difficulty levels
- **Format**: Strict JSONL output with question, answer, and source
- **Language**: Bahasa Melayu baku (standard Malay)

### Stage 3: Reviewer (Penyemak)
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
- **Skip Review Mode**: Fast mode that skips AI review but includes basic metadata filtering
- **Smart Deduplication**: Fuzzy matching to prevent near-duplicate questions
- **Metadata Stripping**: Automatically removes file headers and metadata before processing 
