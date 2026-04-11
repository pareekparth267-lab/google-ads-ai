"""
Run this once:  python fix_app.py app_v13.py
It fixes the 2 bugs causing fetch + agents to fail, then saves app_v13.py in place.
"""
import sys, re, os, shutil

target = sys.argv[1] if len(sys.argv) > 1 else "app_v13.py"
if not os.path.exists(target):
    print(f"❌ File not found: {target}")
    sys.exit(1)

with open(target, "r", encoding="utf-8") as f:
    src = f.read()

orig = src
fixes = 0

# ── FIX 1: add "import re" if missing ──────────────────────────
if "import re\n" not in src and "import re " not in src:
    # Insert after the last stdlib import block (after "import threading")
    src = src.replace(
        "import threading\nfrom urllib.parse import",
        "import re\nimport threading\nfrom urllib.parse import",
        1
    )
    if "import re" in src:
        print("✅ Fix 1 applied: added 'import re'")
        fixes += 1
    else:
        # fallback: insert right after "import hashlib" near top
        src = src.replace("import hashlib\n", "import re\nimport hashlib\n", 1)
        print("✅ Fix 1 applied (fallback): added 'import re'")
        fixes += 1
else:
    print("ℹ️  Fix 1 skipped: 'import re' already present")

# ── FIX 2: add missing @app.get("/history") decorator ──────────
if '@app.get("/history")' not in src and "async def history(" in src:
    src = src.replace(
        "async def history(_: None = Depends(verify_key)):",
        '@app.get("/history")\nasync def history(_: None = Depends(verify_key)):',
        1
    )
    print("✅ Fix 2 applied: added @app.get('/history') decorator")
    fixes += 1
else:
    print("ℹ️  Fix 2 skipped: decorator already present or function not found")

# ── FIX 3: Remove location words from A04 prompt ───────────────
old_a04_hint = '5 service-only themes for {d.business_type}:'
new_a04_hint = '5 service-only themes for {d.business_type} (NO location names — service actions only):'
if old_a04_hint in src:
    src = src.replace(old_a04_hint, new_a04_hint)
    print("✅ Fix 3 applied: A04 prompt reinforced (no location names)")
    fixes += 1

if fixes == 0 and src == orig:
    print("⚠️  No changes made — file may already be patched or structure differs.")
    sys.exit(0)

# Backup original
shutil.copy(target, target + ".bak")
print(f"📦 Backup saved: {target}.bak")

with open(target, "w", encoding="utf-8") as f:
    f.write(src)

print(f"\n✅ Done — {fixes} fix(es) applied to {target}")
print("▶  Restart server:  uvicorn app_v13:app --host 0.0.0.0 --port 8000 --reload")
