#!/usr/bin/env python3
"""
Apply all 4 fixes to app_v14.py and index_v14.html
Run: python3 apply_fixes.py app_v14.py index_v14.html
"""

import sys, re

PY_FILE  = "app_v14.py"
HTML_FILE = "index_v14.html"

# ═══════════════════════════════════════════════════════════════
# PYTHON FIXES
# ═══════════════════════════════════════════════════════════════

def fix_python(src: str) -> str:

    # ── FIX 1: Agent 04 — NO location in keywords ──────────────
    old = '''    return ai_json(
        "You are a Google Ads keyword architect. Return ONLY valid compact JSON. No explanation.",
        f"""Build STAG keyword structure for {d.business_name} ({d.business_type}) in {d.target_location}.
RULES: Return compact JSON with NO extra whitespace. Exactly 5 themes, 5 keywords each (25 total).
Each keyword object must have: keyword, match_type (EXACT/PHRASE/BROAD), estimated_volume (high/med/low), estimated_cpc (number).

{{"keywords_by_service":{{"[Theme Name]":[{{"keyword":"[kw]","match_type":"EXACT","estimated_volume":"high","estimated_cpc":3.5}}]}},"total_keywords":25,"recommended_ad_groups":5}}

5 themes for {d.business_type}:""",
        max_tokens=1500,
        agent_num=4,
    )'''

    new = '''    return ai_json(
        "You are a Google Ads keyword architect. Return ONLY valid compact JSON. No explanation.\\n\\n"
        "CRITICAL RULES — violations cause keyword rejection and wasted spend:\\n"
        "1. NEVER include city/state/location names in keywords — geo-targeting handles location\\n"
        "2. NEVER use: near me, nearby, local, around me, in my area\\n"
        "3. NEVER use price words: cheap, affordable, cost, price, quote, discount, free\\n"
        "4. NEVER use superlatives: best, top, #1, leading, award-winning\\n"
        "5. ONLY pure service-action keywords (what the person needs DONE)",
        f"""Build STAG keyword structure for {d.business_name} ({d.business_type}).
Location for geo-targeting only (DO NOT include in keywords): {d.target_location}

GOOD keyword examples for {d.business_type}: "emergency repair", "installation service", "24 hour service", "replacement"
BAD (NEVER USE): "repair {d.target_location}", "service near me", "best repair", "cheap installation"

Return compact JSON. Exactly 5 service themes, 5 keywords each (25 total).
{{"keywords_by_service":{{"[Service Theme]":[{{"keyword":"[service keyword no location]","match_type":"EXACT","estimated_volume":"high","estimated_cpc":3.5}}]}},"total_keywords":25,"recommended_ad_groups":5}}

5 service-only themes for {d.business_type}:""",
        max_tokens=1500,
        agent_num=4,
    )'''

    if old in src:
        src = src.replace(old, new, 1)
        print("✅ Fix 1: Agent 04 — location keywords removed from prompt")
    else:
        print("⚠️  Fix 1: Agent 04 pattern not found — check manually")

    # ── FIX 2: Agent 07 intent clustering — also no location ──
    old7 = '"You are an intent clustering expert for Google Ads campaign organization."'
    new7 = ('"You are an intent clustering expert for Google Ads campaign organization. '
            'CRITICAL: NEVER include city/location names in keywords. Pure service terms only. '
            'Location targeting is handled at the campaign level."')
    if old7 in src:
        src = src.replace(old7, new7, 1)
        print("✅ Fix 2: Agent 07 — no location in cluster keywords")
    else:
        print("⚠️  Fix 2: Agent 07 pattern not found")

    # ── FIX 3: Agent 22 conversion tracking — GA4 ID instructions ──
    old22 = '''  "google_analytics_integration": {},'''
    new22 = ('''  "google_analytics_integration": {{"tracking_id": "ACTION: Go to analytics.google.com → Admin → Data Streams → click your stream → copy Measurement ID starting with G-", '''
             '''"how_to_find_step_by_step": "1. analytics.google.com 2. Admin (gear icon bottom-left) 3. Data Streams 4. Click your website stream 5. Copy the G-XXXXXXXX Measurement ID", "linker": true}},''')
    if old22 in src:
        src = src.replace(old22, new22, 1)
        print("✅ Fix 3: Agent 22 — GA4 ID instructions added")
    else:
        print("⚠️  Fix 3: Agent 22 pattern not found — may already be patched")

    # ── FIX 4: Agent 81 keyword expander — no location ──
    old81 = '"You are a keyword expansion and opportunity discovery expert for Google Ads."'
    new81 = ('"You are a keyword expansion and opportunity discovery expert for Google Ads. '
             'CRITICAL: NEVER include city/location names in keywords. Use pure service-based terms only. '
             'Location is handled by geo-targeting settings."')
    if old81 in src:
        src = src.replace(old81, new81, 1)
        print("✅ Fix 4: Agent 81 — no location in expanded keywords")
    else:
        print("⚠️  Fix 4: Agent 81 pattern not found")

    return src


# ═══════════════════════════════════════════════════════════════
# HTML FIXES
# ═══════════════════════════════════════════════════════════════

NEGATIVE_MINING_FN = r"""
function renderNegativeMiningModal(data) {
  if (!data || data.error) return `<div style="color:var(--danger);padding:16px;">${data?.error || 'No data returned'}</div>`;
  let html = '';
  const sections = [
    { key: 'campaign_level_negatives',  label: '🚫 Campaign-Level Negatives',      color: 'var(--danger)'  },
    { key: 'competitor_brand_negatives',label: '🏢 Competitor Brand Negatives',     color: 'var(--accent4)' },
    { key: 'informational_negatives',   label: '📚 Informational Negatives',        color: 'var(--accent)'  },
    { key: 'job_seeker_negatives',      label: '💼 Job Seeker Negatives',           color: 'var(--accent2)' },
  ];
  const allNegs = sections.reduce((a,s) => a.concat(data[s.key]||[]),[]);
  html += `<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
    <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:8px;padding:10px 16px;text-align:center;">
      <div style="font-size:22px;font-weight:800;color:var(--danger)">${allNegs.length}</div>
      <div style="font-size:10px;color:var(--muted);font-family:var(--mono)">TOTAL NEGATIVES</div>
    </div>
    ${data.estimated_waste_saved?`<div style="background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);border-radius:8px;padding:10px 16px;text-align:center;">
      <div style="font-size:18px;font-weight:800;color:var(--accent3)">${escHtml(data.estimated_waste_saved)}</div>
      <div style="font-size:10px;color:var(--muted);font-family:var(--mono)">MONTHLY SAVINGS</div>
    </div>`:''}
    ${data.total_negative_count?`<div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);border-radius:8px;padding:10px 16px;text-align:center;">
      <div style="font-size:22px;font-weight:800;color:var(--accent)">${data.total_negative_count}</div>
      <div style="font-size:10px;color:var(--muted);font-family:var(--mono)">COUNT</div>
    </div>`:''}
  </div>`;
  sections.forEach(({key,label,color}) => {
    const items = data[key]||[];
    if(!items.length) return;
    html += `<div style="margin-bottom:14px;">
      <div style="font-size:10px;font-family:var(--mono);color:${color};letter-spacing:1px;margin-bottom:6px;">${label} (${items.length})</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px;">${items.map(k=>`<span style="background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.18);border-radius:5px;padding:2px 9px;font-size:11px;color:${color};">${escHtml(k)}</span>`).join('')}</div>
    </div>`;
  });
  const agLevel = data.ad_group_level_negatives||{};
  if(Object.keys(agLevel).length){
    html += `<div style="margin-bottom:14px;"><div style="font-size:10px;font-family:var(--mono);color:var(--accent4);letter-spacing:1px;margin-bottom:6px;">📋 AD GROUP LEVEL NEGATIVES</div>`;
    Object.entries(agLevel).forEach(([ag,kws])=>{
      const kwList = Array.isArray(kws)?kws:(typeof kws==='object'?Object.values(kws):[]);
      html += `<div style="background:var(--surface);border-radius:6px;padding:8px 12px;margin-bottom:5px;">
        <div style="font-size:11px;font-weight:700;color:var(--text);margin-bottom:4px;">${escHtml(ag)}</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;">${kwList.slice(0,10).map(k=>`<span style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:4px;padding:1px 7px;font-size:10px;color:var(--accent4);">${escHtml(typeof k==='string'?k:JSON.stringify(k))}</span>`).join('')}</div>
      </div>`;
    });
    html += '</div>';
  }
  if(allNegs.length===0) {
    html += `<div style="background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.2);border-radius:8px;padding:12px;font-size:12px;color:var(--accent4);">
      ℹ️ No negative keywords extracted from agent data. Click ✏️ Edit Data to manually add negative keywords.
    </div>`;
    html += renderSmartPanel(data,'negative_keywords');
  } else {
    html += `<div style="margin-top:10px;padding:10px 14px;background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.2);border-radius:8px;font-size:11px;color:var(--accent3);">
      ✅ These ${allNegs.length} negative keywords block irrelevant traffic and prevent wasted spend. Add via Google Ads → Shared Library → Negative Keyword Lists.
    </div>`;
  }
  return html;
}
"""

CONV_TRACKING_FN = r"""
function renderConvTrackingModal(data) {
  if (!data || data.error) return renderGenericModalContent(data, 'Conversion Tracking');
  let html = '';
  const ga4 = data.google_analytics_integration || {};
  const gaId = ga4.tracking_id || '';
  const needsSetup = !gaId || gaId.toLowerCase().includes('action') || gaId.includes('XXXXX') || gaId.length < 5;
  html += `<div style="background:${needsSetup?'rgba(245,158,11,.07)':'rgba(16,185,129,.07)'};border:1px solid ${needsSetup?'rgba(245,158,11,.3)':'rgba(16,185,129,.3)'};border-radius:10px;padding:14px 16px;margin-bottom:16px;">
    <div style="font-size:12px;font-weight:700;color:${needsSetup?'var(--accent4)':'var(--accent3)'};margin-bottom:6px;">
      ${needsSetup?'⚠️ GA4 Measurement ID — Client Must Provide':'✅ GA4 Tracking ID'}
    </div>
    ${needsSetup?`<div style="font-size:12px;color:var(--text);line-height:1.9;">
      <strong>Tell your client to find their GA4 ID:</strong><br>
      1. Go to <a href="https://analytics.google.com" target="_blank" style="color:var(--accent);">analytics.google.com</a><br>
      2. Click ⚙️ <strong>Admin</strong> (bottom-left gear icon)<br>
      3. Click <strong>Data Streams</strong><br>
      4. Click their website stream<br>
      5. Copy the <strong>Measurement ID</strong> — it starts with <code style="background:rgba(0,0,0,.4);padding:1px 6px;border-radius:4px;color:var(--accent3);">G-</code><br>
      <div style="margin-top:8px;padding:8px 10px;background:rgba(0,0,0,.25);border-radius:6px;font-family:var(--mono);font-size:11px;color:var(--accent4);">Replace G-XXXXXX with their actual Measurement ID in the tracking code</div>
    </div>`:
    `<code style="font-size:14px;font-weight:700;color:var(--accent3);">${escHtml(gaId)}</code>`}
  </div>`;
  const convActions = data.conversion_actions||[];
  if(convActions.length){
    html += `<div style="margin-bottom:14px;"><div style="font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;margin-bottom:8px;">CONVERSION ACTIONS (${convActions.length})</div>`;
    convActions.slice(0,4).forEach(a=>{
      html += `<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 14px;margin-bottom:6px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:13px;font-weight:700;">${escHtml(a.name||'Conversion')}</span>
          <span style="font-family:var(--mono);font-size:11px;color:var(--accent);">$${a.value||1}</span>
        </div>
        <div style="font-size:11px;color:var(--muted);margin-top:3px;">${escHtml(a.category||'')} · ${escHtml(a.attribution_model||'')} · ${escHtml(a.implementation||'gtag')}</div>
      </div>`;
    });
    html += '</div>';
  }
  const callTrack = data.call_tracking;
  if(callTrack){
    html += `<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 14px;margin-bottom:14px;">
      <div style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-bottom:4px;">CALL TRACKING</div>
      <div style="font-size:12px;color:var(--text);">Setup: ${escHtml(String(callTrack.setup||''))} · Phone swap: ${callTrack.phone_swap_enabled?'✅ Enabled':'❌ Disabled'}</div>
    </div>`;
  }
  html += `<div style="background:linear-gradient(135deg,rgba(16,185,129,.08),rgba(16,185,129,.03));border:1px solid rgba(16,185,129,.25);border-radius:10px;padding:14px 16px;margin-top:8px;">
    <div style="font-size:13px;font-weight:700;color:var(--accent3);margin-bottom:6px;">📧 Send Tracking Code to Client</div>
    <div style="font-size:12px;color:var(--muted);margin-bottom:10px;">Generate a complete GTM + Google Ads + GA4 tracking install package. Your client or web developer pastes it into their website.</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="btn btn-green btn-sm" onclick="closeAgentModal();setTimeout(()=>showGTMModal(lastResults?.conversion_tracking),200)">📦 GTM Install Package</button>
      <button class="btn btn-primary btn-sm" onclick="closeAgentModal();setTimeout(()=>{ showGTMModal(lastResults?.conversion_tracking); setTimeout(emailGTMCode,300); },200)">📧 Email to Client</button>
    </div>
  </div>`;
  return html;
}
"""

def fix_html(src: str) -> str:

    # ── FIX A: Remove agent 6 from kwAgents array ──────────────
    old_kw = "  const kwAgents = [4,5,6,7,38,81,82];"
    new_kw  = "  const kwAgents = [4,5,7,38,81,82]; // A06 (Negative Mining) handled separately below"
    if old_kw in src:
        src = src.replace(old_kw, new_kw, 1)
        print("✅ Fix A: Removed agent 6 from kwAgents")

    # ── FIX B: Add special cases for A06 and A22 BEFORE kwAgents check ──
    old_block = """  // ── Keyword agents — deep quality check ──
  const kwAgents = [4,5,7,38,81,82]; // A06 (Negative Mining) handled separately below
  if (kwAgents.includes(num)) {"""

    new_block = """  // ── Agent 06: Negative Mining — custom display (NOT a quality checker) ──
  if (num === 6) {
    body.innerHTML = renderNegativeMiningModal(data);
    const totNeg = [
      ...(data.campaign_level_negatives||[]),
      ...(data.competitor_brand_negatives||[]),
      ...(data.informational_negatives||[]),
      ...(data.job_seeker_negatives||[])
    ].length;
    setModalQuality(totNeg > 5 ? 100 : totNeg > 0 ? 70 : 30);
  }
  // ── Agent 22: Conv. Tracking — show with GA4 instructions + email button ──
  else if (num === 22) {
    body.innerHTML = renderConvTrackingModal(data);
    setModalQuality(100);
  }
  // ── Keyword agents — deep quality check ──
  else """

    old_kwcheck = "  const kwAgents = [4,5,7,38,81,82]; // A06 (Negative Mining) handled separately below\n  if (kwAgents.includes(num)) {"
    new_kwcheck  = (
        "  // ── Agent 06: Negative Mining — custom display ──\n"
        "  if (num === 6) {\n"
        "    body.innerHTML = renderNegativeMiningModal(data);\n"
        "    const totNeg = [\n"
        "      ...(data.campaign_level_negatives||[]),\n"
        "      ...(data.competitor_brand_negatives||[]),\n"
        "      ...(data.informational_negatives||[]),\n"
        "      ...(data.job_seeker_negatives||[])\n"
        "    ].length;\n"
        "    setModalQuality(totNeg > 5 ? 100 : totNeg > 0 ? 70 : 30);\n"
        "  }\n"
        "  // ── Agent 22: Conv Tracking — GA4 instructions + email button ──\n"
        "  else if (num === 22) {\n"
        "    body.innerHTML = renderConvTrackingModal(data);\n"
        "    setModalQuality(100);\n"
        "  }\n"
        "  // ── Keyword agents — deep quality check ──\n"
        "  const kwAgents = [4,5,7,38,81,82];\n"
        "  else if (kwAgents.includes(num)) {"
    )
    if old_kwcheck in src:
        src = src.replace(old_kwcheck, new_kwcheck, 1)
        print("✅ Fix B: Agent 06 and 22 special cases added")
    else:
        print("⚠️  Fix B: kwAgents pattern not found — check agent modal section")

    # ── FIX C: Insert renderNegativeMiningModal and renderConvTrackingModal functions ──
    insert_before = "function renderAdCopyModalContent(data) {"
    if insert_before in src:
        src = src.replace(insert_before,
            NEGATIVE_MINING_FN + "\n" + CONV_TRACKING_FN + "\n" + insert_before,
            1)
        print("✅ Fix C: renderNegativeMiningModal and renderConvTrackingModal functions added")
    else:
        print("⚠️  Fix C: renderAdCopyModalContent not found")

    # ── FIX D: Make Send to Client button more visible on Phase E tab ──
    old_btn = '<button class="btn btn-green btn-sm" onclick="showGTMModal(lastResults?.conversion_tracking)">📦 Send to Client</button>'
    new_btn = ('<div style="display:flex;gap:6px;">'
               '<button class="btn btn-green btn-sm" onclick="showGTMModal(lastResults?.conversion_tracking)">📦 GTM Package</button>'
               '<button class="btn btn-primary btn-sm" onclick="emailGTMCode()">📧 Email Client</button>'
               '</div>')
    if old_btn in src:
        src = src.replace(old_btn, new_btn, 1)
        print("✅ Fix D: Email Client button made prominent in Phase E tab")
    else:
        print("⚠️  Fix D: Send to Client button pattern not found")

    # ── FIX E: extractAllKeywords — also pull from negative mining agent keys ──
    old_extract = "  if (data.negative_list_expansion) tryExtract(data.negative_list_expansion);"
    new_extract = (
        "  if (data.negative_list_expansion) tryExtract(data.negative_list_expansion);\n"
        "  // Negative mining agent keys\n"
        "  if (data.high_value_terms) tryExtract(data.high_value_terms);\n"
        "  if (data.long_tail_goldmines) tryExtract(data.long_tail_goldmines);"
    )
    if old_extract in src:
        src = src.replace(old_extract, new_extract, 1)
        print("✅ Fix E: extractAllKeywords enhanced for negative mining keys")

    return src


# ── Main ───────────────────────────────────────────────────────
import sys, os

if len(sys.argv) < 3:
    print("Usage: python3 apply_fixes.py app_v14.py index_v14.html")
    sys.exit(1)

py_path   = sys.argv[1]
html_path = sys.argv[2]

if not os.path.exists(py_path):
    print(f"❌ {py_path} not found")
    sys.exit(1)
if not os.path.exists(html_path):
    print(f"❌ {html_path} not found")
    sys.exit(1)

with open(py_path, encoding='utf-8') as f:
    py_src = f.read()
with open(html_path, encoding='utf-8') as f:
    html_src = f.read()

print(f"\n{'='*60}")
print("Applying Python fixes...")
print('='*60)
py_fixed = fix_python(py_src)

print(f"\n{'='*60}")
print("Applying HTML fixes...")
print('='*60)
html_fixed = fix_html(html_src)

# Write outputs
out_py   = py_path.replace('.py', '_fixed.py')
out_html = html_path.replace('.html', '_fixed.html')

with open(out_py, 'w', encoding='utf-8') as f:
    f.write(py_fixed)
with open(out_html, 'w', encoding='utf-8') as f:
    f.write(html_fixed)

print(f"\n✅ Done!")
print(f"   Python: {out_py}")
print(f"   HTML:   {out_html}")