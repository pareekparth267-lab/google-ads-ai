"""
Run this in your project folder: python add_key_rotation.py
Patches app_v13.py with automatic Groq key rotation.

BEFORE RUNNING:
Add your extra keys to .env:
  GROQ_API_KEY=gsk_key1
  GROQ_API_KEY_1=gsk_key2
  GROQ_API_KEY_2=gsk_key3
  GROQ_API_KEY_3=gsk_key4
"""
import os, shutil

# ── Find the file ─────────────────────────────────────────────
py_file = next((f for f in ['app_v13.py', 'app_v12.py'] if os.path.exists(f)), None)
if not py_file:
    print("ERROR: app_v13.py not found. Run this from your project folder.")
    exit(1)

# Backup original
shutil.copy(py_file, py_file.replace('.py', '_backup.py'))
print(f"✅ Backup saved: {py_file.replace('.py', '_backup.py')}")

with open(py_file, 'r', encoding='utf-8') as f:
    py = f.read()

# ══════════════════════════════════════════════════════════════
# PATCH 1: Replace the Config section to load multiple keys
# ══════════════════════════════════════════════════════════════

OLD_CONFIG = """GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")"""

NEW_CONFIG = """GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")

# ── Multi-key rotation: load all GROQ_API_KEY, GROQ_API_KEY_1..9 ──
_ALL_GROQ_KEYS = []
for _ki in [""] + [f"_{i}" for i in range(1, 10)]:
    _k = os.getenv(f"GROQ_API_KEY{_ki}", "").strip()
    if _k and _k not in _ALL_GROQ_KEYS:
        _ALL_GROQ_KEYS.append(_k)
_groq_key_idx = 0   # current key index

def _next_groq_key() -> str:
    global _groq_key_idx
    if not _ALL_GROQ_KEYS:
        return GROQ_API_KEY
    key = _ALL_GROQ_KEYS[_groq_key_idx % len(_ALL_GROQ_KEYS)]
    _groq_key_idx += 1
    return key

def _rotate_on_429():
    \"\"\"Called when a key hits 429 — force switch to next key.\"\"\"
    global _groq_key_idx
    _groq_key_idx += 1
    if len(_ALL_GROQ_KEYS) > 1:
        next_key_preview = _ALL_GROQ_KEYS[_groq_key_idx % len(_ALL_GROQ_KEYS)][:12]
        log.info(f"🔄 Rotated to key #{_groq_key_idx % len(_ALL_GROQ_KEYS) + 1}/{len(_ALL_GROQ_KEYS)}: {next_key_preview}...")"""

if OLD_CONFIG in py:
    py = py.replace(OLD_CONFIG, NEW_CONFIG)
    print("✅ Patch 1: Multi-key loader added")
else:
    print("⚠️  Patch 1: Config line not found — adding key loader at top of file")
    # Inject after imports
    py = py.replace(
        'GROQ_BASE_URL = "https://api.groq.com/openai/v1"',
        NEW_CONFIG + '\n\nGROQ_BASE_URL = "https://api.groq.com/openai/v1"'
    )

# ══════════════════════════════════════════════════════════════
# PATCH 2: Replace groq_chat function with key-rotating version
# ══════════════════════════════════════════════════════════════

OLD_GROQ_CHAT = '''def groq_chat(system: str, user: str, max_tokens: int = 1500) -> str:
    """Single Groq API call with automatic retry on 429 and per-call throttling."""
    global _groq_last_call_ts
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set in .env")

    # ── Enforce minimum gap between calls (token bucket) ──────────
    now  = time.time()
    wait = _MIN_GAP_SECONDS - (now - _groq_last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _groq_last_call_ts = time.time()

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":      GROQ_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system + "\\n\\nRespond with valid JSON only. No markdown fences, no preamble."},
            {"role": "user",   "content": user},
        ],
    }
    for attempt in range(6):
        try:
            with httpx.Client(timeout=90) as client:
                r = client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
                if r.status_code == 429:
                    # Parse Retry-After header if present, else exponential backoff
                    retry_after = int(r.headers.get("retry-after", 0))
                    wait = max(retry_after, 2 ** attempt + 2)
                    log.warning(f"Groq 429 — waiting {wait}s (attempt {attempt+1}/6)")
                    time.sleep(15)
                    _groq_last_call_ts = time.time()  # reset gap after wait
                    continue
                r.raise_for_status()
                _groq_last_call_ts = time.time()
                return r.json()["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            if attempt < 5:
                w = 2 ** attempt + 2
                log.warning(f"Groq HTTP {e.response.status_code} — retry {attempt+1} in {w}s")
                time.sleep(w)
            else:
                raise
    raise RuntimeError("Groq API failed after 6 retries")'''

NEW_GROQ_CHAT = '''def groq_chat(system: str, user: str, max_tokens: int = 1500) -> str:
    """Single Groq API call with KEY ROTATION + retry on 429."""
    global _groq_last_call_ts

    keys = _ALL_GROQ_KEYS if _ALL_GROQ_KEYS else [GROQ_API_KEY]
    if not any(keys):
        raise RuntimeError("GROQ_API_KEY not set in .env")

    # Enforce minimum gap between calls
    now  = time.time()
    gap  = _MIN_GAP_SECONDS - (now - _groq_last_call_ts)
    if gap > 0:
        time.sleep(gap)
    _groq_last_call_ts = time.time()

    payload = {
        "model":       GROQ_MODEL,
        "max_tokens":  max_tokens,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system + "\\n\\nRespond with valid JSON only. No markdown fences, no preamble."},
            {"role": "user",   "content": user},
        ],
    }

    MAX_ATTEMPTS = len(keys) * 3   # try each key up to 3 times
    consecutive_429 = 0

    for attempt in range(MAX_ATTEMPTS):
        api_key = _next_groq_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }
        try:
            with httpx.Client(timeout=90) as client:
                r = client.post(f"{GROQ_BASE_URL}/chat/completions",
                                json=payload, headers=headers)

                if r.status_code == 200:
                    consecutive_429 = 0
                    _groq_last_call_ts = time.time()
                    return r.json()["choices"][0]["message"]["content"].strip()

                if r.status_code == 429:
                    consecutive_429 += 1
                    _rotate_on_429()

                    # If ALL keys are exhausted (every key returned 429)
                    if consecutive_429 >= len(keys):
                        # Cap wait at 60s max regardless of retry-after header
                        retry_after = min(int(r.headers.get("retry-after", 30)), 60)
                        log.warning(f"All {len(keys)} key(s) rate-limited — waiting {retry_after}s (attempt {attempt+1})")
                        time.sleep(retry_after)
                        consecutive_429 = 0   # reset and try again
                    else:
                        log.info(f"Key {attempt % len(keys) + 1} hit 429 — switching to next key instantly")
                        time.sleep(1)  # tiny pause before next key
                    continue

                if r.status_code == 401:
                    log.error(f"Key {api_key[:12]}... is invalid (401) — skipping")
                    time.sleep(0.5)
                    continue

                r.raise_for_status()

        except httpx.HTTPStatusError as e:
            if attempt < MAX_ATTEMPTS - 1:
                w = min(2 ** (attempt // len(keys)) + 1, 30)
                log.warning(f"Groq HTTP {e.response.status_code} — retry in {w}s")
                time.sleep(w)
            else:
                raise
        except Exception as e:
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(3)
            else:
                raise

    raise RuntimeError(f"Groq API failed after {MAX_ATTEMPTS} attempts across {len(keys)} key(s)")'''

if OLD_GROQ_CHAT in py:
    py = py.replace(OLD_GROQ_CHAT, NEW_GROQ_CHAT)
    print("✅ Patch 2: groq_chat replaced with key-rotating version")
else:
    print("⚠️  Patch 2: groq_chat exact match not found — injecting new version")
    # Find and replace by function signature
    import re
    py = re.sub(
        r'def groq_chat\(system: str, user: str, max_tokens: int = 1500\) -> str:.*?raise RuntimeError\("Groq API failed after 6 retries"\)',
        NEW_GROQ_CHAT,
        py,
        flags=re.DOTALL
    )
    print("✅ Patch 2: groq_chat replaced via regex")

# ══════════════════════════════════════════════════════════════
# PATCH 3: Fix ai_text to also use key rotation
# ══════════════════════════════════════════════════════════════

OLD_AI_TEXT_429 = """                if r.status_code == 429:
                    wait = 2 ** attempt + 1
                    log.warning(f"Groq 429 (text) — waiting {wait}s")
                    time.sleep(wait)
                    continue"""

NEW_AI_TEXT_429 = """                if r.status_code == 429:
                    _rotate_on_429()
                    wait = min(30, 2 ** attempt + 1)
                    log.warning(f"Groq 429 (text) — key rotated, waiting {wait}s")
                    time.sleep(wait)
                    continue"""

if OLD_AI_TEXT_429 in py:
    py = py.replace(OLD_AI_TEXT_429, NEW_AI_TEXT_429)
    print("✅ Patch 3: ai_text key rotation added")
else:
    print("⚠️  Patch 3: ai_text 429 handler not found exactly")

# ══════════════════════════════════════════════════════════════
# PATCH 4: Fix ai_text to also use rotating key (header)
# ══════════════════════════════════════════════════════════════

OLD_AI_TEXT_HEADER = '    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}'
NEW_AI_TEXT_HEADER = '    headers = {"Authorization": f"Bearer {_next_groq_key()}", "Content-Type": "application/json"}'

if OLD_AI_TEXT_HEADER in py:
    py = py.replace(OLD_AI_TEXT_HEADER, NEW_AI_TEXT_HEADER)
    print("✅ Patch 4: ai_text now uses rotating key")

# ══════════════════════════════════════════════════════════════
# PATCH 5: Add startup log showing key count
# ══════════════════════════════════════════════════════════════

OLD_STARTUP = '    log.info("✅ Google Ads Enterprise v13 — 91 Agents Ready")'
NEW_STARTUP = '''    key_count = len(_ALL_GROQ_KEYS) if _ALL_GROQ_KEYS else 1
    log.info(f"✅ Google Ads Enterprise v13 — 91 Agents Ready | {key_count} Groq key(s) loaded")
    if key_count > 1:
        log.info(f"🔄 Key rotation active: {key_count} keys = ~{key_count * 14400:,} requests/day free capacity")'''

if OLD_STARTUP in py:
    py = py.replace(OLD_STARTUP, NEW_STARTUP)
    print("✅ Patch 5: Startup message shows key count")

# ══════════════════════════════════════════════════════════════
# PATCH 6: Add /key-status endpoint
# ══════════════════════════════════════════════════════════════

KEY_STATUS_ENDPOINT = '''
@app.get("/key-status")
async def key_status():
    """Show how many Groq keys are loaded and which is currently active."""
    keys = _ALL_GROQ_KEYS if _ALL_GROQ_KEYS else [GROQ_API_KEY]
    return {
        "total_keys": len(keys),
        "current_key_index": _groq_key_idx % len(keys),
        "daily_capacity_estimate": len(keys) * 14400,
        "runs_per_day_estimate": (len(keys) * 14400) // 91,
        "keys_preview": [k[:12] + "..." for k in keys if k],
        "how_to_add_more": "Add GROQ_API_KEY_1=..., GROQ_API_KEY_2=... to .env file",
        "get_free_keys": "console.groq.com — free, no card required",
    }

'''

# Insert before the last if __name__ block
if 'if __name__ == "__main__":' in py:
    py = py.replace(
        'if __name__ == "__main__":',
        KEY_STATUS_ENDPOINT + 'if __name__ == "__main__":',
        1
    )
    print("✅ Patch 6: /key-status endpoint added")

# ══════════════════════════════════════════════════════════════
# Write output
# ══════════════════════════════════════════════════════════════
with open(py_file, 'w', encoding='utf-8') as f:
    f.write(py)

print(f"\n{'='*55}")
print(f"✅ ALL PATCHES APPLIED to {py_file}")
print(f"   File size: {len(py):,} chars")
print(f"{'='*55}")
print(f"""
NEXT STEPS:
-----------
1. Add your extra Groq keys to .env:
   GROQ_API_KEY=gsk_your_first_key
   GROQ_API_KEY_1=gsk_second_key
   GROQ_API_KEY_2=gsk_third_key
   GROQ_API_KEY_3=gsk_fourth_key

2. Restart the server:
   uvicorn app_v13:app --reload --port 5000

3. Check http://localhost:5000/key-status
   → shows how many keys loaded + daily capacity

HOW IT WORKS:
-------------
• Agent 1  → uses key 1
• Agent 2  → uses key 2
• Agent 3  → uses key 3
• Agent 4  → uses key 4
• Agent 5  → uses key 1 (cycles back)
• If key 1 hits 429 → instantly switches to key 2
  (no waiting 2357 seconds anymore!)
• All 4 keys exhausted → waits max 60s, then retries

WITH 4 KEYS:
  14,400 × 4 = 57,600 requests/day
  91 agents per run = ~6 full runs per day FREE
""")
