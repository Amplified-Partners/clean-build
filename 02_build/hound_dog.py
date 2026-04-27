#!/usr/bin/env python3
"""
Hound Dog - Forensic Data Mining & Convergence Engine
===================================================
Based on the Amplified Partners Vault Extraction Pipeline specs.
This tool crawls a target directory, extracts raw data (markdown, txt),
and uses an LLM (via the local Swarm or OpenAI) to mine and structure:
1. Raw Text
2. Structured JSON
3. Process/Logic
4. Principles/Values

It acts as both the "Hound Dog" (discovery/clustering) and "DocBench" (extraction).
"""

import os
import json
import glob
import hashlib
import ppdeep
from pathlib import Path
from datetime import datetime

# You can point this to OpenAI or your local Beast Swarm API
import httpx
import asyncio
import logging

# Set up logging for rock-solid observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HoundDog")

# Optional ppdeep for fuzzy matching (fail gracefully if not installed)
try:
    import ppdeep
    HAS_PPDEEP = True
except ImportError:
    logger.warning("ppdeep not installed. Fuzzy deduplication will be disabled. Run 'pip install ppdeep' to enable.")
    HAS_PPDEEP = False

# Target directories to sniff (can include system guts like Claude's local storage)
TARGET_DIRS = [
    "/Users/ewansair/Vaults/Ewan",
    os.path.expanduser("~/Library/Application Support/Claude/logs"), # Where Claude hides its stuff
    "/Users/ewansair/Downloads/Google-Drive-Miner",
    "/Users/ewansair/Downloads/Google-Drive-Miner 2"
]
OUTPUT_DIR = "/Users/ewansair/Vaults/Ewan/02-extracted-data"

# Create output dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Central Ops Voice/Text API for processing
# Allows routing over Tailscale to the Beast (macairm5) or LiteLLM
API_URL = os.environ.get("OLLAMA_URL", "http://localhost:8004/api/generate") 
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB limit to prevent OOM

def crawl_directory(target_paths):
    files = []
    extensions = ["*.md", "*.txt", "*.json", "*.log"]
    
    for path in target_paths:
        print(f"[*] Hound Dog is sniffing: {path}")
        for ext in extensions:
            files.extend(glob.glob(f"{path}/**/{ext}", recursive=True))
            
    return files

async def extract_data(file_path):
    logger.info(f"[*] DocBench extracting: {file_path}")
    
    # Check file size before loading into memory
    if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
        logger.warning(f"[SKIP] File too large for extraction (>5MB): {file_path}")
        return "Extraction failed: File too large"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        logger.warning(f"[SKIP] Binary or non-UTF8 file detected: {file_path}")
        return "Extraction failed: Not a text file"

    prompt = f"""
    You are the Amplified Partners DocBench Extraction Engine.
    Analyze the following raw document and extract the core data into a comprehensive, long-form structured format.
    
    You must extract the content into exactly four categories. For EVERY single item extracted, you MUST provide an "Attribute" (who said it, source file, context, or origin) if possible. Do not summarize the raw voice; preserve it.
    
    1. **Blogs**: Identify and extract full, coherent narratives or stories that can be published as long-form blog posts. Preserve the author's voice entirely.
    2. **Quotes**: Extract specific, powerful, quotable sentences or statements.
    3. **Paragraphs**: Extract standalone, high-value paragraphs that explain a concept, a process, or a principle.
    4. **Nuggets**: Extract short, punchy facts, data points, or core logic pieces.

    Document:
    {content}
    """
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                API_URL,
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2
                    }
                },
                timeout=300.0  # Local inference might take longer
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
    except httpx.RequestError as e:
        logger.error(f"API Request failed: {str(e)}")
        return f"Extraction failed: API unavailable ({API_URL})"
    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        return f"Extraction failed: {str(e)}"

async def run_pipeline():
    files = crawl_directory(TARGET_DIRS)
    print(f"[*] Hound Dog found {len(files)} orphaned/raw files.")

    seen_sha256 = set()
    seen_fuzzy = []

    for file_path in files:
        if "02-extracted-data" in file_path:
            continue # Skip already extracted data
            
        # --- TIER 1 & 2 DEDUPLICATION ---
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
                
            # 1. SHA-256 Exact Match
            exact_hash = hashlib.sha256(raw_bytes).hexdigest()
            if exact_hash in seen_sha256:
                logger.info(f"[SKIP] Exact Duplicate (SHA-256): {os.path.basename(file_path)}")
                continue
            seen_sha256.add(exact_hash)
            
            # 2. ppdeep Fuzzy Hash Match (only if available)
            if HAS_PPDEEP:
                fuzzy_hash = ppdeep.hash(raw_bytes)
                is_fuzzy_dup = False
                for seen_fh in seen_fuzzy:
                    # If similarity > 95, it's a near-duplicate
                    if ppdeep.compare(fuzzy_hash, seen_fh) > 95:
                        is_fuzzy_dup = True
                        break
                        
                if is_fuzzy_dup:
                    logger.info(f"[SKIP] Near-Duplicate (Fuzzy Hash >95%): {os.path.basename(file_path)}")
                    continue
                seen_fuzzy.append(fuzzy_hash)
        except Exception as e:
            logger.warning(f"[ERROR] Deduplication failed for {file_path}: {e}")
            continue

        logger.info(f"\n--- Mining: {os.path.basename(file_path)} ---")
        extracted_content = await extract_data(file_path)
        
        # Save output
        filename = Path(file_path).stem + "_extraction.md"
        out_path = os.path.join(OUTPUT_DIR, filename)
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# DocBench Extraction: {Path(file_path).stem}\n\n")
            f.write(extracted_content)
            
        print(f"[+] Extraction saved to: {out_path}")

import sys

if __name__ == "__main__":
    print("=============================================")
    print(" HOUND DOG \u0026 DOCBENCH: FORENSIC DATA MINING")
    print("=============================================")
    
    # Allow overriding TARGET_DIRS via command-line arguments
    if len(sys.argv) > 1:
        TARGET_DIRS = sys.argv[1:]
        logger.info(f"Target directories overridden by command line: {TARGET_DIRS}")
        
    asyncio.run(run_pipeline())
    print("\n[*] Data Mining Complete. Ready for PUDDING Labelling.")
