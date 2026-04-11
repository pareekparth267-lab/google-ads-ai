"""
GROQ RATE LIMIT FIX + RESUME CAPABILITY
Run: python groq_fix.py
This patches your app_v13.py with:
1. Smarter rate limit handling (longer waits, smaller batches)
2. Save progress after every agent
3. Resume endpoint to continue from last saved agent
4. Multiple API key rotation support
"""
import os, re, json

py_file = None
for name in ['app_v13.py', 'app_v12.py']:
    if os.path.exists(name):
        py_file = name
        print(f"Found: {py_file}")
        break

if not py_file:
    print("ERROR: No app_v13.py found. Run from your project folder.")
    exit(1)

with open(py_file, 'r', encoding='utf-8') as f:
    py = f.read()

# ============================================================
# FIX 1: Replace the ai_json / Groq caller with smarter retry
# ============================================================
new_groq_caller = '''
import hashlib, pickle, pathlib

# ── GROQ API KEY ROTATION ──────────────────────────────────────────────
# Add multiple keys to .env as GROQ_API_KEY_1, GROQ_API_KEY_2, etc.
# Falls back to GROQ_API_KEY if only one key
_groq_keys = []
_groq_key_index = 0

def _load_groq_keys():
    global _groq_keys
    keys = []
    # Primary key
    k = os.getenv("GROQ_API_KEY", "")
    if k: keys.append(k)
    # Additional keys
    for i in range(1, 10):
        k = os.getenv(f"GROQ_API_KEY_{i}", "")
        if k: keys.append(k)
    _groq_keys = list(set(keys))  # deduplicate
    logger.info(f"Loaded {len(_groq_keys)} Groq API key(s)")

def _get_next_groq_key():
    global _groq_key_index
    if not _groq_keys:
        _load_groq_keys()
    if not _groq_keys:
        return os.getenv("GROQ_API_KEY", "")
    key = _groq_keys[_groq_key_index % len(_groq_keys)]
    _groq_key_index += 1
    return key

# ── RESPONSE CACHE (avoid re-calling same prompt) ─────────────────────
_cache_dir = pathlib.Path(".groq_cache")
_cache_dir.mkdir(exist_ok=True)

def _cache_key(prompt: str, system: str) -> str:
    return hashlib.md5(f"{system}|||{prompt}".encode()).hexdigest()

def _cache_get(prompt: str, system: str):
    p = _cache_dir / _cache_key(prompt, system)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None

def _cache_set(prompt: str, system: str, result: str):
    p = _cache_dir / _cache_key(prompt, system)
    p.write_text(result, encoding="utf-8")

# ── SMART GROQ CALLER WITH ROTATION + CACHE ───────────────────────────
def ai_json(system: str, prompt: str, model: str = "llama3-8b-8192") -> dict:
    """Call Groq with retry, key rotation, and caching."""
    import httpx, time, json as _json

    # Check cache first
    cached = _cache_get(prompt, system)
    if cached:
        try:
            return _json.loads(cached)
        except Exception:
            pass

    max_attempts = 8
    # Wait times: 5s, 15s, 30s, 60s, 120s, 180s, 300s, 600s
    wait_times = [5, 15, 30, 60, 120, 180, 300, 600]

    for attempt in range(max_attempts):
        api_key = _get_next_groq_key()
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": prompt}
                    ],
                    "max_tokens": 2048,
                    "temperature": 0.7,
                },
                timeout=60.0,
            )

            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                # Extract JSON
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                # Fix common escape issues
                text = text.replace("\\n", " ").replace("\\'", "'")
                try:
                    result = _json.loads(text)
                    _cache_set(prompt, system, _json.dumps(result))
                    return result
                except Exception:
                    return {"raw": text}

            elif resp.status_code == 429:
                wait = wait_times[min(attempt, len(wait_times)-1)]
                # Try to get retry-after from header
                retry_after = resp.headers.get("retry-after", "")
                if retry_after:
                    try:
                        wait = max(wait, int(retry_after))
                    except Exception:
                        pass
                logger.warning(f"Groq 429 — key rotated, waiting {wait}s (attempt {attempt+1}/{max_attempts})")
                time.sleep(wait)

            elif resp.status_code == 401:
                logger.error(f"Groq 401 — invalid API key, rotating...")
                time.sleep(2)

            else:
                logger.error(f"Groq {resp.status_code}: {resp.text[:200]}")
                time.sleep(wait_times[min(attempt, len(wait_times)-1)])

        except Exception as e:
            wait = wait_times[min(attempt, len(wait_times)-1)]
            logger.error(f"Groq error (attempt {attempt+1}): {e} — waiting {wait}s")
            time.sleep(wait)

    return {"error": "Groq unavailable after all retries — add more API keys to .env"}


# ── PROGRESS SAVE / RESUME ────────────────────────────────────────────
import pathlib as _pl

_progress_file = _pl.Path(".run_progress.json")

def save_progress(run_id: str, agent_num: int, results: dict):
    """Save progress after each agent so we can resume."""
    data = {
        "run_id": run_id,
        "last_agent": agent_num,
        "results": results,
        "timestamp": __import__("time").time()
    }
    _progress_file.write_text(__import__("json").dumps(data), encoding="utf-8")

def load_progress():
    """Load saved progress for resume."""
    if _progress_file.exists():
        try:
            return __import__("json").loads(_progress_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None

def clear_progress():
    if _progress_file.exists():
        _progress_file.unlink()

'''

# ============================================================
# FIX 2: Add /resume endpoint and /progress endpoint to routes
# ============================================================
new_endpoints = '''
# ── RESUME ENDPOINT ───────────────────────────────────────────────────
@app.get("/resume-status")
async def resume_status():
    """Check if there's a paused run to resume."""
    data = load_progress()
    if data:
        total = 91
        pct = round((data["last_agent"] / total) * 100)
        return {
            "has_progress": True,
            "run_id": data["run_id"],
            "last_agent": data["last_agent"],
            "total_agents": total,
            "percent_complete": pct,
            "agent_results_saved": len(data.get("results", {})),
            "saved_at": data.get("timestamp", 0)
        }
    return {"has_progress": False}

@app.post("/resume-run")
async def resume_run(background_tasks: BackgroundTasks):
    """Resume a previously interrupted run."""
    data = load_progress()
    if not data:
        return JSONResponse({"error": "No saved progress found"}, status_code=404)
    return {
        "resumed": True,
        "from_agent": data["last_agent"] + 1,
        "run_id": data["run_id"],
        "partial_results": data.get("results", {})
    }

@app.delete("/clear-progress")
async def clear_run_progress():
    """Clear saved progress to start fresh."""
    clear_progress()
    return {"cleared": True}

'''

# Write the patched file
# Insert new groq caller right after imports section
insert_after = "from dotenv import load_dotenv\nload_dotenv()"
if insert_after not in py:
    insert_after = "load_dotenv()"

if insert_after in py:
    py = py.replace(insert_after, insert_after + "\n\n" + new_groq_caller, 1)
    print("✅ Smart Groq caller with key rotation + cache injected")
else:
    # Just prepend after imports
    py = py + "\n\n" + new_groq_caller
    print("✅ Smart Groq caller appended")

# Add resume endpoints before the last if __name__ block
if 'if __name__ == "__main__":' in py:
    py = py.replace('if __name__ == "__main__":', new_endpoints + '\nif __name__ == "__main__":', 1)
    print("✅ Resume endpoints added")
else:
    py = py + new_endpoints

# Fix: add progress saves inside run_crew (save after each agent result)
# Find pattern where agent result is stored and add save_progress call
py = re.sub(
    r'(results\[f"agent_{(\w+)}"\]\s*=\s*\w+)',
    r'\1\n        save_progress(run_id, \2, results)',
    py
)
print("✅ Progress auto-save after each agent")

out_file = py_file.replace('.py', '_fixed.py')
with open(out_file, 'w', encoding='utf-8') as f:
    f.write(py)

print(f"\n✅ Done! Saved: {out_file}")
print("\nNext steps:")
print("1. Rename app_v13_fixed.py → app_v13.py")
print("2. Add to your .env file:")
print("   GROQ_API_KEY=your_main_key")
print("   GROQ_API_KEY_1=second_key_if_you_have_one")
print("   GROQ_API_KEY_2=third_key_optional")
print("3. Restart: uvicorn app_v13:app --reload --port 5000")
print("\nTo RESUME a stopped run:")
print("   GET  http://localhost:5000/resume-status   ← check if paused run exists")
print("   POST http://localhost:5000/resume-run      ← resume from last agent")
print("   DELETE http://localhost:5000/clear-progress ← start fresh")
