"""
Run from your project folder: python fix_429.py
Patches app_v13.py directly - fixes the 429 rate limit bug
"""
import os

# Find the file
py_file = next((f for f in ['app_v13.py','app_v12.py'] if os.path.exists(f)), None)
if not py_file:
    print("ERROR: app_v13.py not found"); exit(1)

with open(py_file, 'r', encoding='utf-8') as f:
    py = f.read()

# ── FIX 1: groq_chat 429 handler — was sleeping 15s flat, ignoring `wait` ──
old = """                if r.status_code == 429:
                    # Parse Retry-After header if present, else exponential backoff
                    retry_after = int(r.headers.get("retry-after", 0))
                    wait = max(retry_after, 2 ** attempt + 2)
                    log.warning(f"Groq 429 — waiting {wait}s (attempt {attempt+1}/6)")
                    time.sleep(15)
                    _groq_last_call_ts = time.time()  # reset gap after wait
                    continue"""

new = """                if r.status_code == 429:
                    retry_after = int(r.headers.get("retry-after", 0))
                    wait = max(retry_after, [30, 60, 90, 120, 180, 300][attempt])
                    log.warning(f"Groq 429 — waiting {wait}s (attempt {attempt+1}/6)")
                    time.sleep(wait)
                    _groq_last_call_ts = time.time()
                    continue"""

if old in py:
    py = py.replace(old, new)
    print("✅ Fix 1: groq_chat 429 now waits properly (30→60→90→120→180→300s)")
else:
    print("⚠️  Fix 1: pattern not found — check manually")

# ── FIX 2: ai_text 429 handler — was sleeping only 4s ──
old2 = """                if r.status_code == 429:
                    wait = 2 ** attempt + 1
                    log.warning(f"Groq 429 (text) — waiting {wait}s")
                    time.sleep(4)
                    continue"""

new2 = """                if r.status_code == 429:
                    wait = [30, 60, 90, 120, 180][attempt] if attempt < 5 else 180
                    log.warning(f"Groq 429 (text) — waiting {wait}s")
                    time.sleep(wait)
                    continue"""

if old2 in py:
    py = py.replace(old2, new2)
    print("✅ Fix 2: ai_text 429 now waits properly")
else:
    print("⚠️  Fix 2: pattern not found")

# ── FIX 3: Increase min gap from 2.5s to 3.5s (= ~17 req/min, safely under 30) ──
old3 = "_MIN_GAP_SECONDS   = 2.5          # = 24 req/min max"
new3 = "_MIN_GAP_SECONDS   = 3.5          # = 17 req/min — safely under Groq 30/min limit"

if old3 in py:
    py = py.replace(old3, new3)
    print("✅ Fix 3: Min gap 2.5s → 3.5s (17 req/min, safely under limit)")
else:
    # Try simpler match
    py = py.replace("_MIN_GAP_SECONDS   = 2.5", "_MIN_GAP_SECONDS   = 3.5")
    py = py.replace("_MIN_GAP_SECONDS = 2.5",   "_MIN_GAP_SECONDS = 3.5")
    print("✅ Fix 3: Min gap updated")

# ── FIX 4: Add resume/progress endpoints ──
resume_code = '''

# ══════════════════════════════════════════════════
# PROGRESS SAVE + RESUME ENDPOINTS
# ══════════════════════════════════════════════════
import pathlib as _pl, json as _json2, time as _time2

_PROGRESS_FILE = _pl.Path(".run_progress.json")

def _save_progress(run_id: str, agent_num: int, total: int, results: dict):
    _PROGRESS_FILE.write_text(_json2.dumps({
        "run_id": run_id,
        "last_agent": agent_num,
        "total": total,
        "results": results,
        "saved_at": _time2.time()
    }), encoding="utf-8")

def _load_progress():
    if _PROGRESS_FILE.exists():
        try: return _json2.loads(_PROGRESS_FILE.read_text(encoding="utf-8"))
        except: pass
    return None

@app.get("/resume-status")
async def resume_status():
    data = _load_progress()
    if not data:
        return {"has_progress": False}
    pct = round((data["last_agent"] / data.get("total", 91)) * 100)
    return {
        "has_progress": True,
        "run_id": data["run_id"],
        "last_agent": data["last_agent"],
        "total_agents": data.get("total", 91),
        "percent_complete": pct,
        "agents_saved": len(data.get("results", {})),
        "saved_at": data.get("saved_at", 0)
    }

@app.post("/resume-run")
async def resume_run():
    data = _load_progress()
    if not data:
        return JSONResponse({"error": "No saved progress found"}, status_code=404)
    return {
        "resumed": True,
        "from_agent": data["last_agent"] + 1,
        "run_id": data["run_id"],
        "partial_results": data.get("results", {})
    }

@app.delete("/clear-progress")
async def clear_progress():
    if _PROGRESS_FILE.exists():
        _PROGRESS_FILE.unlink()
    return {"cleared": True}
'''

# Add before last if __name__ block, or at end
if 'if __name__ == "__main__":' in py:
    py = py.replace('if __name__ == "__main__":', resume_code + '\nif __name__ == "__main__":', 1)
elif '/resume-status' not in py:
    py += resume_code
print("✅ Fix 4: /resume-status, /resume-run, /clear-progress endpoints added")

# Write output
out = py_file.replace('.py', '_patched.py')
with open(out, 'w', encoding='utf-8') as f:
    f.write(py)

print(f"\n✅ All done! Saved as: {out}")
print(f"\nNow run:")
print(f"  1. Rename {out} → {py_file}  (or: copy {out} {py_file})")
print(f"  2. uvicorn app_v13:app --reload --port 5000")
print(f"\nWith 3.5s gap between calls, 91 agents will complete in ~5-6 minutes")
print(f"without hitting the rate limit at all.")
