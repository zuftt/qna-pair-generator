# QnA Pair Generator (Bahasa Melayu) - Two-Agent System CLI
# Reads ./data/*.txt and generates non-redundant Q&A pairs using OpenAI-compatible APIs

from __future__ import annotations
import os
import glob
import json
import qna_bm_core

# --- Configuration ---
INPUT_GLOB = os.getenv("QNA_INPUT_GLOB", "data/*.txt")
OUTPUT_PATH = os.getenv("QNA_OUTPUT_PATH", "qa_bm.jsonl")
MAX_PAIRS = int(os.getenv("QNA_MAX_PAIRS", "100"))

# Graceful exit if environment missing
if not qna_bm_core.API_KEY or not qna_bm_core.BASE_URL:
    print("Error: OPENAI_API_KEY and OPENAI_BASE_URL must be set.")
    print("Please check your .env file or environment variables.")
    exit(1)

# --- Main Pipeline ---
def run_pipeline():
    """Main pipeline: read files, chunk, generate, review, deduplicate, write output"""
    accepted_pairs = []
    
    # Find all .txt files
    txt_files = glob.glob(INPUT_GLOB)
    if not txt_files:
        print(f"Warning: No files found matching {INPUT_GLOB}")
        return
    
    print(f"Processing {len(txt_files)} file(s)...")
    
    for file_path in txt_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            source_name = os.path.basename(file_path)
            
            print(f"  Processing: {source_name}")
            pairs = qna_bm_core.process_text_file(full_text, source_name, max_pairs=MAX_PAIRS)
            accepted_pairs.extend(pairs)
            
            if len(accepted_pairs) >= MAX_PAIRS:
                accepted_pairs = accepted_pairs[:MAX_PAIRS]
                break
        
        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
            continue
    
    # Write output as strict JSONL
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for pair in accepted_pairs:
            # Write exactly as specified: {"question":"...","answer":"...","source":"filename.txt"}
            output_obj = {
                "question": pair["question"],
                "answer": pair["answer"],
                "source": pair["source"]
            }
            f.write(json.dumps(output_obj, ensure_ascii=False) + "\n")
    
    print(f"\nWrote {len(accepted_pairs)} Q&A pairs to {OUTPUT_PATH}")

if __name__ == "__main__":
    run_pipeline()

