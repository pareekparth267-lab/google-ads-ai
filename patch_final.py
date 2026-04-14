"""
FINAL PATCH — fixes the REAL issues in app_v13.py
Run: python patch_final.py
"""
import re, shutil, sys
from pathlib import Path

TARGET = Path("app_v13.py")
if not TARGET.exists():
    print("❌ app_v13.py not found — run this from C:\\google ads ai agents 111")
    sys.exit(1)

# Backup
shutil.copy(TARGET, TARGET.with_name("app_v13_backup_final.py"))
print("✅ Backed up to app_v13_backup_final.py")

src = TARGET.read_text(encoding="utf-8")
original = src
fixes = []

# ══════════════════════════════════════════════════════
# FIX 1 — Agent 17 max_tokens 700 → 2500
# ══════════════════════════════════════════════════════
old = '''        max_tokens=700,
        agent_num=17
    )'''
new = '''        max_tokens=2500,
        agent_num=17
    )'''
if old in src:
    src = src.replace(old, new, 1)
    fixes.append("✅ A17 Campaign Architect: max_tokens 700 → 2500")
else:
    fixes.append("⚠️  A17 max_tokens not found")

# ══════════════════════════════════════════════════════
# FIX 2 — Agent 49 max_tokens 600 → 1800
# ══════════════════════════════════════════════════════
old = '''        max_tokens=600,
        agent_num=49
    )'''
new = '''        max_tokens=1800,
        agent_num=49
    )'''
if old in src:
    src = src.replace(old, new, 1)
    fixes.append("✅ A49 Dayparting Optimizer: max_tokens 600 → 1800")
else:
    fixes.append("⚠️  A49 max_tokens not found")

# ══════════════════════════════════════════════════════
# FIX 3 — Agent 56 max_tokens 600 → 1800
# ══════════════════════════════════════════════════════
old = '''        max_tokens=600,
        agent_num=56
    )'''
new = '''        max_tokens=1800,
        agent_num=56
    )'''
if old in src:
    src = src.replace(old, new, 1)
    fixes.append("✅ A56 Lookalike Audience Builder: max_tokens 600 → 1800")
else:
    fixes.append("⚠️  A56 max_tokens not found")

# ══════════════════════════════════════════════════════
# FIX 4 — Agent 81 max_tokens 600 → 1800 + NO LOCATION in prompt
# ══════════════════════════════════════════════════════
old = '''def agent_81_keyword_expander(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 81: Keyword Expander")
    return ai_json(
        "You are a keyword expansion and opportunity discovery expert for Google Ads.",
        f"""Discover keyword expansion opportunities for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "expansion_keyword_clusters": [
    {{
      "theme": "",
      "keywords": [...],
      "estimated_monthly_volume": number,
      "competition": "low|medium|high",
      "recommended_match_type": "",
      "priority": "high|medium|low"
    }}
  ],
  "long_tail_opportunities": [...],
  "question_based_keywords": [...],
  "competitor_gap_keywords": [...],
  "trending_keywords": [...],
  "negative_list_expansion": [...],
  "weekly_expansion_cadence": ""
}}"""
    ,
        max_tokens=600,
        agent_num=81
    )'''

new = '''def agent_81_keyword_expander(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 81: Keyword Expander")
    return ai_json(
        "You are a keyword expansion expert for Google Ads. CRITICAL RULE: ALL keywords must be SERVICE-BASED ONLY. Never include city names, state names, 'near me', 'nearby', 'local', or any geographic modifiers in any keyword. Generate generic service keywords that work in any location.",
        f"""Discover keyword expansion opportunities for {d.business_name} ({d.business_type}).
STRICT RULE: Do NOT include {d.target_location} or any location words in any keyword. Service keywords only.
Return JSON: {{
  "expansion_keyword_clusters": [
    {{
      "theme": "",
      "keywords": [...],
      "estimated_monthly_volume": number,
      "competition": "low|medium|high",
      "recommended_match_type": "",
      "priority": "high|medium|low"
    }}
  ],
  "long_tail_opportunities": [...],
  "question_based_keywords": [...],
  "competitor_gap_keywords": [...],
  "trending_keywords": [...],
  "negative_list_expansion": [...],
  "weekly_expansion_cadence": ""
}}"""
    ,
        max_tokens=1800,
        agent_num=81
    )'''

if 'def agent_81_keyword_expander' in src:
    src = src.replace(old, new, 1)
    if 'SERVICE-BASED ONLY' in src:
        fixes.append("✅ A81 Keyword Expander: max_tokens 600 → 1800 + NO LOCATION prompt added")
    else:
        fixes.append("⚠️  A81 prompt replace failed (whitespace mismatch) — applying regex fallback")
        # Regex fallback for max_tokens only
        src = re.sub(
            r'(agent_num=81\s*\))',
            lambda m: m.group(0),
            src
        )
        # Try a simpler approach — just fix the tokens
        src = re.sub(
            r'(def agent_81_keyword_expander.*?max_tokens=)600(\s*,\s*agent_num=81)',
            r'\g<1>1800\2',
            src, flags=re.DOTALL
        )
        fixes.append("✅ A81 max_tokens fixed via regex")
else:
    fixes.append("⚠️  A81 function not found")

# ══════════════════════════════════════════════════════
# FIX 5 — Agent 04 STAG — add NO LOCATION to system prompt
# ══════════════════════════════════════════════════════
old_04_sys = '"You are a Google Ads keyword architect. Return ONLY valid compact JSON. No explanation."'
new_04_sys = '"You are a Google Ads keyword architect. Return ONLY valid compact JSON. No explanation. CRITICAL: All keywords must be SERVICE-BASED only — NO city names, NO state names, NO \'near me\', NO geographic modifiers in any keyword."'
if old_04_sys in src:
    src = src.replace(old_04_sys, new_04_sys, 1)
    fixes.append("✅ A04 STAG Keywords: NO LOCATION system prompt added")
else:
    fixes.append("⚠️  A04 system prompt not found (may already be patched)")

# ══════════════════════════════════════════════════════
# FIX 6 — Agent 07 Intent Clustering — add NO LOCATION
# ══════════════════════════════════════════════════════
old_07_sys = '"You are an intent clustering expert for Google Ads campaign organization."'
new_07_sys = '"You are an intent clustering expert for Google Ads campaign organization. CRITICAL: All keywords must be SERVICE-BASED only — NO city names, NO state names, NO \'near me\', NO geographic modifiers in any keyword."'
if old_07_sys in src:
    src = src.replace(old_07_sys, new_07_sys, 1)
    fixes.append("✅ A07 Intent Clustering: NO LOCATION system prompt added")
else:
    fixes.append("⚠️  A07 system prompt not found")

# ══════════════════════════════════════════════════════
# FIX 7 — Agent 82 Competitor Gap — add NO LOCATION
# ══════════════════════════════════════════════════════
old_82_sys = '"You are a competitive keyword gap analysis expert for Google Ads."'
new_82_sys = '"You are a competitive keyword gap analysis expert for Google Ads. CRITICAL: All keywords must be SERVICE-BASED only — NO city names, NO state names, NO \'near me\', NO geographic modifiers."'
if old_82_sys in src:
    src = src.replace(old_82_sys, new_82_sys, 1)
    fixes.append("✅ A82 Competitor Gap: NO LOCATION system prompt added")
else:
    fixes.append("⚠️  A82 system prompt not found")

# ══════════════════════════════════════════════════════
# FIX 8 — Agents 86, 87, 88 missing agent_num in run() calls
# ══════════════════════════════════════════════════════
old_86 = "brain      = await run(agent_86_campaign_brain)"
new_86 = "brain      = await run(agent_86_campaign_brain, 86)"
if old_86 in src:
    src = src.replace(old_86, new_86, 1)
    fixes.append("✅ Agent 86: agent_num=86 added to run() call")
else:
    fixes.append("⚠️  Agent 86 run() call not found")

old_87 = "scheduler  = await run(agent_87_agent_scheduler)"
new_87 = "scheduler  = await run(agent_87_agent_scheduler, 87)"
if old_87 in src:
    src = src.replace(old_87, new_87, 1)
    fixes.append("✅ Agent 87: agent_num=87 added to run() call")
else:
    fixes.append("⚠️  Agent 87 run() call not found")

old_88 = "aggregator = await run(agent_88_signal_aggregator)"
new_88 = "aggregator = await run(agent_88_signal_aggregator, 88)"
if old_88 in src:
    src = src.replace(old_88, new_88, 1)
    fixes.append("✅ Agent 88: agent_num=88 added to run() call")
else:
    fixes.append("⚠️  Agent 88 run() call not found")

# ══════════════════════════════════════════════════════
# FIX 9 — groq_chat system prompt: strengthen JSON + no location
# ══════════════════════════════════════════════════════
old_groq_sys = '"content": system + "\\n\\nRespond with valid JSON only. No markdown fences, no preamble."'
new_groq_sys = '"content": system + "\\n\\nRespond with valid JSON only. No markdown fences, no preamble. NEVER include city names, state names, \'near me\' or geographic modifiers inside keyword arrays."'
if old_groq_sys in src:
    src = src.replace(old_groq_sys, new_groq_sys, 1)
    fixes.append("✅ Groq system prompt: global NO LOCATION rule added")
else:
    fixes.append("⚠️  Groq system prompt line not found")

# ══════════════════════════════════════════════════════
# Write + verify
# ══════════════════════════════════════════════════════
Target_path = TARGET
Target_path.write_text(src, encoding="utf-8")

print("\n📋 Fix Results:")
for f in fixes:
    print(f"  {f}")

# Python syntax check
import subprocess
result = subprocess.run([sys.executable, "-m", "py_compile", str(TARGET)], capture_output=True, text=True)
if result.returncode == 0:
    print(f"\n✅ Python syntax check PASSED on {TARGET}")
else:
    print(f"\n❌ Syntax error — restoring backup!")
    shutil.copy(TARGET.with_name("app_v13_backup_final.py"), TARGET)
    print(result.stderr)
    sys.exit(1)

changed = sum(1 for a, b in zip(original.splitlines(), src.splitlines()) if a != b)
print(f"   {changed} lines changed")
print("\n🚀 Ready to push:")
print('   git add app_v13.py')
print('   git commit -m "Fix: token limits + location keywords + agent 86/87/88 model routing"')
print('   git push')
