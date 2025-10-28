# Core QnA processing functions - shared by CLI and GUI

from __future__ import annotations
import os
import json
import difflib
from typing import List, Dict, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

# --- Configuration ---
MAX_PAIRS = int(os.getenv("QNA_MAX_PAIRS", "100"))
CHUNK_WORDS = int(os.getenv("QNA_CHUNK_WORDS", "800"))
CHUNK_OVERLAP = int(os.getenv("QNA_CHUNK_OVERLAP", "100"))
SIM_THRESH = float(os.getenv("QNA_DUP_QUESTION_SIM", "0.88"))

BASE_URL = os.getenv("OPENAI_BASE_URL")
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_GEN = os.getenv("QWEN_GEN_MODEL", "qwen/qwen3-next-80b-a3b-instruct")
MODEL_REVIEW = os.getenv("QWEN_REVIEW_MODEL", "qwen/qwen3-next-80b-a3b-instruct")

if not API_KEY or not BASE_URL:
    client = None
else:
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

# --- Load System Prompts from files ---
def load_prompt(prompt_file: str) -> str:
    """Load prompt from file"""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", prompt_file)
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: Prompt file {prompt_file} not found. Using default.")
        return ""

PREFILTER_SYSTEM = load_prompt("prefilter_system.txt")
GENERATOR_SYSTEM = load_prompt("generator_system.txt")
REVIEWER_SYSTEM = load_prompt("reviewer_system.txt")

# Fallback prompts if files not found
if not PREFILTER_SYSTEM:
    PREFILTER_SYSTEM = """Anda ialah penyaring awal. TOLAK teks dengan metadata atau tidak sesuai. Pulangkan: {"status":"accept"|"reject","reason":"..."}"""

if not GENERATOR_SYSTEM:
    GENERATOR_SYSTEM = """Anda ialah penjana Soal–Jawab BM. Hasilkan JSONL: {"question":"…","answer":"…","source":""}."""

if not REVIEWER_SYSTEM:
    REVIEWER_SYSTEM = """Anda ialah penyemak. TOLAK metadata. Pulangkan: {"status":"accept"|"edit"|"reject","question":"…","answer":"…","reason":"…"}."""

# --- Chat Helper ---
def chat(model: str, system: str, user: str, temperature: float = 0.2) -> str:
    """Helper function using chat.completions.create"""
    if not client:
        raise ValueError("OpenAI client not initialized. Check API credentials.")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        error_msg = str(e)
        print(f"Error calling API: {error_msg}")
        # Raise specific errors for rate limits
        if "429" in error_msg or "rate limit" in error_msg.lower():
            raise ValueError("API rate limit exceeded. Please try again later or upgrade your plan.")
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            raise ValueError("Invalid API key. Please check your credentials.")
        raise ValueError(f"API error: {error_msg}")

# --- Text Chunking ---
def chunk_words(text: str, size: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> List[Tuple[str, int, int]]:
    """Chunk text by words with overlap"""
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, size - overlap)
    for i in range(0, len(words), step):
        chunk_words_list = words[i:i + size]
        if not chunk_words_list:
            break
        chunk_text = " ".join(chunk_words_list)
        chunks.append((chunk_text, i, min(i + size, len(words))))
    return chunks

# --- Generation: Agent 1 (Penjana) ---
def generate_pairs_for_chunk(chunk_text: str, source_name: str) -> List[Dict]:
    """Generate up to 10 Q&A pairs for a text chunk"""
    user_prompt = f"""Nama fail: {source_name}

Petikan teks:
{chunk_text}

Arahan: Hasilkan sehingga 10 pasangan Soal–Jawab dalam Bahasa Melayu. Setiap pasangan mesti unik dan disokong jelas oleh teks. Format JSONL (satu objek per baris) dengan kunci: question, answer, source."""
    
    try:
        raw = chat(MODEL_GEN, GENERATOR_SYSTEM, user_prompt, temperature=0.1)
    except Exception as e:
        print(f"Error generating pairs: {e}")
        return []
    
    if not raw or not raw.strip():
        return []
    
    pairs = []
    
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        
        # Try to extract JSON from line
        try:
            obj = json.loads(line)
            q = (obj.get("question") or "").strip()
            a = (obj.get("answer") or "").strip()
            if q and a:
                pairs.append({"question": q, "answer": a, "source": source_name})
        except json.JSONDecodeError:
            # Try to find JSON in the line
            if "{" in line and "}" in line:
                start = line.find("{")
                end = line.rfind("}") + 1
                if start < end:
                    try:
                        obj = json.loads(line[start:end])
                        q = (obj.get("question") or "").strip()
                        a = (obj.get("answer") or "").strip()
                        if q and a:
                            pairs.append({"question": q, "answer": a, "source": source_name})
                    except json.JSONDecodeError:
                        pass
            continue
    
    return pairs[:10]  # Cap at 10 pairs per chunk

# --- Pre-filter: Stage 1 (Penyaring Awal) ---
def prefilter_chunk(chunk_text: str) -> Tuple[bool, str]:
    """Pre-filter chunk to reject metadata or inappropriate content"""
    if len(chunk_text.split()) < 50:
        return False, "Text too short"
    
    prefilter_prompt = f"""Teks untuk disemak:
{chunk_text}

Semak teks ini dan tentukan sama ada sesuai untuk Q&A."""
    
    try:
        raw = chat(MODEL_GEN, PREFILTER_SYSTEM, prefilter_prompt, temperature=0.0).strip()
        
        # Try to extract JSON from response
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON in response
            if "{" in raw and "}" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start < end:
                    try:
                        obj = json.loads(raw[start:end])
                    except json.JSONDecodeError:
                        return True, "Could not parse prefilter response, accepting by default"
            else:
                return True, "No JSON in response, accepting by default"
        
        status = obj.get("status", "").lower()
        reason = obj.get("reason", "No reason provided")
        
        if status == "reject":
            return False, reason
        return True, reason if status == "accept" else "Accepted"
    except Exception as e:
        # If prefilter fails, accept by default
        return True, f"Prefilter error: {str(e)}, accepting by default"

# --- Review: Agent 3 (Penyemak) ---
def review_pair(pair: Dict, supporting_text: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Review a Q&A pair and return (accepted_pair, reason_or_error)"""
    review_prompt = f"""Teks sumber:
{supporting_text}

Pasangan cadangan:
{json.dumps(pair, ensure_ascii=False, indent=2)}

Semak pasangan ini dan pulangkan SATU objek JSON sahaja dengan status (accept/edit/reject), question, answer, dan reason."""
    
    raw = chat(MODEL_REVIEW, REVIEWER_SYSTEM, review_prompt, temperature=0.0).strip()
    
    # Try to extract JSON from response
    try:
        # Try direct parse
        obj = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON in response
        if "{" in raw and "}" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start < end:
                try:
                    obj = json.loads(raw[start:end])
                except json.JSONDecodeError:
                    return None, "cannot_parse_reviewer"
            else:
                return None, "cannot_parse_reviewer"
        else:
            return None, "cannot_parse_reviewer"
    
    status = obj.get("status", "").lower()
    if status == "reject":
        return None, obj.get("reason", "rejected")
    
    if status in {"accept", "edit"}:
        q = (obj.get("question") or pair.get("question") or "").strip()
        a = (obj.get("answer") or pair.get("answer") or "").strip()
        if q and a:
            return {"question": q, "answer": a, "source": pair.get("source")}, None
    
    return None, f"invalid_status: {status}"

# --- Deduplication by fuzzy similarity ---
def is_dup_question(question: str, existing_questions: List[str], threshold: float = SIM_THRESH) -> bool:
    """Check if question is a near-duplicate using fuzzy matching"""
    q_lower = question.lower().strip()
    for existing_q in existing_questions:
        existing_lower = existing_q.lower().strip()
        similarity = difflib.SequenceMatcher(None, q_lower, existing_lower).ratio()
        if similarity >= threshold:
            return True
    return False

# --- Process single text file with async/parallel processing ---
def process_text_file(text_content: str, source_name: str, max_pairs: int = MAX_PAIRS, 
                     progress_callback: Optional[Callable[[str], None]] = None,
                     max_workers: int = 5,
                     skip_review: bool = True) -> List[Dict]:
    """Process a single text file and return Q&A pairs using parallel processing"""
    accepted_pairs = []
    existing_questions = []
    lock = Lock()  # For thread-safe access to shared data
    
    if progress_callback:
        progress_callback(f"Processing: {source_name}")
    
    # Strip metadata headers if present (lines before "Teks:" or main content)
    if "Teks:" in text_content:
        text_content = text_content.split("Teks:")[-1].strip()
    elif "ID Fail :" in text_content or "Tajuk :" in text_content:
        # Find where actual content starts (after metadata)
        lines = text_content.split('\n')
        for i, line in enumerate(lines):
            if line.strip() and not any(keyword in line for keyword in ["ID Fail", "Tajuk", "Penulis", "Tarikh", "Bidang", "Subbidang", "Sumber", "Tahap", "Bahasa", "Laras", "Panjang", "Sensitif", "Format", "Kaedah", "Hak Guna", "Rujukan"]):
                # Found content, skip metadata lines
                text_content = '\n'.join(lines[i:]).strip()
                break
    
    # Check if text is too short
    if len(text_content.strip()) < 50:
        if progress_callback:
            progress_callback("Text too short for processing")
        return []
    
    chunks = chunk_words(text_content, CHUNK_WORDS, CHUNK_OVERLAP)
    total_chunks = len(chunks)
    
    if total_chunks == 0:
        if progress_callback:
            progress_callback("No chunks generated from text")
        return []
    
    if progress_callback:
        progress_callback(f"Found {total_chunks} chunks. Processing in parallel...")
    
    def process_chunk(chunk_data: Tuple[str, str, int, int]) -> List[Dict]:
        """Process a single chunk and return reviewed pairs"""
        chunk_text, src_name, idx, total = chunk_data
        chunk_results = []
        
        try:
            # Stage 1: Pre-filter chunk (basic check, skip AI call for speed when review disabled)
            # Simple length check first
            if len(chunk_text.split()) < 50:
                if progress_callback:
                    progress_callback(f"Chunk {idx} too short ({len(chunk_text.split())} words)")
                return chunk_results
            
            # Only run full prefilter AI check if review is enabled (for quality)
            # When review is disabled, we skip prefilter AI call for speed
            if not skip_review:
                accepted, reason = prefilter_chunk(chunk_text)
                if not accepted:
                    if progress_callback:
                        progress_callback(f"Chunk {idx} rejected by prefilter: {reason}")
                    return chunk_results
            
            # Stage 2: Generate candidates
            candidate_pairs = generate_pairs_for_chunk(chunk_text, src_name)
            
            if not candidate_pairs:
                if progress_callback:
                    progress_callback(f"Chunk {idx}: No pairs generated")
            
            # Stage 3: Review each candidate
            for pair in candidate_pairs:
                # Check if we've reached max pairs
                with lock:
                    if len(accepted_pairs) >= max_pairs:
                        return chunk_results
                
                # Check for duplicates (needs lock)
                with lock:
                    if is_dup_question(pair["question"], existing_questions):
                        continue
                
                # Review pair (or skip review for speed)
                if skip_review:
                    # Quick metadata check even when review is skipped (less aggressive)
                    q_lower = pair.get("question", "").lower()
                    a_lower = pair.get("answer", "").lower()
                    # Only filter obvious metadata, not normal words
                    metadata_keywords = ["file://", "path://", "http://", "https://", "metadata:", "e-mel:", "@", ".com"]
                    if any(keyword in q_lower or keyword in a_lower for keyword in metadata_keywords):
                        continue  # Skip pairs with obvious metadata
                    reviewed = pair
                    reason = None
                else:
                    reviewed, reason = review_pair(pair, chunk_text)
                
                if reviewed and isinstance(reviewed, dict):
                    # Add to results with lock
                    with lock:
                        # Check again if we've reached max
                        if len(accepted_pairs) >= max_pairs:
                            return chunk_results
                        # Double-check duplicates after lock
                        if not is_dup_question(reviewed["question"], existing_questions):
                            accepted_pairs.append(reviewed)
                            existing_questions.append(reviewed["question"])
                            chunk_results.append(reviewed)
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error in chunk {idx}: {str(e)}")
        
        return chunk_results
    
    # Process chunks in parallel using ThreadPoolExecutor
    chunk_data_list = [(chunk_text, source_name, idx, total_chunks) 
                       for idx, (chunk_text, _start, _end) in enumerate(chunks, 1)]
    
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks
        future_to_chunk = {
            executor.submit(process_chunk, chunk_data): chunk_data[2] 
            for chunk_data in chunk_data_list
        }
        
        # Process completed chunks as they finish
        for future in as_completed(future_to_chunk):
            chunk_idx = future_to_chunk[future]
            completed += 1
            
            try:
                chunk_results = future.result()
                if progress_callback:
                    with lock:
                        current_count = len(accepted_pairs)
                    progress_callback(
                        f"Completed chunk {completed}/{total_chunks} | "
                        f"Total pairs: {current_count}/{max_pairs}"
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Error processing chunk {chunk_idx}: {str(e)}")
            
            # Check if we've reached max pairs (continue processing to check all chunks)
            with lock:
                if len(accepted_pairs) >= max_pairs:
                    # Note: We don't cancel futures as they may already be running
                    # The chunk processing function checks max_pairs internally
                    pass
    
    # Sort by source order for consistency
    accepted_pairs = sorted(accepted_pairs, key=lambda x: x.get('source', ''))
    
    if progress_callback:
        progress_callback(f"Completed! Generated {len(accepted_pairs)} Q&A pairs.")
    
    return accepted_pairs

