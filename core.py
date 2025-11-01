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
    """Chunk text by words with overlap (no limit on words or chunks)"""
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, size - overlap)
    # Process all words without stopping early
    i = 0
    while i < len(words):
        chunk_words_list = words[i:i + size]
        if chunk_words_list:
            chunk_text = " ".join(chunk_words_list)
            chunks.append((chunk_text, i, min(i + size, len(words))))
        i += step
        # Only stop if we've processed everything
        if i >= len(words):
            break
    return chunks

# --- Generation ---
def generate_pairs_for_chunk(
    chunk_text: str,
    source_name: str,
    *,
    title: Optional[str] = None,
    cap_this_chunk: Optional[int] = None,
    total_target: Optional[int] = None,
    produced_so_far: Optional[int] = None,
    remaining_chunks: Optional[int] = None,
    chunk_idx: Optional[int] = None,
) -> List[Dict]:
    """Generate Q&A pairs for a text chunk using the new prompt schema (CLEAN_TEXT blocks)."""
    clean_title = (title or "").strip()
    clean_body = chunk_text.strip()
    user_lines: List[str] = []
    user_lines.append("CLEAN_TEXT:")
    user_lines.append("TITLE:")
    user_lines.append(clean_title)
    user_lines.append("")
    user_lines.append("ABSTRACT_BLOCK:")
    user_lines.append("")
    user_lines.append("")
    user_lines.append("BODY_BLOCK:")
    user_lines.append(clean_body)
    user_lines.append("")
    # Use chunk reference if available, otherwise use source name
    if chunk_idx:
        user_lines.append(f"SOURCE_LABEL: {source_name} Chunk {chunk_idx}")
    else:
        user_lines.append(f"SOURCE_LABEL: {source_name}")
    # Targets and caps
    if total_target is not None:
        user_lines.append(f"MIN_TARGET = 80, TOTAL_TARGET = {int(total_target)}")
    else:
        user_lines.append("MIN_TARGET = 80, TOTAL_TARGET = 100")
    if produced_so_far is not None:
        user_lines.append(f"PRODUCED_SO_FAR = {int(max(0, produced_so_far))}")
    if remaining_chunks is not None:
        user_lines.append(f"REMAINING_CHUNKS = {int(max(0, remaining_chunks))}")
    if cap_this_chunk is not None:
        user_lines.append(f"CAP_THIS_CHUNK = {int(max(0, cap_this_chunk))}")
    user_prompt = "\n".join(user_lines)

    try:
        raw = chat(MODEL_GEN, GENERATOR_SYSTEM, user_prompt, temperature=0.2)
    except Exception as e:
        print(f"Error generating pairs: {e}")
        return []
    if not raw or not raw.strip():
        return []

    pairs: List[Dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            if "{" in line and "}" in line:
                start = line.find("{")
                end = line.rfind("}") + 1
                try:
                    obj = json.loads(line[start:end])
                except json.JSONDecodeError:
                    continue
            else:
                continue
        q = (obj.get("question") or "").strip()
        a = (obj.get("answer") or "").strip()
        if q and a:
            # Use chunk reference if available
            src_label = f"{source_name} Chunk {chunk_idx}" if chunk_idx else source_name
            pairs.append({"question": q, "answer": a, "source": src_label, "chunk_text": chunk_text})
    # If a cap is supplied, enforce it
    if cap_this_chunk is not None and cap_this_chunk >= 0:
        return pairs[:cap_this_chunk]
    return pairs

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

# --- Review ---
def review_pair(pair: Dict, supporting_text: str, *, title: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
    """Review a Q&A pair using the new reviewer schema."""
    user_lines: List[str] = []
    user_lines.append("CLEAN_TEXT:")
    user_lines.append("TITLE:")
    user_lines.append((title or "").strip())
    user_lines.append("")
    user_lines.append("ABSTRACT_BLOCK:")
    user_lines.append("")
    user_lines.append("")
    user_lines.append("BODY_BLOCK:")
    user_lines.append(supporting_text.strip())
    user_lines.append("")
    user_lines.append(f"SOURCE_LABEL: {pair.get('source','')}")
    user_lines.append("")
    user_lines.append("PAIR:")
    user_lines.append(json.dumps(pair, ensure_ascii=False))
    review_prompt = "\n".join(user_lines)

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
def process_text_file(text_content: str, source_name: str, max_pairs: Optional[int] = None, 
                     progress_callback: Optional[Callable[[str], None]] = None,
                     max_workers: int = 5,
                     skip_review: bool = True,
                     doc_title: Optional[str] = None) -> List[Dict]:
    """Process a single text file and return Q&A pairs using parallel processing"""
    accepted_pairs = []
    existing_questions = []
    lock = Lock()  # For thread-safe access to shared data
    
    if progress_callback:
        progress_callback(f"Processing: {source_name}")
    
    chunks = chunk_words(text_content, CHUNK_WORDS, CHUNK_OVERLAP)
    total_chunks = len(chunks)
    
    if total_chunks == 0:
        if progress_callback:
            progress_callback("No chunks generated from text")
        return []
    
    # Adaptive max_pairs based on document size (always calculated)
    word_count = len(text_content.split())
    # Estimate: ~15-20 pairs per 800-word chunk, but cap at reasonable limits
    estimated_pairs = min(word_count // 40, total_chunks * 20)  # 1 pair per ~40 words or 20 per chunk
    # Ensure minimum of 50 and maximum of 200
    adaptive_max = max(50, min(200, estimated_pairs))
    # Round to nearest 10
    adaptive_max = round(adaptive_max / 10) * 10
    
    # Apply user cap if provided (max_pairs is used as a cap, not absolute value)
    # If max_pairs is None/0/negative, use adaptive only
    if max_pairs is not None and max_pairs > 0:
        if max_pairs < adaptive_max:
            final_max = max_pairs
            if progress_callback:
                progress_callback(f"Adaptive max_pairs: {adaptive_max}, capped at {final_max} by user (based on {word_count} words, {total_chunks} chunks)")
        else:
            final_max = adaptive_max
            if progress_callback:
                progress_callback(f"Adaptive max_pairs set to {final_max} (user cap {max_pairs} not limiting, based on {word_count} words, {total_chunks} chunks)")
    else:
        final_max = adaptive_max
        if progress_callback:
            progress_callback(f"Adaptive max_pairs set to {final_max} based on {word_count} words and {total_chunks} chunks")
    
    max_pairs = final_max  # Update for use in rest of function
    
    if progress_callback:
        progress_callback(f"Found {total_chunks} chunks. Target: {max_pairs} pairs. Processing in parallel...")
    
    def process_chunk(chunk_data: Tuple[str, str, int, int]) -> List[Dict]:
        """Process a single chunk and return reviewed pairs"""
        chunk_text, src_name, idx, total = chunk_data
        chunk_results = []
        
        try:
            # Stage 1: Pre-filter chunk (basic check, skip AI call for speed when review disabled)
            
            # Only run full prefilter AI check if review is enabled (for quality)
            # When review is disabled, we skip prefilter AI call for speed
            if not skip_review:
                accepted, reason = prefilter_chunk(chunk_text)
                if not accepted:
                    if progress_callback:
                        progress_callback(f"Chunk {idx} rejected by prefilter: {reason}")
                    return chunk_results
            
            # Stage 2: Generate candidates using new prompt schema
            with lock:
                current_produced = len(accepted_pairs)
            remaining_budget = max(0, max_pairs - current_produced)
            remaining_after_this = max(1, total - idx + 1)
            # For 800-word chunks, aim for 15-20 pairs per chunk is reasonable
            cap_this_chunk = min(20, max(0, round(remaining_budget / remaining_after_this)))
            candidate_pairs = generate_pairs_for_chunk(
                chunk_text,
                src_name,
                title=doc_title or source_name,
                cap_this_chunk=cap_this_chunk,
                total_target=max_pairs,
                produced_so_far=current_produced,
                remaining_chunks=remaining_after_this - 1,
                chunk_idx=idx,
            )
            
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
                    reviewed, reason = review_pair(pair, chunk_text, title=doc_title or source_name)
                
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

