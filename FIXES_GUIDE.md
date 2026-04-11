# AdsForge AI — Fix Guide for 4 Issues

## How to apply

1. Put `apply_fixes.py` in the same folder as your `app_v14.py` and `index_v14.html`
2. Run: `python3 apply_fixes.py app_v14.py index_v14.html`
3. This creates `app_v14_fixed.py` and `index_v14_fixed.html`
4. Rename them (remove `_fixed`) and restart the server

---

## What was fixed

### Fix 1 — Agent 04 STAG Keywords: NO location in keywords ✅
**Problem:** Keywords like "garage door repair phoenix" were generated  
**Root cause:** Agent 04 prompt didn't explicitly forbid location words  
**Fix:** System prompt now has 5 strict rules blocking location/price/superlative keywords

The fixed prompt tells the AI:
- ❌ NEVER: "repair phoenix", "service near me", "best repair", "cheap installation"  
- ✅ ONLY: "emergency repair", "installation service", "24 hour service"

Location targeting is set in Google Ads campaign settings, NOT in keywords.

---

### Fix 2 — Negative Mining A06: Shows 0/0/0 ✅
**Problem:** A06 showed "0 clean keywords / 0 need fixing / 0 total"  
**Root cause:** The keyword quality checker was applied to negative keywords — wrong approach.
Negative keywords ARE supposed to contain words like "near me", "free", "jobs" — that's the point!  
**Fix:** Agent 06 now has its own custom renderer (`renderNegativeMiningModal`) that:
- Shows campaign-level negatives as red tags
- Shows ad group level negatives per group
- Shows competitor brand, informational, job seeker negatives
- Shows estimated waste saved
- Shows total count correctly

---

### Fix 3 — Tracking ID G-XXXXXX ✅
**Problem:** Conversion Tracking (A22) shows placeholder G-XXXXXX  
**Root cause:** The GA4 Measurement ID must come from the client's Google Analytics account — no AI can generate it  
**Fix:** Agent 22 modal now shows clear step-by-step instructions:
1. Go to analytics.google.com
2. Admin (gear icon) → Data Streams
3. Click website stream → copy Measurement ID (G-XXXXXXXX)
4. Replace in the tracking code

The G-XXXXXX placeholder is CORRECT behavior — it must be replaced with the client's real ID.

---

### Fix 4 — Email to Client button ✅
**Problem:** Email button was hard to find  
**Fix:** Agent 22 (Conv. Tracking) modal now prominently shows:
- 📦 GTM Install Package button  
- 📧 Email to Client button  

Also added 📧 Email Client button directly in the Phase E results tab (next to 📦 GTM Package).

---

## Manual fixes (if apply_fixes.py doesn't work)

### app_v14.py — Agent 04 system prompt
Find the line:
```
"You are a Google Ads keyword architect. Return ONLY valid compact JSON. No explanation.",
```
Replace with:
```
"You are a Google Ads keyword architect. Return ONLY valid compact JSON. No explanation.\n\n"
"CRITICAL RULES — violations cause keyword rejection:\n"
"1. NEVER include city/state/location names in keywords — geo-targeting handles location\n"
"2. NEVER use: near me, nearby, local, around me, in my area\n"
"3. NEVER use price words: cheap, affordable, cost, price, quote, discount, free\n"
"4. NEVER use superlatives: best, top, #1, leading, award-winning\n"
"5. ONLY pure service-action keywords (what the person needs DONE)",
```

Also update the f-string first line:
```
# OLD:
f"""Build STAG keyword structure for {d.business_name} ({d.business_type}) in {d.target_location}.
# NEW:
f"""Build STAG keyword structure for {d.business_name} ({d.business_type}).
Location for geo-targeting only (DO NOT include in keywords): {d.target_location}
```

### index_v14.html — kwAgents array
Find:
```js
const kwAgents = [4,5,6,7,38,81,82];
```
Replace:
```js
const kwAgents = [4,5,7,38,81,82]; // Agent 6 handled separately
```

Then add BEFORE the kwAgents check block:
```js
if (num === 6) {
  body.innerHTML = renderNegativeMiningModal(data);
  const totNeg = [
    ...(data.campaign_level_negatives||[]),
    ...(data.competitor_brand_negatives||[]),
    ...(data.informational_negatives||[]),
    ...(data.job_seeker_negatives||[])
  ].length;
  setModalQuality(totNeg > 5 ? 100 : totNeg > 0 ? 70 : 30);
} else if (num === 22) {
  body.innerHTML = renderConvTrackingModal(data);
  setModalQuality(100);
} else 
```
(note the `else` at the end connects to the existing `if (kwAgents.includes(num))` block)

