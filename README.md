# QnA Pair Generator (Bahasa Melayu)

A Python CLI tool that generates non-redundant Question-Answer pairs in Bahasa Melayu from text files using a two-agent system. Agent 1 (Penjana/Generator) creates Q&A candidates, and Agent 2 (Penyemak/Reviewer) verifies, edits, or rejects each pair to ensure quality and accuracy.

## Features

- **Two-Agent System**: Generator creates candidates, Reviewer validates quality
- **OpenAI-Compatible APIs**: Works with OpenRouter, DashScope, or any OpenAI-compatible endpoint
- **Smart Chunking**: Configurable word-window chunking with overlap
- **Deduplication**: Fuzzy matching to eliminate near-duplicate questions
- **Strict JSONL Output**: Clean, parseable output format
- **Configurable**: Environment variables for all key parameters

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Access**
   ```bash
   cp .env.example .env
   # Edit .env with your API credentials
   ```

   **Option A: OpenRouter (Recommended - Free Tier Available)**
   - Sign up at [OpenRouter](https://openrouter.ai/)
   - Get your API key
   - Use these settings in `.env`:
     ```
     OPENAI_API_KEY=your_openrouter_api_key_here
     OPENAI_BASE_URL=https://openrouter.ai/api/v1
     QWEN_GEN_MODEL=qwen/qwen3-next-80b-a3b-instruct
     QWEN_REVIEW_MODEL=qwen/qwen3-next-80b-a3b-instruct
     ```

   **Option B: DashScope (Alibaba Cloud)**
   - Sign up at [DashScope](https://dashscope.aliyun.com/)
   - Get your API key
   - Use these settings in `.env`:
     ```
     OPENAI_API_KEY=your_dashscope_api_key_here
     OPENAI_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
     QWEN_GEN_MODEL=qwen-plus
     QWEN_REVIEW_MODEL=qwen-plus
     ```

3. **Prepare Input Files**
   - For CLI: Place your `.txt` files in the `./data/` directory
   - For GUI: You can select any text file directly
   - A sample file `data/sample.txt` is included for testing

## Usage

### 🌐 Web Interface (Recommended - Browser-Based)

Launch the web application:
```bash
python3 qna_bm_web.py
```

Then open your browser and navigate to: **http://localhost:8080**

The web interface provides:
- ✅ **Live Progress Updates** - Real-time streaming progress as Q&A pairs are generated
- ✅ **AI Connection Verification** - Automatic check to ensure API is connected before starting
- ✅ **File Upload** - Upload any text file via drag & drop or file browser
- ✅ **Configurable Settings** - Adjust maximum number of Q&A pairs
- ✅ **Beautiful Preview** - View generated Q&A pairs in a clean, organized interface
- ✅ **One-Click CSV Export** - Download results as CSV file instantly
- ✅ **Cross-Platform** - Works on any device with a modern browser

### 💻 CLI Interface

For batch processing multiple files:
```bash
python qna_bm_two_agent.py
```

The script will:
1. Read all `.txt` files from `./data/*.txt`
2. Chunk each file into overlapping segments
3. Generate Q&A pairs using Agent 1 (Penjana)
4. Review each pair using Agent 2 (Penyemak)
5. Filter out duplicates
6. Write results to `qa_bm.jsonl`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *required* | Your API key |
| `OPENAI_BASE_URL` | *required* | API endpoint URL |
| `QWEN_GEN_MODEL` | `qwen/qwen3-next-80b-a3b-instruct` | Model for generator agent |
| `QWEN_REVIEW_MODEL` | `qwen/qwen3-next-80b-a3b-instruct` | Model for reviewer agent |
| `QNA_CHUNK_WORDS` | `800` | Words per chunk |
| `QNA_CHUNK_OVERLAP` | `100` | Overlapping words between chunks |
| `QNA_DUP_QUESTION_SIM` | `0.88` | Similarity threshold for duplicate detection (0-1) |
| `QNA_MAX_PAIRS` | `100` | Maximum Q&A pairs to generate |
| `QNA_INPUT_GLOB` | `data/*.txt` | Input file pattern |
| `QNA_OUTPUT_PATH` | `qa_bm.jsonl` | Output file path |

## Output Format

The output file `qa_bm.jsonl` contains one JSON object per line:
```json
{"question":"Apakah ibu negara Malaysia?","answer":"Kuala Lumpur","source":"sample.txt"}
{"question":"Berapa banyak negeri di Malaysia?","answer":"Tiga belas negeri","source":"sample.txt"}
```

## How It Works

1. **Chunking**: Text files are split into overlapping chunks (default: 800 words, 100 overlap)
2. **Generation**: For each chunk, Agent 1 generates up to 10 Q&A pair candidates in Bahasa Melayu
3. **Review**: Agent 2 reviews each candidate and returns:
   - `accept`: Pair is good as-is
   - `edit`: Pair needs corrections (auto-corrected)
   - `reject`: Pair doesn't meet quality standards
4. **Deduplication**: Accepted pairs are checked against existing questions using fuzzy matching
5. **Output**: Final pairs are written to JSONL format

## Troubleshooting

- **"Error: OPENAI_API_KEY and OPENAI_BASE_URL must be set"**
  - Check your `.env` file exists and contains the required variables
  - Ensure you've copied `.env.example` to `.env` and filled in your credentials

- **"No files found matching data/*.txt"**
  - Create a `data/` directory and add `.txt` files to it
  - Or modify `QNA_INPUT_GLOB` environment variable

- **API Errors**
  - Verify your API key is correct
  - Check that your chosen model is available
  - For OpenRouter free tier, ensure you're using the correct model names

## License

MIT License - feel free to use and modify as needed.

