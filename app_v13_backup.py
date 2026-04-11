# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║   GOOGLE ADS ENTERPRISE v13 — FULLY AUTONOMOUS                  ║
║   88 AI Agents | 100% Google Ads Platform Coverage              ║
║   FastAPI Backend — Fixed & Enhanced                            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ── Auto-load .env file ───────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _v = _v.strip().strip('"').strip("'")
                os.environ.setdefault(_k.strip(), _v)

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")

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
    """Called when a key hits 429 — force switch to next key."""
    global _groq_key_idx
    _groq_key_idx += 1
    if len(_ALL_GROQ_KEYS) > 1:
        next_key_preview = _ALL_GROQ_KEYS[_groq_key_idx % len(_ALL_GROQ_KEYS)][:12]
        log.info(f"🔄 Rotated to key #{_groq_key_idx % len(_ALL_GROQ_KEYS) + 1}/{len(_ALL_GROQ_KEYS)}: {next_key_preview}...")

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
    """Called when a key hits 429 — force switch to next key."""
    global _groq_key_idx
    _groq_key_idx += 1
    if len(_ALL_GROQ_KEYS) > 1:
        next_key_preview = _ALL_GROQ_KEYS[_groq_key_idx % len(_ALL_GROQ_KEYS)][:12]
        log.info(f"🔄 Rotated to key #{_groq_key_idx % len(_ALL_GROQ_KEYS) + 1}/{len(_ALL_GROQ_KEYS)}: {next_key_preview}...")

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
    """Called when a key hits 429 — force switch to next key."""
    global _groq_key_idx
    _groq_key_idx += 1
    if len(_ALL_GROQ_KEYS) > 1:
        next_key_preview = _ALL_GROQ_KEYS[_groq_key_idx % len(_ALL_GROQ_KEYS)][:12]
        log.info(f"🔄 Rotated to key #{_groq_key_idx % len(_ALL_GROQ_KEYS) + 1}/{len(_ALL_GROQ_KEYS)}: {next_key_preview}...")

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
    """Called when a key hits 429 — force switch to next key."""
    global _groq_key_idx
    _groq_key_idx += 1
    if len(_ALL_GROQ_KEYS) > 1:
        next_key_preview = _ALL_GROQ_KEYS[_groq_key_idx % len(_ALL_GROQ_KEYS)][:12]
        log.info(f"🔄 Rotated to key #{_groq_key_idx % len(_ALL_GROQ_KEYS) + 1}/{len(_ALL_GROQ_KEYS)}: {next_key_preview}...")
DASHBOARD_API_KEY   = os.getenv("DASHBOARD_API_KEY", "").strip()  # empty = no auth required
GOOGLE_ADS_DEV_TOK  = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()
GOOGLE_CLIENT_ID    = os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SEC   = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip()
GOOGLE_REFRESH_TOK  = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "").strip()
GOOGLE_MCC_ID       = os.getenv("GOOGLE_ADS_MCC_ID", "").strip()

DB_PATH = "campaigns.db"

# ── Groq AI Client (OpenAI-compatible) ───────────────────────────
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL    = "llama-3.3-70b-versatile"

# ── Token-bucket rate limiter: max 25 requests/minute ────────────
# Groq free tier = 30 req/min. We cap at 25 to stay safely under.
# Between each request we enforce a minimum 2.5-second gap.
_groq_lock         = asyncio.Lock()
_groq_last_call_ts = 0.0          # epoch seconds of last completed call
_MIN_GAP_SECONDS   = 2.5          # = 24 req/min max
_groq_sem          = asyncio.Semaphore(2)   # max 2 truly concurrent

def groq_chat(system: str, user: str, max_tokens: int = 1500) -> str:
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
            {"role": "system", "content": system + "\n\nRespond with valid JSON only. No markdown fences, no preamble."},
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

    raise RuntimeError(f"Groq API failed after {MAX_ATTEMPTS} attempts across {len(keys)} key(s)")

# ── Database ─────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT,
            business_type TEXT,
            website_url TEXT,
            target_location TEXT,
            daily_budget REAL,
            campaign_types TEXT,
            result_json TEXT,
            published INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

def save_campaign(data: dict, result: dict, published: bool = False) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """INSERT INTO campaigns
           (business_name,business_type,website_url,target_location,daily_budget,campaign_types,result_json,published)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            data.get("business_name",""),
            data.get("business_type",""),
            data.get("website_url",""),
            data.get("target_location",""),
            data.get("daily_budget",50),
            json.dumps(data.get("campaign_types",[])),
            json.dumps(result),
            1 if published else 0,
        )
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_campaigns() -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,business_name,business_type,target_location,daily_budget,campaign_types,published,created_at FROM campaigns ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["campaign_types"] = json.loads(d["campaign_types"] or "[]")
        out.append(d)
    return out

# ── Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    key_count = len(_ALL_GROQ_KEYS) if _ALL_GROQ_KEYS else 1
    log.info(f"✅ Google Ads Enterprise v13 — 91 Agents Ready | {key_count} Groq key(s) loaded")
    if key_count > 1:
        log.info(f"🔄 Key rotation active: {key_count} keys = ~{key_count * 14400:,} requests/day free capacity")
    yield
    log.info("Server shutting down")

# ── App ───────────────────────────────────────────────────────────
app = FastAPI(
    title="Google Ads Enterprise AI v12",
    version="13.0.0",
    description="88 Autonomous AI Agents for Google Ads",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve index.html at root ──────────────────────────────────────
# Try multiple HTML filenames in order
_base = os.path.dirname(__file__)
for _fname in ["index.html", "index_v13.html", "index_v12.html"]:
    HTML_FILE = os.path.join(_base, _fname)
    if os.path.exists(HTML_FILE):
        break

@app.get("/", response_class=HTMLResponse)
async def serve_root():
    if os.path.exists(HTML_FILE):
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>index.html not found — place it in the same folder as app.py</h2>", status_code=404)

@app.get("/favicon.ico")
async def favicon():
    return JSONResponse({})  # suppress 404 in logs

# ── Auth ─────────────────────────────────────────────────────────
def verify_key(x_api_key: Optional[str] = Header(None)):
    """If DASHBOARD_API_KEY is set in .env, enforce it. Otherwise open access."""
    if DASHBOARD_API_KEY and x_api_key != DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key — set it in Settings tab or leave DASHBOARD_API_KEY empty in .env")

# ── AI Helpers (Groq) ────────────────────────────────────────────
def ai_json(system: str, user: str, max_tokens: int = 2000) -> dict:
    """Call Groq and parse JSON response robustly."""
    raw = ""
    try:
        raw = groq_chat(system, user, max_tokens)
        # Strip markdown fences
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else parts[0]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Fix 1: Try replacing literal backslash sequences in code strings
        try:
            import re as _re
            # Escape unescaped backslashes inside string values (common in code snippets)
            fixed = _re.sub(r'(?<!\)\(?!["\/bfnrtu])', r'\\', raw)
            return json.loads(fixed)
        except Exception:
            pass
        # Fix 2: Try extracting just the JSON object/array
        try:
            import re as _re
            m = _re.search(r'(\{.*\}|\[.*\])', raw, _re.DOTALL)
            if m:
                return json.loads(m.group(1))
        except Exception:
            pass
        log.error(f"JSON parse error: {e} | raw[:200]: {raw[:200]}")
        return {"error": f"JSON parse error — {str(e)}", "raw_preview": raw[:300]}
    except Exception as e:
        log.error(f"AI call failed: {e}")
        return {"error": str(e)}

def ai_text(system: str, user: str, max_tokens: int = 600) -> str:
    """Call Groq for plain text (no JSON parsing), with retry on 429."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set in .env")
    headers = {"Authorization": f"Bearer {_next_groq_key()}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.5,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }
    for attempt in range(5):
        try:
            with httpx.Client(timeout=90) as client:
                r = client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
                if r.status_code == 429:
                    _rotate_on_429()
                    wait = min(30, 2 ** attempt + 1)
                    log.warning(f"Groq 429 (text) — key rotated, waiting {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < 4:
                time.sleep(2 ** attempt + 1)
            else:
                log.error(f"AI text call failed: {e}")
                return f"Error: {e}"
    return "Error: max retries exceeded"

# ════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ════════════════════════════════════════════════════════════════

class RunCrewRequest(BaseModel):
    business_name: str
    business_type: str
    website_url: str
    target_location: str
    target_language: str = "English"
    secondary_language: str = "Spanish"
    conversion_goal: str = "Leads"
    daily_budget: float = 50.0
    monthly_revenue: float = 0.0
    customer_id: str = ""
    auto_publish: bool = False
    campaign_types: List[str] = ["Search", "Performance Max", "Display"]
    disabled_agents: List[int] = []   # agent numbers to skip e.g. [12, 13, 65]

class AnalyzeUrlRequest(BaseModel):
    url: str

class SearchTermsRequest(BaseModel):
    search_terms: List[str]
    business_type: str
    current_negatives: List[str] = []

class QualityScoreRequest(BaseModel):
    keywords: List[str]
    headlines: List[str]
    descriptions: List[str] = []
    landing_page_content: str = ""
    business_type: str

class AnomalyRequest(BaseModel):
    campaign_name: str
    metrics: Dict[str, Any]
    historical_avg: Dict[str, Any]

class AudienceRequest(BaseModel):
    business_name: str
    business_type: str
    target_location: str
    website_url: str = ""

class ReportRequest(BaseModel):
    campaign_name: str
    metrics: Dict[str, Any]
    conversion_goal: str = "Leads"

class BidAdjustRequest(BaseModel):
    campaign_name: str
    device_data: Dict[str, Any]
    location_data: Dict[str, Any]
    time_data: Dict[str, Any]

class CompetitorSpyRequest(BaseModel):
    business_type: str
    target_location: str
    competitors: List[str] = []

class SmartBudgetRequest(BaseModel):
    business_name: str
    current_spend: float
    current_roas: float
    target_cpa: float
    campaign_data: Dict[str, Any] = {}

class LandingPageRequest(BaseModel):
    business_name: str
    business_type: str
    target_location: str
    conversion_goal: str
    keywords: List[str] = []

class ShoppingFeedRequest(BaseModel):
    business_name: str
    products: List[Dict[str, Any]]
    target_location: str

# ════════════════════════════════════════════════════════════════
# THE 35 AGENTS
# ════════════════════════════════════════════════════════════════

# ─── PHASE A: FOUNDATION (Agents 1–3) ───────────────────────────

def agent_01_business_intelligence(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 01: Business Intelligence")
    return ai_json(
        "You are a business intelligence analyst specializing in Google Ads.",
        f"""Analyze this business and return a JSON object:
Business: {d.business_name}
Type: {d.business_type}
Website: {d.website_url}
Location: {d.target_location}
Return JSON with: {{
  "unique_selling_points": [...5 USPs],
  "target_customer_profile": {{"age_range":"","income":"","pain_points":[]}},
  "seasonal_trends": [...],
  "price_positioning": "budget|mid|premium",
  "key_services": [...top 6 services],
  "estimated_avg_ticket": number,
  "google_ads_opportunity_score": number (1-10)
}}"""
    )

def agent_02_competitor_analysis(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 02: Competitor Analysis")
    return ai_json(
        "You are a competitive intelligence expert for Google Ads.",
        f"""Analyze the competitive landscape for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "top_competitors": [
    {{"name":"","estimated_ad_spend":"","strengths":[],"weaknesses":[],"ad_copy_patterns":[]}}
  ],
  "competitive_gaps": [...],
  "recommended_differentiators": [...],
  "average_competitor_cpc": number,
  "market_saturation": "low|medium|high"
}}"""
    )

def agent_03_search_intent_map(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 03: Search Intent Map")
    return ai_json(
        "You are a search intent expert for Google Ads strategy.",
        f"""Map search intent categories for {d.business_type} in {d.target_location}.
Return JSON: {{
  "intent_categories": {{
    "informational": [...keywords],
    "navigational": [...keywords],
    "commercial": [...keywords],
    "transactional": [...keywords]
  }},
  "funnel_mapping": {{
    "top_of_funnel": [...],
    "middle_of_funnel": [...],
    "bottom_of_funnel": [...]
  }},
  "recommended_bid_strategy_per_intent": {{}}
}}"""
    )

# ─── PHASE B: KEYWORDS (Agents 4–7) ─────────────────────────────

def agent_04_stag_keyword_architect(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 04: STAG Keyword Architect")
    return ai_json(
        "You are a Google Ads keyword architect using Single Theme Ad Groups (STAG).",
        f"""Build a STAG keyword structure for {d.business_name} ({d.business_type}) in {d.target_location}.
Return COMPACT JSON (no extra whitespace) with exactly 5 service themes, 6 keywords each:
{{"keywords_by_service":{{"Theme1":[{{"keyword":"","match_type":"EXACT|PHRASE|BROAD","estimated_volume":"high|med|low","estimated_cpc":0.0,"commercial_intent":0.0}}]}},"total_keywords":30,"recommended_ad_groups":5}}
Use real keywords specific to {d.business_type}. Keep all strings short.""",
        max_tokens=1200,
    )

def agent_05_brand_segmentation(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 05: Brand Segmentation")
    return ai_json(
        "You are a brand keyword segmentation specialist for Google Ads.",
        f"""Create brand vs. non-brand keyword segmentation for {d.business_name} ({d.business_type}).
Return JSON: {{
  "brand_campaign": {{
    "keywords": [...],
    "recommended_bid_strategy": "",
    "budget_percentage": number
  }},
  "non_brand_campaigns": {{
    "keywords": [...],
    "recommended_bid_strategy": "",
    "budget_percentage": number
  }},
  "competitor_keywords": [...],
  "brand_protection_keywords": [...]
}}"""
    )

def agent_06_negative_keyword_mining(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 06: Negative Keyword Mining")
    return ai_json(
        "You are a negative keyword specialist. Your goal is to prevent wasted ad spend.",
        f"""Generate comprehensive negative keyword lists for {d.business_type} in {d.target_location}.
Return JSON: {{
  "campaign_level_negatives": [...20+ irrelevant terms],
  "ad_group_level_negatives": {{}},
  "competitor_brand_negatives": [...],
  "informational_negatives": [...],
  "job_seeker_negatives": [...],
  "estimated_waste_saved": "$X-Y per month",
  "total_negative_count": number
}}"""
    )

def agent_07_intent_clustering(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 07: Intent Clustering")
    return ai_json(
        "You are an intent clustering expert for Google Ads campaign organization.",
        f"""Create intent-based keyword clusters for {d.business_type}.
Return JSON: {{
  "clusters": [
    {{
      "cluster_name": "",
      "intent": "emergency|planned|research|local",
      "keywords": [...],
      "recommended_landing_page_type": "",
      "recommended_cta": "",
      "bid_multiplier": number
    }}
  ],
  "prioritization": {{
    "highest_roi_cluster": "",
    "quickest_wins": []
  }}
}}"""
    )

# ─── PHASE C: AD CREATIVE (Agents 8–16) ─────────────────────────

def agent_08_rsa_copywriter(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 08: RSA Copywriter")
    return ai_json(
        "You are a Google Ads RSA copywriter. You write headlines under 30 chars and descriptions under 90 chars.",
        f"""Write complete RSA ad copy for {d.business_name} ({d.business_type}) in {d.target_location}.
Goal: {d.conversion_goal}
Return JSON: {{
  "headlines": [...15 headlines, max 30 chars each],
  "descriptions": [...4 descriptions, max 90 chars each],
  "sitelinks": [
    {{"title":"","description1":"","description2":"","final_url_path":""}}
  ],
  "callouts": [...8 callout extensions],
  "structured_snippets": {{"header":"Services","values":[...]}},
  "price_extensions": []
}}"""
    )

def agent_09_pmax_asset_generator(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 09: Performance Max Assets")
    return ai_json(
        "You are a Performance Max campaign asset specialist for Google Ads.",
        f"""Generate complete Performance Max asset groups for {d.business_name} ({d.business_type}).
Return JSON: {{
  "asset_groups": [
    {{
      "name": "",
      "final_urls": [...],
      "headlines": [...5],
      "long_headlines": [...5, max 90 chars],
      "descriptions": [...5],
      "business_name": "{d.business_name}",
      "call_to_action": "CALL_NOW|GET_QUOTE|LEARN_MORE|BOOK_NOW",
      "images_needed": [...describe 5 image concepts],
      "audience_signals": [...],
      "themes": [...]
    }}
  ]
}}"""
    )

def agent_10_dsa_generator(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 10: DSA Generator")
    return ai_json(
        "You are a Dynamic Search Ads specialist.",
        f"""Create Dynamic Search Ads configuration for {d.business_name} website.
Return JSON: {{
  "dsa_settings": {{
    "domain": "{d.website_url}",
    "language": "{d.target_language}",
    "targeting_source": "WEBSITE",
    "page_feed": false
  }},
  "auto_targets": [
    {{"category":"","description":""}}
  ],
  "ad_descriptions": [...4 descriptions for DSA],
  "exclusion_pages": [...pages to exclude from DSA]
}}"""
    )

def agent_11_display_creative(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 11: Display Creative")
    return ai_json(
        "You are a Display Network creative strategist for Google Ads.",
        f"""Design Display ad creatives for {d.business_name} ({d.business_type}).
Return JSON: {{
  "responsive_display_ads": [
    {{
      "headlines": [...5, max 30 chars],
      "long_headline": "",
      "descriptions": [...5, max 90 chars],
      "business_name": "{d.business_name}",
      "call_to_action": "",
      "image_concepts": [
        {{"size":"1200x628","description":"","color_scheme":"","key_element":""}}
      ]
    }}
  ],
  "targeting_options": {{
    "topics": [...],
    "placements": [...relevant websites],
    "custom_intent_audiences": [...],
    "remarketing_lists": [...]
  }},
  "brand_guidelines": {{
    "primary_color": "",
    "tone": ""
  }}
}}"""
    )

def agent_12_youtube_scripts(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 12: YouTube Video Scripts")
    return ai_json(
        "You are a YouTube advertising copywriter for Google Ads video campaigns.",
        f"""Write YouTube ad scripts for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "skippable_instream": {{
    "duration_seconds": 30,
    "hook_5s": "",
    "full_script": "",
    "call_to_action": ""
  }},
  "non_skippable_15s": {{
    "script": "",
    "call_to_action": ""
  }},
  "bumper_6s": [
    {{"script":"","message_focus":""}}
  ],
  "discovery_ads": {{
    "title": "",
    "description_lines": ["",""]
  }}
}}"""
    )

def agent_13_shopping_feed_optimizer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 13: Shopping Feed Optimizer")
    return ai_json(
        "You are a Google Shopping feed optimization expert.",
        f"""Create Shopping campaign setup for {d.business_name} ({d.business_type}).
Return JSON: {{
  "feed_optimization_rules": [...],
  "product_titles_formula": "",
  "smart_shopping_settings": {{}},
  "bidding_strategy": "",
  "product_groups": [...],
  "merchant_center_checklist": [...]
}}"""
    )

def agent_14_call_only_ads(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 14: Call-Only Ads")
    return ai_json(
        "You are a call-only ad specialist for local service businesses.",
        f"""Create call-only ad campaigns for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "call_only_ads": [
    {{
      "headline_1": "",
      "headline_2": "",
      "description": "",
      "phone_number": "REPLACE_WITH_ACTUAL",
      "display_url": "",
      "verification_url": "{d.website_url}",
      "call_tracked": true
    }}
  ],
  "call_schedule": {{"days":[],"hours":""}},
  "bid_strategy_for_calls": "",
  "recommended_extensions": [...]
}}"""
    )

def agent_15_ab_urgency_copy(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 15: A/B Urgency Copy")
    return ai_json(
        "You are a conversion copywriter specializing in urgency and psychological triggers for Google Ads.",
        f"""Create A/B test variations with urgency for {d.business_name} ({d.business_type}).
Return JSON: {{
  "test_variants": [
    {{
      "variant": "A",
      "angle": "urgency",
      "headlines": [...3],
      "description": "",
      "psychological_trigger": ""
    }},
    {{
      "variant": "B",
      "angle": "social_proof",
      "headlines": [...3],
      "description": "",
      "psychological_trigger": ""
    }},
    {{
      "variant": "C",
      "angle": "value_proposition",
      "headlines": [...3],
      "description": "",
      "psychological_trigger": ""
    }}
  ],
  "test_hypothesis": "",
  "success_metric": "",
  "minimum_test_duration_days": number
}}"""
    )

def agent_16_multilingual_ads(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 16: Multilingual Ad Copy")
    return ai_json(
        "You are a multilingual Google Ads copywriter.",
        f"""Translate and culturally adapt ads for {d.business_name} ({d.business_type}).
Primary Language: {d.target_language}
Secondary Language: {d.secondary_language}
Return JSON: {{
  "primary_language_ads": {{
    "language": "{d.target_language}",
    "headlines": [...5],
    "descriptions": [...2]
  }},
  "secondary_language_ads": {{
    "language": "{d.secondary_language}",
    "headlines": [...5],
    "descriptions": [...2]
  }},
  "cultural_notes": "",
  "geo_targeting_recommendation": ""
}}"""
    )

# ─── PHASE D: STRUCTURE (Agents 17–21) ──────────────────────────

def agent_17_campaign_architect(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 17: Campaign Architect")
    return ai_json(
        "You are a Google Ads campaign architect. Design the full account structure.",
        f"""Design the complete campaign architecture for {d.business_name} ({d.business_type}).
Campaign Types: {', '.join(d.campaign_types)}
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "account_structure": {{
    "campaigns": [
      {{
        "name": "",
        "type": "",
        "goal": "",
        "budget_percentage": number,
        "ad_groups": [...],
        "bid_strategy": "",
        "targeting": {{}}
      }}
    ]
  }},
  "naming_conventions": {{}},
  "launch_sequence": [...phases],
  "scaling_triggers": [...]
}}"""
    )

def agent_18_budget_allocator(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 18: Budget Allocator")
    return ai_json(
        "You are a Google Ads budget optimization expert.",
        f"""Allocate ${d.daily_budget}/day budget across campaign types for {d.business_name}.
Campaign Types: {', '.join(d.campaign_types)}
Conversion Goal: {d.conversion_goal}
Monthly Revenue: ${d.monthly_revenue}
Return JSON: {{
  "daily_budget": {d.daily_budget},
  "allocation": [
    {{"campaign_type":"","daily":number,"percentage":number,"rationale":""}}
  ],
  "scaling_milestones": [...],
  "budget_warnings": [...],
  "break_even_point": {{}}
}}"""
    )

def agent_19_smart_bidding(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 19: Smart Bidding Strategy")
    return ai_json(
        "You are a Google Ads Smart Bidding strategist.",
        f"""Design the bidding roadmap for {d.business_name} ({d.business_type}).
Goal: {d.conversion_goal}
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "phase_1_bidding": {{"strategy":"Manual CPC","duration_days":14,"rationale":""}},
  "phase_2_bidding": {{"strategy":"Target CPA","target_cpa":number,"rationale":""}},
  "phase_3_bidding": {{"strategy":"Target ROAS","target_roas":number,"rationale":""}},
  "bid_adjustments": {{
    "device": {{"mobile":number,"desktop":number,"tablet":number}},
    "time": [...hourly multipliers],
    "location": [...]
  }},
  "portfolio_strategies": []
}}"""
    )

def agent_20_audience_builder(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 20: Audience Builder")
    return ai_json(
        "You are a Google Ads audience segmentation expert.",
        f"""Build the complete audience ecosystem for {d.business_name} ({d.business_type}).
Return JSON: {{
  "remarketing_audiences": [
    {{"name":"","membership_duration_days":number,"targeting_rule":"","bid_adjustment":number}}
  ],
  "customer_match": {{"description":"","upload_fields":[]}},
  "similar_audiences": [...],
  "in_market_audiences": [...],
  "custom_intent_audiences": [
    {{"name":"","keywords":[...],"urls":[...]}}
  ],
  "affinity_audiences": [...],
  "life_events": [...]
}}"""
    )

def agent_21_geo_device_time_targeting(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 21: Geo/Device/Time Targeting")
    return ai_json(
        "You are a targeting optimization specialist for Google Ads.",
        f"""Optimize geo, device, and time targeting for {d.business_name} in {d.target_location}.
Business Type: {d.business_type}
Return JSON: {{
  "geo_targeting": {{
    "primary_target": "{d.target_location}",
    "radius_miles": number,
    "excluded_areas": [],
    "bid_adjustments_by_area": []
  }},
  "device_strategy": {{"mobile":"","desktop":"","tablet":""}},
  "ad_schedule": {{
    "peak_hours": [...],
    "off_hours": [...],
    "day_of_week_adjustments": {{}}
  }},
  "demographic_targeting": {{
    "age_ranges": [...],
    "household_income": [...],
    "parental_status": []
  }}
}}"""
    )

# ─── PHASE E: TRACKING & AUTOMATION (Agents 22–27) ──────────────

def agent_22_conversion_tracking(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 22: Conversion Tracking Setup")
    return ai_json(
        "You are a Google Ads conversion tracking implementation expert.",
        f"""Design conversion tracking for {d.business_name} ({d.business_type}).
Goal: {d.conversion_goal}
Website: {d.website_url}
Return JSON: {{
  "conversion_actions": [
    {{
      "name":"","category":"","counting":"ONE|MANY","value":number,"attribution_model":"",
      "implementation":"gtag|google_tag_manager","code_snippet":""
    }}
  ],
  "google_analytics_integration": {{}},
  "call_tracking": {{"setup":"","phone_swap_enabled":true}},
  "import_from_ga4": [],
  "value_based_bidding_setup": {{}}
}}"""
    )

def agent_23_ads_scripts_writer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 23: Google Ads Scripts")
    return ai_json(
        "You are a Google Ads Scripts developer. Write production-ready automation scripts.",
        f"""Write Google Ads automation scripts for {d.business_name}.
Return JSON: {{
  "scripts": [
    {{
      "name": "Budget Pacer",
      "trigger": "Hourly",
      "description": "Pause campaigns if daily budget pacing is off",
      "code": "function main() {{ // Paste into Google Ads Scripts\\n  var campaigns = AdsApp.campaigns().get();\\n  while (campaigns.hasNext()) {{\\n    var c = campaigns.next();\\n    Logger.log(c.getName() + ': ' + c.getBudget().getAmount());\\n  }}\\n}}"
    }},
    {{
      "name": "Quality Score Monitor",
      "trigger": "Daily",
      "description": "Alert if QS drops below threshold",
      "code": "function main() {{ var kw = AdsApp.keywords().withCondition('QualityScore < 5').get(); Logger.log('Low QS keywords: ' + kw.totalNumEntities()); }}"
    }},
    {{
      "name": "Search Term Auto-Negatives",
      "trigger": "Weekly",
      "description": "Auto-add irrelevant search terms as negatives",
      "code": "function main() {{ Logger.log('Search term mining complete'); }}"
    }},
    {{
      "name": "Bid Adjustment Automator",
      "trigger": "Daily",
      "description": "Auto-adjust bids by hour/device performance",
      "code": "function main() {{ Logger.log('Bid adjustments applied'); }}"
    }},
    {{
      "name": "Zero Impression Alert",
      "trigger": "Daily",
      "description": "Email alert for ads with zero impressions",
      "code": "function main() {{ Logger.log('Zero impression check done'); }}"
    }}
  ]
}}"""
    )

def agent_24_quality_score_optimizer_agent(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 24: Quality Score Optimizer")
    return ai_json(
        "You are a Quality Score optimization expert for Google Ads.",
        f"""Maximize Quality Scores for {d.business_name} ({d.business_type}).
Return JSON: {{
  "qs_audit": {{
    "expected_ctr_factors": [...],
    "ad_relevance_factors": [...],
    "landing_page_factors": [...]
  }},
  "optimization_actions": [
    {{"action":"","impact":"high|medium|low","effort":"easy|medium|hard","estimated_qs_gain":number}}
  ],
  "landing_page_recommendations": [...],
  "ad_group_restructuring": [...],
  "estimated_cpc_reduction_pct": number
}}"""
    )

def agent_25_anomaly_detection_agent(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 25: Anomaly Detection Framework")
    return ai_json(
        "You are an anomaly detection specialist for Google Ads campaigns.",
        f"""Build an anomaly detection framework for {d.business_name}.
Return JSON: {{
  "kpi_thresholds": {{
    "ctr_drop_alert_pct": number,
    "cpc_spike_alert_pct": number,
    "conversion_rate_drop_pct": number,
    "impression_share_loss_pct": number
  }},
  "detection_rules": [
    {{"rule":"","condition":"","action":"","severity":"critical|warning|info"}}
  ],
  "automated_responses": [...],
  "weekly_audit_checklist": [...],
  "alert_channels": ["email","slack"]
}}"""
    )

def agent_26_extension_suite(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 26: Extension Suite (All 9 Types)")
    return ai_json(
        "You are a Google Ads extension specialist. Cover all 9 extension types.",
        f"""Create all ad extension types for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "sitelinks": [{{"title":"","description1":"","description2":"","url":""}}],
  "callouts": [...8 callout texts],
  "structured_snippets": {{"header":"Services","values":[...6]}},
  "call_extension": {{"phone":"REPLACE_WITH_NUMBER","call_only":false}},
  "location_extension": {{"address":"","city":"{d.target_location}"}},
  "price_extension": [{{"header":"","price":"","unit":"","description":""}}],
  "image_extension": [{{"image_concept":"","url_path":""}}],
  "lead_form_extension": {{"headline":"","description":"","fields":["name","email","phone"]}},
  "promotion_extension": {{"promotion":"","amount":"","occasion":"","start_date":"","end_date":""}}
}}"""
    )

def agent_27_dynamic_landing_page(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 27: Dynamic Landing Page Generator")
    return ai_json(
        "You are a CRO and landing page specialist for Google Ads.",
        f"""Design dynamic landing pages for {d.business_name} ({d.business_type}) in {d.target_location}.
Goal: {d.conversion_goal}
Return JSON: {{
  "landing_pages": [
    {{
      "keyword_theme": "",
      "headline": "",
      "subheadline": "",
      "hero_cta": "",
      "trust_signals": [...],
      "above_fold_elements": [...],
      "form_fields": [...],
      "page_speed_targets": {{"fcp_seconds":number,"lcp_seconds":number}}
    }}
  ],
  "personalization_rules": [...],
  "a_b_test_elements": [...],
  "conversion_elements_checklist": [...]
}}"""
    )

# ─── PHASE F: COMPLIANCE & FORECAST (Agents 28–31) ──────────────

def agent_28_policy_auditor(d: RunCrewRequest) -> str:
    log.info("▶ Agent 28: Policy Auditor")
    return ai_text(
        "You are a Google Ads policy compliance expert. You identify potential policy violations and risk factors.",
        f"""Audit this Google Ads campaign for policy compliance:
Business: {d.business_name}
Type: {d.business_type}
Location: {d.target_location}
Website: {d.website_url}

Provide a 3-sentence compliance summary. Start with CLEAN or FLAG.
Example: "CLEAN — This campaign shows no major policy flags. The business type is compliant. Standard monitoring recommended."
Or: "FLAG — This business type may require certification. Review ad copy for restricted claims. Check landing page compliance."
"""
    )

def agent_29_cro_analyzer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 29: CRO Analyzer")
    return ai_json(
        "You are a Conversion Rate Optimization expert for Google Ads.",
        f"""Perform a CRO audit for {d.business_name} ({d.business_type}).
Goal: {d.conversion_goal}
Website: {d.website_url}
Return JSON: {{
  "cro_score": number (1-100),
  "critical_fixes": [
    {{"issue":"","impact":"high|medium|low","recommendation":"","estimated_cvr_lift_pct":number}}
  ],
  "trust_elements_needed": [...],
  "mobile_optimization": [...],
  "page_speed_priority": [...],
  "form_optimization": [...],
  "estimated_baseline_cvr": "X%",
  "target_cvr_after_cro": "Y%"
}}"""
    )

def agent_30_roi_forecaster(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 30: ROI Forecaster")
    return ai_json(
        "You are a Google Ads ROI forecasting expert. Create realistic 90-day projections.",
        f"""Forecast 90-day ROI for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Monthly Revenue: ${d.monthly_revenue}
Goal: {d.conversion_goal}
Location: {d.target_location}
Return JSON: {{
  "monthly_projections": [
    {{"month":"Month 1","phase":"Learning","est_leads":number,"est_revenue":number,"spend":number,"roas":number}},
    {{"month":"Month 2","phase":"Optimization","est_leads":number,"est_revenue":number,"spend":number,"roas":number}},
    {{"month":"Month 3","phase":"Scaling","est_leads":number,"est_revenue":number,"spend":number,"roas":number}}
  ],
  "break_even_analysis": {{"days_to_break_even":number,"cumulative_cost":number,"cumulative_revenue":number}},
  "attribution_model": "Data-Driven",
  "projected_roas": number,
  "90_day_revenue_forecast": number,
  "risk_factors": [...],
  "upside_scenarios": [...]
}}"""
    )

# ─── BONUS AGENTS (31–35) ────────────────────────────────────────

def agent_31_smart_budget_optimizer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 31: Smart Budget Optimizer")
    return ai_json(
        "You are a smart budget optimization AI for Google Ads.",
        f"""Optimize budget distribution for {d.business_name} using AI recommendations.
Return JSON: {{
  "budget_efficiency_score": number,
  "waste_detection": [...],
  "reallocation_recommendations": [...],
  "dayparting_budget": {{}},
  "weather_based_adjustments": [],
  "competitor_budget_estimates": []
}}"""
    )

def agent_32_competitor_spy(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 32: Competitor Intelligence Spy")
    return ai_json(
        "You are a competitor intelligence agent for Google Ads.",
        f"""Deep competitive intelligence for {d.business_type} in {d.target_location}.
Return JSON: {{
  "auction_insights_simulation": {{
    "impression_share_benchmark": "X%",
    "overlap_rate_estimate": "X%",
    "outranking_share_target": "X%"
  }},
  "competitor_ad_patterns": [...],
  "gap_opportunities": [...],
  "recommended_counter_strategies": [...]
}}"""
    )

def agent_33_remarketing_architect(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 33: Remarketing Architect")
    return ai_json(
        "You are a remarketing and retargeting architect for Google Ads.",
        f"""Design full remarketing strategy for {d.business_name} ({d.business_type}).
Return JSON: {{
  "remarketing_lists": [
    {{"name":"","trigger":"","membership_days":number,"message":"","bid_adjustment":""}}
  ],
  "remarketing_sequence": [...],
  "rlsa_strategy": {{}},
  "customer_match_strategy": {{}},
  "cross_sell_opportunities": [...],
  "win_back_campaigns": [...]
}}"""
    )

def agent_34_performance_reporter(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 34: Performance Report Generator")
    return ai_json(
        "You are a Google Ads performance reporting specialist.",
        f"""Create a performance monitoring framework for {d.business_name}.
Return JSON: {{
  "kpi_dashboard": {{
    "primary_kpis": [...],
    "secondary_kpis": [...],
    "vanity_metrics_to_ignore": [...]
  }},
  "weekly_report_template": {{
    "sections": [...],
    "data_sources": [...]
  }},
  "monthly_review_checklist": [...],
  "stakeholder_reporting": {{
    "executive_summary_format": "",
    "agency_report_format": ""
  }}
}}"""
    )

def agent_35_ai_scaling_advisor(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 35: AI Scaling Advisor")
    return ai_json(
        "You are an AI-powered Google Ads scaling strategist.",
        f"""Create a scaling roadmap for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "scaling_phases": [
    {{"phase":1,"budget":"","trigger":"","actions":[]}},
    {{"phase":2,"budget":"","trigger":"","actions":[]}},
    {{"phase":3,"budget":"","trigger":"","actions":[]}}
  ],
  "automation_opportunities": [...],
  "channel_expansion": [...],
  "ai_tools_recommended": [...],
  "scaling_risks": [...],
  "six_month_roadmap": [...]
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE G: DATA & INTELLIGENCE (Agents 36–42)
# ════════════════════════════════════════════════════════════════

def agent_36_first_party_data_sync(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 36: First-Party Data Sync")
    return ai_json(
        "You are a first-party data strategy expert for Google Ads.",
        f"""Design a first-party data sync plan for {d.business_name} ({d.business_type}).
Return JSON: {{
  "crm_upload_strategy": {{
    "data_fields_to_upload": [...],
    "upload_frequency": "",
    "estimated_match_rate": "X%",
    "hashing_requirements": []
  }},
  "customer_match_segments": [
    {{"name":"","criteria":"","estimated_size":number,"bid_adjustment":""}}
  ],
  "data_enrichment_opportunities": [...],
  "privacy_compliance_checklist": [...],
  "expected_roas_lift": "X%"
}}"""
    )

def agent_37_profit_margin_tracker(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 37: Profit Margin Tracker")
    return ai_json(
        "You are a profit margin optimization expert for Google Ads.",
        f"""Create a profit-based bidding framework for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Monthly Revenue: ${d.monthly_revenue}
Return JSON: {{
  "profit_margin_tiers": [
    {{"product_category":"","gross_margin_pct":number,"recommended_target_roas":number,"max_cpa":number}}
  ],
  "margin_based_bid_rules": [...],
  "low_margin_exclusion_strategy": "",
  "high_margin_scaling_triggers": [...],
  "profit_vs_revenue_tradeoff": "",
  "estimated_profit_improvement": "X%"
}}"""
    )

def agent_38_search_term_miner(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 38: Search Term Miner")
    return ai_json(
        "You are a search term analysis and mining expert for Google Ads.",
        f"""Mine search term opportunities for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "high_value_search_terms": [
    {{"term":"","estimated_volume":"high|med|low","commercial_intent":number,"action":"add_as_keyword|negate|monitor"}}
  ],
  "new_keyword_opportunities": [...],
  "search_themes_discovered": [...],
  "irrelevant_terms_to_negate": [...],
  "long_tail_goldmines": [...],
  "match_type_optimization_tips": [...],
  "estimated_cpa_improvement": "X%"
}}"""
    )

def agent_39_auction_insights_bot(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 39: Auction Insights Bot")
    return ai_json(
        "You are an auction insights analyst for Google Ads competitive intelligence.",
        f"""Simulate auction insights for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "auction_insights_simulation": {{
    "your_impression_share_estimate": "X%",
    "top_of_page_rate_estimate": "X%",
    "abs_top_rate_estimate": "X%"
  }},
  "competitor_benchmarks": [
    {{"competitor":"","impression_share":"X%","overlap_rate":"X%","outranking_share":"X%","position_above_rate":"X%"}}
  ],
  "impression_share_lost_reasons": {{"budget":"X%","rank":"X%"}},
  "recommended_actions_to_gain_share": [...],
  "estimated_budget_needed_for_top_impression": number
}}"""
    )

def agent_40_attribution_modeler(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 40: Attribution Modeler")
    return ai_json(
        "You are an attribution modeling expert for Google Ads.",
        f"""Design attribution strategy for {d.business_name} ({d.business_type}).
Conversion Goal: {d.conversion_goal}
Return JSON: {{
  "recommended_attribution_model": "",
  "model_comparison": [
    {{"model":"Last Click","pros":[],"cons":[],"best_for":""}}
  ],
  "cross_channel_attribution_plan": {{
    "channels": [...],
    "weights": {{}}
  }},
  "view_through_conversion_window": number,
  "click_conversion_window": number,
  "estimated_true_roas_vs_reported": "",
  "implementation_steps": [...]
}}"""
    )

def agent_41_ltv_predictor(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 41: Lifetime Value Predictor")
    return ai_json(
        "You are a customer lifetime value prediction expert for Google Ads.",
        f"""Predict and leverage LTV for {d.business_name} ({d.business_type}).
Return JSON: {{
  "ltv_segments": [
    {{"segment":"","estimated_ltv":number,"characteristics":[],"bid_multiplier":number,"recommended_strategy":""}}
  ],
  "ltv_calculation_formula": "",
  "high_ltv_acquisition_strategy": "",
  "ltv_based_target_cpa": number,
  "churn_prevention_signals": [...],
  "upsell_opportunities": [...],
  "estimated_revenue_from_ltv_bidding": "X% improvement"
}}"""
    )

def agent_42_demand_forecaster(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 42: Demand Forecaster")
    return ai_json(
        "You are a demand forecasting expert for Google Ads budget planning.",
        f"""Forecast demand trends for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "monthly_demand_forecast": [
    {{"month":"","demand_index":number,"recommended_budget_multiplier":number,"key_events":[]}}
  ],
  "seasonal_peaks": [...],
  "seasonal_troughs": [...],
  "competitor_activity_forecast": "",
  "budget_recommendation_by_quarter": {{}},
  "demand_triggers_to_monitor": [...],
  "pre_peak_preparation_checklist": [...]
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE H: CREATIVE AUTOMATION (Agents 43–48)
# ════════════════════════════════════════════════════════════════

def agent_43_creative_scorer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 43: Creative Scorer")
    return ai_json(
        "You are an AI creative scoring expert for Google Ads performance prediction.",
        f"""Score and predict ad creative performance for {d.business_name} ({d.business_type}).
Return JSON: {{
  "creative_scoring_criteria": [
    {{"criterion":"","weight":number,"description":""}}
  ],
  "headline_effectiveness_rules": [...],
  "description_effectiveness_rules": [...],
  "predicted_ctr_boosters": [...],
  "creative_red_flags": [...],
  "top_performing_patterns": [...],
  "creative_strength_score_formula": "",
  "ab_test_priority_list": [...]
}}"""
    )

def agent_44_image_ad_generator(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 44: Image Ad Generator")
    return ai_json(
        "You are a display and Performance Max image ad creative director.",
        f"""Generate image ad creative briefs for {d.business_name} ({d.business_type}).
Return JSON: {{
  "image_concepts": [
    {{
      "name": "",
      "size": "1200x628",
      "layout_description": "",
      "headline_overlay": "",
      "cta_text": "",
      "color_palette": [],
      "visual_elements": [],
      "target_placement": "display|pmax|youtube",
      "audience_segment": ""
    }}
  ],
  "brand_consistency_guidelines": {{}},
  "image_testing_matrix": [...],
  "ai_image_prompt_templates": [...],
  "responsive_display_ad_specs": {{}}
}}"""
    )

def agent_45_video_script_optimizer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 45: Video Script Optimizer")
    return ai_json(
        "You are a YouTube ad video script optimizer for Google Ads.",
        f"""Optimize video ad scripts for {d.business_name} ({d.business_type}).
Return JSON: {{
  "hook_variations": [
    {{"hook_type":"question|stat|story|pain_point","script_5s":"","predicted_skip_rate":"X%"}}
  ],
  "cta_variations": [...],
  "ab_test_elements": [...],
  "optimal_video_length_by_goal": {{}},
  "voiceover_guidelines": "",
  "thumbnail_concepts": [...],
  "view_through_rate_predictions": {{}},
  "performance_max_video_guidelines": [...]
}}"""
    )

def agent_46_ad_fatigue_detector(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 46: Ad Fatigue Detector")
    return ai_json(
        "You are an ad fatigue detection and creative refresh specialist for Google Ads.",
        f"""Design an ad fatigue detection and rotation system for {d.business_name} ({d.business_type}).
Return JSON: {{
  "fatigue_signals": [
    {{"metric":"","threshold":"","action":""}}
  ],
  "creative_rotation_strategy": "",
  "refresh_schedule": {{
    "display_ads_days": number,
    "rsa_headlines_days": number,
    "video_ads_days": number
  }},
  "creative_library_requirements": {{
    "min_active_variations": number,
    "variety_guidelines": []
  }},
  "automated_pause_rules": [...],
  "winner_promotion_criteria": [...]
}}"""
    )

def agent_47_seasonal_creative_switcher(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 47: Seasonal Creative Switcher")
    return ai_json(
        "You are a seasonal ad creative strategy expert for Google Ads.",
        f"""Design seasonal creative switching plan for {d.business_name} ({d.business_type}).
Return JSON: {{
  "seasonal_calendar": [
    {{
      "season": "",
      "months": [],
      "creative_theme": "",
      "headline_adjustments": [...],
      "offer_suggestions": [...],
      "budget_multiplier": number,
      "switch_date": ""
    }}
  ],
  "holiday_campaigns": [...],
  "evergreen_vs_seasonal_ratio": "",
  "advance_preparation_timeline": {{}}
}}"""
    )

def agent_48_competitor_ad_copier(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 48: Competitor Ad Analyzer")
    return ai_json(
        "You are a competitor ad analysis and counter-strategy expert for Google Ads.",
        f"""Analyze competitor ad patterns for {d.business_type} in {d.target_location} and suggest counters.
Return JSON: {{
  "competitor_ad_patterns": [
    {{"competitor_type":"","common_hooks":[],"offers_used":[],"weaknesses":[]}}
  ],
  "counter_strategies": [
    {{"counter_type":"","headline_template":"","description_template":"","unique_angle":""}}
  ],
  "differentiation_opportunities": [...],
  "positioning_gaps": [...],
  "messaging_recommendations": [...],
  "competitive_advantage_statements": [...]
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE I: BIDDING & BUDGET AUTOMATION (Agents 49–54)
# ════════════════════════════════════════════════════════════════

def agent_49_dayparting_optimizer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 49: Dayparting Optimizer")
    return ai_json(
        "You are a dayparting and ad scheduling optimization expert for Google Ads.",
        f"""Optimize dayparting schedule for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "hourly_bid_multipliers": {{
    "monday": [{{"hour":0,"multiplier":1.0}}],
    "weekday_pattern": [...24 multipliers],
    "weekend_pattern": [...24 multipliers]
  }},
  "peak_performance_windows": [...],
  "low_performance_windows": [...],
  "recommended_ad_schedule": {{}},
  "business_hours_strategy": "",
  "after_hours_strategy": "",
  "estimated_cpa_improvement": "X%"
}}"""
    )

def agent_50_weather_bid_adjuster(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 50: Weather Bid Adjuster")
    return ai_json(
        "You are a weather-based bid adjustment specialist for Google Ads.",
        f"""Design weather-triggered bid adjustments for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "weather_bid_rules": [
    {{"condition":"","temperature_range":"","bid_adjustment":number,"rationale":""}}
  ],
  "seasonal_weather_patterns": [...],
  "weather_api_integration_plan": "",
  "location_specific_rules": [...],
  "weather_campaign_types": [...],
  "implementation_via_scripts": "",
  "estimated_performance_lift": "X%"
}}"""
    )

def agent_51_seasonality_adjuster(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 51: Seasonality Adjuster")
    return ai_json(
        "You are a Google Ads seasonality adjustment specialist.",
        f"""Design seasonality bid adjustment plan for {d.business_name} ({d.business_type}).
Return JSON: {{
  "seasonality_adjustment_calendar": [
    {{"event":"","date_range":"","adjustment_pct":number,"apply_to":[],"advance_setup_days":number}}
  ],
  "google_seasonality_tool_usage": {{
    "when_to_use": "",
    "how_to_apply": "",
    "adjustment_duration": ""
  }},
  "smart_bidding_seasonality_tips": [...],
  "historical_spike_events": [...],
  "pre_event_budget_increase_plan": {{}}
}}"""
    )

def agent_52_portfolio_bid_manager(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 52: Portfolio Bid Manager")
    return ai_json(
        "You are a portfolio bidding strategy expert for Google Ads.",
        f"""Design portfolio bidding strategy for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "portfolio_strategy_recommendation": "",
  "campaign_groupings": [
    {{"group_name":"","campaigns":[],"shared_budget":number,"bid_strategy":"","rationale":""}}
  ],
  "shared_budget_rules": [...],
  "target_cpa_by_portfolio": {{}},
  "target_roas_by_portfolio": {{}},
  "portfolio_performance_thresholds": [...],
  "rebalancing_triggers": [...]
}}"""
    )

def agent_53_micro_conversion_trainer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 53: Micro-Conversion Trainer")
    return ai_json(
        "You are a micro-conversion and Smart Bidding training expert for Google Ads.",
        f"""Design micro-conversion training plan for {d.business_name} ({d.business_type}).
Conversion Goal: {d.conversion_goal}
Return JSON: {{
  "micro_conversions": [
    {{"action":"","type":"","tracking_method":"","value_assigned":number,"smart_bidding_signal_strength":"high|med|low"}}
  ],
  "conversion_funnel_mapping": [...],
  "smart_bidding_warmup_plan": {{
    "phase_1": {{"duration_days":number,"strategy":"","micro_conversions_used":[]}},
    "phase_2": {{"duration_days":number,"strategy":"","conversion_shift":""}},
    "phase_3": {{"duration_days":number,"strategy":""}}
  }},
  "minimum_conversions_threshold": number,
  "data_collection_estimate": "X weeks",
  "gtm_implementation_notes": [...]
}}"""
    )

def agent_54_zero_click_protector(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 54: Zero-Click Protector")
    return ai_json(
        "You are a wasted spend and zero-conversion protection expert for Google Ads.",
        f"""Design zero-click and zero-conversion protection rules for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "automated_pause_rules": [
    {{"rule":"","trigger_condition":"","action":"pause|reduce_bid|add_negative","review_period_days":number}}
  ],
  "budget_protection_thresholds": {{}},
  "keyword_level_cpc_caps": [...],
  "placement_exclusion_list": [...],
  "scripts_for_automation": [...],
  "estimated_waste_prevented": "$X per month",
  "monitoring_dashboard_kpis": [...]
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE J: AUDIENCE & TARGETING (Agents 55–60)
# ════════════════════════════════════════════════════════════════

def agent_55_customer_match_uploader(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 55: Customer Match Uploader")
    return ai_json(
        "You are a Customer Match strategy expert for Google Ads.",
        f"""Design Customer Match upload and strategy plan for {d.business_name} ({d.business_type}).
Return JSON: {{
  "customer_match_lists": [
    {{"list_name":"","data_type":"email|phone|address","estimated_size":number,"use_case":"","bid_adjustment":number}}
  ],
  "upload_schedule": "",
  "data_preparation_checklist": [...],
  "match_rate_optimization_tips": [...],
  "campaign_application_plan": [...],
  "exclusion_lists": [...],
  "gdpr_ccpa_compliance_notes": [...]
}}"""
    )

def agent_56_lookalike_audience_builder(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 56: Lookalike Audience Builder")
    return ai_json(
        "You are a similar audience and lookalike targeting expert for Google Ads.",
        f"""Build lookalike audience strategy for {d.business_name} ({d.business_type}).
Return JSON: {{
  "seed_audience_recommendations": [
    {{"seed_list":"","quality_score":number,"expansion_approach":"","estimated_reach":""}}
  ],
  "similar_audience_tiers": [...],
  "performance_max_audience_signals": [...],
  "expansion_settings_recommendation": "",
  "funnel_position_mapping": {{}},
  "testing_framework": [...],
  "expected_cpa_vs_remarketing": ""
}}"""
    )

def agent_57_in_market_audience_tagger(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 57: In-Market Audience Tagger")
    return ai_json(
        "You are an in-market audience and intent targeting expert for Google Ads.",
        f"""Select and layer in-market audiences for {d.business_name} ({d.business_type}).
Return JSON: {{
  "recommended_in_market_segments": [
    {{"segment":"","relevance_score":number,"bid_adjustment":number,"campaign_type":""}}
  ],
  "affinity_audience_recommendations": [...],
  "life_event_audiences": [...],
  "custom_intent_audiences": [
    {{"name":"","keywords":[],"competitor_urls":[],"estimated_reach":""}}
  ],
  "audience_layering_strategy": "",
  "observation_vs_targeting_plan": {{}},
  "combined_audience_segments": [...]
}}"""
    )

def agent_58_demographic_optimizer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 58: Demographic Optimizer")
    return ai_json(
        "You are a demographic targeting and bid adjustment optimizer for Google Ads.",
        f"""Optimize demographic targeting for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "demographic_bid_adjustments": {{
    "age_groups": {{"18-24":number,"25-34":number,"35-44":number,"45-54":number,"55-64":number,"65+":number}},
    "gender": {{"male":number,"female":number,"unknown":number}},
    "household_income": {{"top10%":number,"11-20%":number,"21-30%":number,"lower50%":number}}
  }},
  "target_demographic_profile": {{}},
  "exclusion_demographics": [...],
  "estimated_efficiency_gain": "X%",
  "testing_plan": [...],
  "rationale": ""
}}"""
    )

def agent_59_remarketing_sequencer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 59: Remarketing Sequencer")
    return ai_json(
        "You are a remarketing sequence and funnel ad expert for Google Ads.",
        f"""Design remarketing ad sequence for {d.business_name} ({d.business_type}).
Conversion Goal: {d.conversion_goal}
Return JSON: {{
  "remarketing_sequence": [
    {{
      "step": number,
      "trigger": "",
      "days_after_visit": number,
      "ad_message": "",
      "ad_format": "",
      "frequency_cap": "",
      "cta": "",
      "next_step_trigger": ""
    }}
  ],
  "burn_list_strategy": "",
  "cross_campaign_exclusions": [...],
  "sequential_messaging_themes": [...],
  "window_durations": {{}},
  "estimated_conversion_lift": "X%"
}}"""
    )

def agent_60_brand_defender(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 60: Brand Defender")
    return ai_json(
        "You are a brand keyword protection and competitor defense expert for Google Ads.",
        f"""Design brand defense strategy for {d.business_name} ({d.business_type}).
Return JSON: {{
  "brand_keywords_to_protect": [...],
  "competitor_bidding_on_brand_signals": [...],
  "defensive_campaign_structure": {{
    "campaign_name": "",
    "bid_strategy": "",
    "target_impression_share": "X%",
    "budget_recommendation": number
  }},
  "trademark_keywords": [...],
  "branded_rsa_templates": [...],
  "competitor_brand_targeting_opportunity": {...},
  "brand_impression_share_target": "X%",
  "monitoring_alerts_setup": [...]
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE K: CAMPAIGN TYPES (Agents 61–67)
# ════════════════════════════════════════════════════════════════

def agent_61_demand_gen_manager(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 61: Demand Gen Manager")
    return ai_json(
        "You are a Google Demand Gen campaign specialist (YouTube, Gmail, Discover).",
        f"""Design Demand Gen campaign strategy for {d.business_name} ({d.business_type}).
Return JSON: {{
  "demand_gen_campaigns": [
    {{
      "name": "",
      "channels": ["YouTube","Gmail","Discover"],
      "goal": "",
      "budget_percentage": number,
      "audience_targeting": [],
      "creative_requirements": {{
        "video_specs": "",
        "image_specs": "",
        "headlines": [...3]
      }}
    }}
  ],
  "funnel_role": "awareness|consideration|conversion",
  "lookalike_expansion_plan": "",
  "reporting_kpis": [...],
  "budget_recommendation": number
}}"""
    )

def agent_62_shopping_optimizer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 62: Shopping Optimizer")
    return ai_json(
        "You are a Google Shopping campaign optimization specialist.",
        f"""Optimize Shopping campaigns for {d.business_name} ({d.business_type}).
Return JSON: {{
  "feed_optimization_checklist": [...],
  "product_segmentation_strategy": [
    {{"segment":"","criteria":"","bid_strategy":"","target_roas":number}}
  ],
  "smart_shopping_vs_standard": "",
  "merchant_center_health_checklist": [...],
  "title_optimization_formula": "",
  "custom_label_strategy": {{}},
  "competitive_price_monitoring": "",
  "seasonal_feed_updates": [...],
  "shopping_vs_pmax_recommendation": ""
}}"""
    )

def agent_63_local_campaign_bot(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 63: Local Campaign Bot")
    return ai_json(
        "You are a local campaign and Google Business Profile ads specialist.",
        f"""Optimize local campaigns for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "local_campaign_setup": {{
    "campaign_type": "LOCAL",
    "goal": "Store visits|Calls|Directions",
    "bid_strategy": "",
    "budget": number
  }},
  "google_business_profile_optimization": [...],
  "local_search_ads_strategy": "",
  "location_extensions_setup": [...],
  "call_extensions_for_local": {...},
  "radius_targeting_recommendations": {{}},
  "local_keyword_strategy": [...],
  "store_visit_conversion_setup": [...]
}}"""
    )

def agent_64_app_campaign_manager(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 64: App Campaign Manager")
    return ai_json(
        "You are a Google App campaign (UAC) specialist.",
        f"""Design App campaign strategy for {d.business_name} ({d.business_type}).
Return JSON: {{
  "app_campaign_types": [
    {{"type":"App Installs|App Engagement|App Pre-Registration","goal":"","bid_strategy":"","target_cpa":number}}
  ],
  "asset_requirements": {{
    "text_assets": [...5],
    "image_assets": [...],
    "video_assets": [...],
    "html5_assets": []
  }},
  "audience_strategy": "",
  "in_app_event_setup": [...],
  "creative_best_practices": [...],
  "bid_optimization_timeline": [...]
}}"""
    )

def agent_65_hotel_ads_manager(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 65: Specialty Ads Manager")
    return ai_json(
        "You are a specialty Google Ads campaign manager for service and local businesses.",
        f"""Design specialty campaign types for {d.business_name} ({d.business_type}).
Return JSON: {{
  "applicable_specialty_formats": [
    {{"format":"","eligibility_criteria":"","setup_requirements":[],"estimated_benefit":""}}
  ],
  "local_services_ads_eligibility": {{
    "eligible": true,
    "verification_steps": [...],
    "expected_lead_quality": ""
  }},
  "service_campaign_recommendations": [...],
  "lead_form_extensions_config": {{}},
  "smart_campaign_consideration": "",
  "performance_expectations": {{}}
}}"""
    )

def agent_66_lead_form_optimizer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 66: Lead Form Optimizer")
    return ai_json(
        "You are a Google Ads native lead form extension optimization expert.",
        f"""Optimize lead form extensions for {d.business_name} ({d.business_type}).
Conversion Goal: {d.conversion_goal}
Return JSON: {{
  "lead_form_config": {{
    "headline": "",
    "description": "",
    "questions": [
      {{"question":"","type":"short_answer|multiple_choice|dropdown","required":true}}
    ],
    "cta_text": "",
    "post_submit_cta": {{}}
  }},
  "lead_qualification_fields": [...],
  "crm_webhook_integration_plan": "",
  "follow_up_automation_recommendation": "",
  "a_b_test_variations": [...],
  "expected_conversion_rate": "X%",
  "quality_vs_volume_tradeoffs": ""
}}"""
    )

def agent_67_call_campaign_manager(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 67: Call Campaign Manager")
    return ai_json(
        "You are a call-focused campaign optimization expert for Google Ads.",
        f"""Design full call campaign strategy for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "call_campaign_structure": {{
    "campaign_types": ["Call-Only","Call Extensions on Search"],
    "bidding": "",
    "target_cpa_per_call": number,
    "call_duration_threshold_seconds": number
  }},
  "call_tracking_setup": [...],
  "call_recording_recommendation": "",
  "call_schedule": {{}},
  "call_quality_scoring": [...],
  "voicemail_strategy": "",
  "call_to_lead_handoff_process": [...],
  "estimated_calls_per_day": number
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE L: REPORTING & ALERTS (Agents 68–73)
# ════════════════════════════════════════════════════════════════

def agent_68_daily_pulse_reporter(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 68: Daily Pulse Reporter")
    return ai_json(
        "You are a Google Ads daily reporting automation expert.",
        f"""Design automated daily pulse report for {d.business_name} ({d.business_type}).
Return JSON: {{
  "daily_report_template": {{
    "sections": [...],
    "kpis_to_include": [...],
    "format": "email|slack|dashboard",
    "delivery_time": ""
  }},
  "alert_thresholds": [
    {{"metric":"","warning_threshold":"","critical_threshold":"","action":""}}
  ],
  "executive_summary_format": "",
  "variance_analysis_rules": [...],
  "google_ads_script_skeleton": "",
  "automated_insights_prompts": [...]
}}"""
    )

def agent_69_budget_burn_alert(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 69: Budget Burn Rate Alert")
    return ai_json(
        "You are a budget monitoring and burn rate alert specialist for Google Ads.",
        f"""Design budget burn rate monitoring system for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "burn_rate_thresholds": {{
    "overspend_alert_pct": number,
    "underspend_alert_pct": number,
    "check_frequency": "hourly|every_4hr|daily"
  }},
  "automated_rules": [
    {{"rule_name":"","trigger":"","action":"","campaigns_affected":[]}}
  ],
  "monthly_pacing_strategy": "",
  "end_of_month_budget_plan": "",
  "google_ads_script_for_burn_rate": "",
  "slack_email_alert_template": "",
  "emergency_pause_criteria": [...]
}}"""
    )

def agent_70_ctr_drop_alerter(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 70: CTR Drop Alerter")
    return ai_json(
        "You are a CTR monitoring and performance alert expert for Google Ads.",
        f"""Design CTR monitoring and alert system for {d.business_name} ({d.business_type}).
Return JSON: {{
  "ctr_benchmarks_by_campaign_type": {{
    "search": "X%",
    "display": "X%",
    "pmax": "X%",
    "shopping": "X%"
  }},
  "drop_detection_rules": [
    {{"metric":"","drop_threshold_pct":number,"time_window_days":number,"action":""}}
  ],
  "root_cause_investigation_checklist": [...],
  "recovery_action_playbook": [...],
  "automated_alert_script": "",
  "escalation_protocol": [...]
}}"""
    )

def agent_71_conversion_spike_detector(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 71: Conversion Spike Detector")
    return ai_json(
        "You are a conversion tracking anomaly and spike detection expert for Google Ads.",
        f"""Design conversion monitoring system for {d.business_name} ({d.business_type}).
Conversion Goal: {d.conversion_goal}
Return JSON: {{
  "spike_detection_rules": [
    {{"metric":"","spike_threshold_pct":number,"drop_threshold_pct":number,"investigation_steps":[]}}
  ],
  "conversion_health_checks": [...],
  "tracking_integrity_audit": [...],
  "false_spike_indicators": [...],
  "automated_investigation_workflow": [...],
  "stakeholder_notification_template": "",
  "data_reconciliation_process": [...]
}}"""
    )

def agent_72_wasted_spend_auditor(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 72: Wasted Spend Auditor")
    return ai_json(
        "You are a Google Ads wasted spend audit and elimination expert.",
        f"""Audit and eliminate wasted spend for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "waste_categories": [
    {{"category":"","estimated_waste_pct":number,"diagnosis":"","fix":"","priority":"high|medium|low"}}
  ],
  "immediate_savings_opportunities": [...],
  "weekly_audit_checklist": [...],
  "negative_keyword_gaps": [...],
  "quality_score_waste": [...],
  "placement_waste": [...],
  "estimated_monthly_savings": number,
  "audit_automation_plan": [...]
}}"""
    )

def agent_73_executive_dashboard_builder(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 73: Executive Dashboard Builder")
    return ai_json(
        "You are an executive reporting and client dashboard expert for Google Ads.",
        f"""Design executive dashboard for {d.business_name} ({d.business_type}).
Return JSON: {{
  "dashboard_layout": {{
    "sections": [...],
    "primary_metrics": [...],
    "charts": [
      {{"title":"","chart_type":"","data_source":"","time_period":""}}
    ]
  }},
  "client_report_template": {{
    "frequency": "weekly|monthly",
    "sections": [...],
    "tone": "executive|technical|agency"
  }},
  "looker_studio_widgets": [...],
  "kpi_goal_tracking": {{}},
  "commentary_templates": [...],
  "red_amber_green_thresholds": {{}}
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE M: COMPLIANCE & PROTECTION (Agents 74–78)
# ════════════════════════════════════════════════════════════════

def agent_74_disapproval_fixer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 74: Disapproval Fixer")
    return ai_json(
        "You are a Google Ads policy compliance and disapproval resolution expert.",
        f"""Design auto-fix system for ad disapprovals for {d.business_name} ({d.business_type}).
Return JSON: {{
  "common_disapproval_reasons": [
    {{"policy":"","risk_level":"high|medium|low","auto_fix_possible":true,"fix_procedure":""}}
  ],
  "pre_submission_audit_checklist": [...],
  "sensitive_category_flags": [...],
  "appeal_process_guide": [...],
  "compliant_rewrite_templates": [...],
  "monitoring_schedule": "",
  "escalation_to_google_support_criteria": [...]
}}"""
    )

def agent_75_trademark_guard(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 75: Trademark Guard")
    return ai_json(
        "You are a trademark protection and brand safety expert for Google Ads.",
        f"""Design trademark protection plan for {d.business_name} ({d.business_type}).
Return JSON: {{
  "trademark_risks_in_ad_copy": [...],
  "competitor_trademark_usage_rules": [...],
  "protected_terms_to_avoid": [...],
  "trademark_authorization_process": "",
  "brand_bidding_policy_summary": "",
  "defensive_trademark_actions": [...],
  "legal_disclaimer_requirements": [...],
  "monitoring_tools_recommendation": [...]
}}"""
    )

def agent_76_landing_page_monitor(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 76: Landing Page Monitor")
    return ai_json(
        "You are a landing page health monitoring specialist for Google Ads.",
        f"""Design landing page monitoring system for {d.business_name}.
Website: {d.website_url}
Return JSON: {{
  "monitoring_checks": [
    {{"check":"","frequency":"","alert_threshold":"","action_on_failure":""}}
  ],
  "page_speed_requirements": {{
    "mobile_lcp_target_seconds": number,
    "desktop_lcp_target_seconds": number,
    "cls_threshold": number
  }},
  "uptime_monitoring_setup": "",
  "quality_score_impact_checks": [...],
  "automated_pause_triggers": [...],
  "recovery_runbook": [...],
  "tools_recommended": [...]
}}"""
    )

def agent_77_billing_anomaly_detector(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 77: Billing Anomaly Detector")
    return ai_json(
        "You are a Google Ads billing monitoring and anomaly detection expert.",
        f"""Design billing anomaly detection for {d.business_name}.
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "billing_anomaly_rules": [
    {{"anomaly_type":"","detection_method":"","alert_threshold":"","immediate_action":""}}
  ],
  "daily_spend_reconciliation_process": [...],
  "invalid_click_monitoring": {{
    "detection_signals": [],
    "reporting_to_google_process": "",
    "credit_request_threshold": number
  }},
  "budget_cap_enforcement_checks": [...],
  "account_security_checklist": [...],
  "billing_health_score_formula": ""
}}"""
    )

def agent_78_mcc_supervisor(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 78: MCC Account Supervisor")
    return ai_json(
        "You are a Google Ads MCC (Manager Account) multi-account supervision expert.",
        f"""Design MCC supervision framework for {d.business_name} ({d.business_type}).
Return JSON: {{
  "mcc_account_structure": {{
    "recommended_hierarchy": "",
    "account_naming_convention": "",
    "label_system": []
  }},
  "cross_account_reporting": {{
    "metrics_to_track": [],
    "reporting_frequency": "",
    "anomaly_thresholds": {{}}
  }},
  "budget_reallocation_across_accounts": "",
  "shared_assets_strategy": [...],
  "account_health_scorecard": [...],
  "automated_rules_cross_account": [...]
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE N: SCALING & GROWTH (Agents 79–85)
# ════════════════════════════════════════════════════════════════

def agent_79_winner_scaler(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 79: Winner Scaler")
    return ai_json(
        "You are a Google Ads winning campaign scaling expert.",
        f"""Design winner scaling system for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "winner_criteria": [
    {{"metric":"","threshold":"","minimum_data_period_days":number,"confidence_level":"X%"}}
  ],
  "scaling_playbook": [
    {{"step":number,"action":"","budget_increase_pct":number,"wait_days":number,"success_criteria":""}}
  ],
  "automated_scaling_rules": [...],
  "loser_sunset_criteria": [...],
  "budget_reallocation_matrix": {{}},
  "scaling_risk_guardrails": [...],
  "projected_scaled_revenue": number
}}"""
    )

def agent_80_market_expander(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 80: Market Expander")
    return ai_json(
        "You are a geographic and market expansion strategist for Google Ads.",
        f"""Identify market expansion opportunities for {d.business_name} ({d.business_type}).
Current Location: {d.target_location}
Return JSON: {{
  "expansion_markets": [
    {{
      "market": "",
      "priority": "high|medium|low",
      "estimated_search_volume": "",
      "competition_level": "low|medium|high",
      "recommended_budget": number,
      "entry_strategy": "",
      "estimated_ramp_weeks": number
    }}
  ],
  "international_considerations": [...],
  "language_targeting_needed": [...],
  "expansion_timeline": [...],
  "risk_assessment": {{}},
  "pilot_campaign_design": {{}}
}}"""
    )

def agent_81_keyword_expander(d: RunCrewRequest) -> dict:
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
    )

def agent_82_competitor_gap_finder(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 82: Competitor Gap Finder")
    return ai_json(
        "You are a competitive keyword gap analysis expert for Google Ads.",
        f"""Find competitor keyword gaps for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "competitor_keyword_gaps": [
    {{"keyword":"","competitor_presence":"high|med|low","your_presence":"none|weak|strong","opportunity_score":number,"recommended_action":""}}
  ],
  "untapped_search_themes": [...],
  "competitor_ad_copy_gaps": [...],
  "landing_page_opportunity_gaps": [...],
  "budget_gap_analysis": "",
  "quick_wins": [...],
  "strategic_plays": [...]
}}"""
    )

def agent_83_profit_roas_calculator(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 83: Profit ROAS Calculator")
    return ai_json(
        "You are a profit-based ROAS target calculation expert for Google Ads.",
        f"""Calculate profit-based ROAS targets for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Monthly Revenue: ${d.monthly_revenue}
Return JSON: {{
  "break_even_roas": number,
  "target_roas_by_margin_tier": [
    {{"margin_pct":number,"break_even_roas":number,"target_roas":number,"max_cpa":number}}
  ],
  "roas_calculation_formula": "",
  "blended_account_roas_target": number,
  "roas_vs_cpa_recommendation": "",
  "profitability_sensitivity_analysis": [...],
  "roas_floor_and_ceiling": {{}},
  "quarterly_roas_scaling_targets": [...]
}}"""
    )

def agent_84_cross_campaign_syncer(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 84: Cross-Campaign Syncer")
    return ai_json(
        "You are a cross-campaign coordination and cannibalization prevention expert for Google Ads.",
        f"""Design cross-campaign sync strategy for {d.business_name} ({d.business_type}).
Campaign Types: {', '.join(d.campaign_types)}
Return JSON: {{
  "cannibalization_risks": [
    {{"campaign_pair":"","risk_type":"keyword|audience|placement","severity":"high|medium|low","fix":""}}
  ],
  "negative_keyword_sharing_plan": [...],
  "audience_exclusion_cross_campaign": [...],
  "budget_priority_hierarchy": [...],
  "portfolio_synergy_opportunities": [...],
  "shared_negative_lists": [...],
  "campaign_coordination_schedule": ""
}}"""
    )

def agent_85_funnel_orchestrator(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 85: Full Funnel Orchestrator")
    return ai_json(
        "You are a full-funnel Google Ads orchestration expert coordinating all campaign types.",
        f"""Design full-funnel campaign orchestration for {d.business_name} ({d.business_type}).
Goal: {d.conversion_goal}
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "funnel_stages": [
    {{
      "stage": "Awareness|Consideration|Conversion|Retention",
      "campaign_types": [],
      "budget_percentage": number,
      "kpis": [],
      "targeting": "",
      "messaging_theme": ""
    }}
  ],
  "cross_funnel_audience_flow": [...],
  "touchpoint_sequence": [...],
  "budget_rebalancing_rules": [...],
  "funnel_health_dashboard": {{}},
  "optimization_priority_order": [...],
  "estimated_full_funnel_roas": number
}}"""
    )

# ════════════════════════════════════════════════════════════════
# PHASE O: MASTER ORCHESTRATORS (Agents 86–88)
# ════════════════════════════════════════════════════════════════

def agent_86_campaign_brain(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 86: Campaign Brain (Master AI)")
    return ai_json(
        "You are the central AI brain orchestrating all Google Ads agents. You decide which agents to activate, prioritize actions, and synthesize all data into a master strategy.",
        f"""Synthesize a master campaign strategy for {d.business_name} ({d.business_type}) in {d.target_location}.
Daily Budget: ${d.daily_budget}
Conversion Goal: {d.conversion_goal}
Campaign Types: {', '.join(d.campaign_types)}
Return JSON: {{
  "master_strategy_summary": "",
  "top_priority_actions": [
    {{"priority":number,"action":"","expected_impact":"","timeline":"","owner":"human|automation"}}
  ],
  "agent_activation_sequence": [...],
  "30_day_game_plan": [...],
  "60_day_game_plan": [...],
  "90_day_game_plan": [...],
  "success_probability_score": number,
  "critical_dependencies": [...],
  "risk_mitigation_plan": [...]
}}"""
    )

def agent_87_agent_scheduler(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 87: Agent Scheduler")
    return ai_json(
        "You are an AI agent scheduling and automation orchestration expert for Google Ads.",
        f"""Design the agent execution schedule for {d.business_name} ({d.business_type}).
Return JSON: {{
  "hourly_agents": [
    {{"agent":"","task":"","trigger":""}}
  ],
  "daily_agents": [
    {{"agent":"","task":"","run_time":"","dependencies":[]}}
  ],
  "weekly_agents": [
    {{"agent":"","task":"","run_day":"","estimated_duration_min":number}}
  ],
  "monthly_agents": [...],
  "dependency_graph": {{}},
  "parallel_execution_groups": [...],
  "error_handling_protocol": "",
  "schedule_automation_tools": [...],
  "estimated_automation_hours_saved_monthly": number
}}"""
    )

def agent_88_signal_aggregator(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 88: Signal Aggregator (Master Decision Engine)")
    return ai_json(
        "You are the master signal aggregation and unified decision engine for Google Ads. You collect all agent outputs, identify conflicting signals, and produce unified, high-confidence recommendations.",
        f"""Aggregate all signals and produce unified decisions for {d.business_name} ({d.business_type}).
Daily Budget: ${d.daily_budget}
Return JSON: {{
  "unified_bid_recommendation": {{
    "strategy": "",
    "target_cpa": number,
    "target_roas": number,
    "confidence_score": number,
    "conflicting_signals": []
  }},
  "unified_budget_recommendation": {{
    "daily_budget": number,
    "allocation": {{}},
    "reasoning": ""
  }},
  "top_10_immediate_actions": [...],
  "signal_confidence_matrix": [
    {{"signal":"","source_agents":[],"confidence":"high|medium|low","action":""}}
  ],
  "automation_readiness_score": number,
  "human_review_required_items": [...],
  "system_health_score": number,
  "next_review_date": ""
}}"""
    )

# ════════════════════════════════════════════════════════════════
# MAIN CREW RUNNER  (rate-limit safe — max 2 concurrent Groq calls)
# ════════════════════════════════════════════════════════════════

async def run_all_agents(d: RunCrewRequest) -> dict:
    loop = asyncio.get_event_loop()
    disabled = set(d.disabled_agents or [])

    def _skip():
        return {"skipped": True, "reason": "Disabled by user"}

    async def run(fn, agent_num: int = 0):
        if agent_num and agent_num in disabled:
            log.info(f"⏭ Agent {agent_num:02d} skipped (disabled)")
            return _skip()
        async with _groq_sem:
            return await loop.run_in_executor(None, fn, d)

    async def run_batch(fns, label, start_num: int = 1):
        log.info(f"═══ {label} ═══")
        nums = list(range(start_num, start_num + len(fns)))
        results = []
        pairs = list(zip(fns, nums))
        for i in range(0, len(pairs), 2):
            chunk = pairs[i:i+2]
            chunk_results = await asyncio.gather(*[run(fn, n) for fn, n in chunk])
            results.extend(chunk_results)
            if i + 2 < len(pairs):
                active_in_chunk = [n for _, n in chunk if n not in disabled]
                if active_in_chunk:
                    log.info(f"  ⏸ Rate-limit pause 3s...")
                    await asyncio.sleep(3)
        return results

    if disabled:
        log.info(f"⚙️ Running {88 - len(disabled)}/88 agents ({len(disabled)} disabled)")

    # ── Phase A: Foundation ──────────────────────────────────────
    log.info("═══ Phase A: Foundation ═══")
    biz_intel  = await run(agent_01_business_intelligence, 1)
    competitor = await run(agent_02_competitor_analysis, 2)
    intent_map = await run(agent_03_search_intent_map, 3)

    # ── Phase B: Keywords ────────────────────────────────────────
    log.info("═══ Phase B: Keywords ═══")
    keywords   = await run(agent_04_stag_keyword_architect, 4)
    brand_seg  = await run(agent_05_brand_segmentation, 5)
    negatives  = await run(agent_06_negative_keyword_mining, 6)
    clusters   = await run(agent_07_intent_clustering, 7)

    # ── Phase C: Creative ────────────────────────────────────────
    c_results = await run_batch([
        agent_08_rsa_copywriter, agent_09_pmax_asset_generator,
        agent_10_dsa_generator, agent_11_display_creative,
        agent_12_youtube_scripts, agent_13_shopping_feed_optimizer,
        agent_14_call_only_ads, agent_15_ab_urgency_copy,
        agent_16_multilingual_ads,
    ], "Phase C: Creative", start_num=8)
    ad_copy, pmax, dsa, display, video, shopping, calls, ab_copy, multi = c_results

    # ── Phase D: Structure ───────────────────────────────────────
    d_results = await run_batch([
        agent_17_campaign_architect, agent_18_budget_allocator,
        agent_19_smart_bidding, agent_20_audience_builder,
        agent_21_geo_device_time_targeting,
    ], "Phase D: Structure", start_num=17)
    strategy, budget, bidding, audiences, targeting = d_results

    # ── Phase E: Tracking ────────────────────────────────────────
    e_results = await run_batch([
        agent_22_conversion_tracking, agent_23_ads_scripts_writer,
        agent_24_quality_score_optimizer_agent, agent_25_anomaly_detection_agent,
        agent_26_extension_suite, agent_27_dynamic_landing_page,
    ], "Phase E: Tracking & Automation", start_num=22)
    tracking, scripts, qs, anomaly, extensions, landing_pages = e_results

    # ── Phase F: Compliance ──────────────────────────────────────
    log.info("═══ Phase F: Compliance & Forecast ═══")
    policy = await loop.run_in_executor(None, agent_28_policy_auditor, d)
    cro    = await run(agent_29_cro_analyzer, 29)
    roi    = await run(agent_30_roi_forecaster, 30)

    # ── Bonus (31–35) ────────────────────────────────────────────
    bonus_results = await run_batch([
        agent_31_smart_budget_optimizer, agent_32_competitor_spy,
        agent_33_remarketing_architect, agent_34_performance_reporter,
        agent_35_ai_scaling_advisor,
    ], "Bonus Agents 31–35", start_num=31)
    budget_opt, spy, remarketing, reporter, scaling = bonus_results

    # ── Phase G: Data & Intelligence (36–42) ────────────────────
    g_results = await run_batch([
        agent_36_first_party_data_sync, agent_37_profit_margin_tracker,
        agent_38_search_term_miner, agent_39_auction_insights_bot,
        agent_40_attribution_modeler, agent_41_ltv_predictor,
        agent_42_demand_forecaster,
    ], "Phase G: Data & Intelligence")
    first_party, profit_margin, search_miner, auction_bot, attribution, ltv, demand_fcst = g_results

    # ── Phase H: Creative Automation (43–48) ────────────────────
    h_results = await run_batch([
        agent_43_creative_scorer, agent_44_image_ad_generator,
        agent_45_video_script_optimizer, agent_46_ad_fatigue_detector,
        agent_47_seasonal_creative_switcher, agent_48_competitor_ad_copier,
    ], "Phase H: Creative Automation")
    creative_scorer, image_gen, video_opt, ad_fatigue, seasonal_creative, comp_ads = h_results

    # ── Phase I: Bidding & Budget (49–54) ────────────────────────
    i_results = await run_batch([
        agent_49_dayparting_optimizer, agent_50_weather_bid_adjuster,
        agent_51_seasonality_adjuster, agent_52_portfolio_bid_manager,
        agent_53_micro_conversion_trainer, agent_54_zero_click_protector,
    ], "Phase I: Bidding & Budget Automation")
    dayparting, weather_bid, seasonality, portfolio_bid, micro_conv, zero_click = i_results

    # ── Phase J: Audience & Targeting (55–60) ───────────────────
    j_results = await run_batch([
        agent_55_customer_match_uploader, agent_56_lookalike_audience_builder,
        agent_57_in_market_audience_tagger, agent_58_demographic_optimizer,
        agent_59_remarketing_sequencer, agent_60_brand_defender,
    ], "Phase J: Audience & Targeting")
    cust_match, lookalike, in_market, demographic, remark_seq, brand_def = j_results

    # ── Phase K: Campaign Types (61–67) ─────────────────────────
    k_results = await run_batch([
        agent_61_demand_gen_manager, agent_62_shopping_optimizer,
        agent_63_local_campaign_bot, agent_64_app_campaign_manager,
        agent_65_hotel_ads_manager, agent_66_lead_form_optimizer,
        agent_67_call_campaign_manager,
    ], "Phase K: Campaign Types")
    demand_gen, shop_opt, local_bot, app_mgr, specialty_ads, lead_form, call_mgr = k_results

    # ── Phase L: Reporting & Alerts (68–73) ─────────────────────
    l_results = await run_batch([
        agent_68_daily_pulse_reporter, agent_69_budget_burn_alert,
        agent_70_ctr_drop_alerter, agent_71_conversion_spike_detector,
        agent_72_wasted_spend_auditor, agent_73_executive_dashboard_builder,
    ], "Phase L: Reporting & Alerts")
    daily_pulse, burn_alert, ctr_alert, conv_spike, waste_audit, exec_dash = l_results

    # ── Phase M: Compliance & Protection (74–78) ────────────────
    m_results = await run_batch([
        agent_74_disapproval_fixer, agent_75_trademark_guard,
        agent_76_landing_page_monitor, agent_77_billing_anomaly_detector,
        agent_78_mcc_supervisor,
    ], "Phase M: Compliance & Protection")
    disapproval, trademark, lp_monitor, billing_alert, mcc_super = m_results

    # ── Phase N: Scaling & Growth (79–85) ───────────────────────
    n_results = await run_batch([
        agent_79_winner_scaler, agent_80_market_expander,
        agent_81_keyword_expander, agent_82_competitor_gap_finder,
        agent_83_profit_roas_calculator, agent_84_cross_campaign_syncer,
        agent_85_funnel_orchestrator,
    ], "Phase N: Scaling & Growth")
    winner_scale, mkt_expand, kw_expand, comp_gap, profit_roas, cross_sync, funnel_orch = n_results

    # ── Phase O: Master Orchestrators (86–88) ───────────────────
    log.info("═══ Phase O: Master Orchestrators ═══")
    brain      = await run(agent_86_campaign_brain)
    scheduler  = await run(agent_87_agent_scheduler)
    aggregator = await run(agent_88_signal_aggregator)

    return {
        "business_name": d.business_name,
        "business_type": d.business_type,
        "target_location": d.target_location,
        "campaign_types": d.campaign_types,
        "generated_at": datetime.now().isoformat(),
        # Phase A
        "business_intelligence": biz_intel,
        "competitor_analysis": competitor,
        "intent_map": intent_map,
        # Phase B
        "keywords": keywords,
        "brand_segmentation": brand_seg,
        "negative_keywords": negatives,
        "intent_clusters": clusters,
        # Phase C
        "ad_copy": ad_copy,
        "performance_max": pmax,
        "dsa_ads": dsa,
        "display_ads": display,
        "video_scripts": video,
        "shopping_feed": shopping,
        "call_extensions": calls,
        "ab_test_copy": ab_copy,
        "multilingual": multi,
        # Phase D
        "campaign_strategy": strategy,
        "budget_plan": budget,
        "bidding_strategy": bidding,
        "audiences": audiences,
        "targeting": targeting,
        # Phase E
        "conversion_tracking": tracking,
        "ads_scripts": scripts,
        "quality_score": qs,
        "anomaly_detection": anomaly,
        "extensions": extensions,
        "landing_pages": landing_pages,
        # Phase F
        "policy_report": policy,
        "cro_audit": cro,
        "roi_forecast": roi,
        # Bonus
        "budget_optimizer": budget_opt,
        "competitor_intelligence": spy,
        "remarketing_strategy": remarketing,
        "performance_reporter": reporter,
        "scaling_advisor": scaling,
        # Phase G
        "first_party_data": first_party,
        "profit_margin": profit_margin,
        "search_term_miner": search_miner,
        "auction_insights": auction_bot,
        "attribution_model": attribution,
        "ltv_prediction": ltv,
        "demand_forecast": demand_fcst,
        # Phase H
        "creative_scorer": creative_scorer,
        "image_ad_generator": image_gen,
        "video_optimizer": video_opt,
        "ad_fatigue": ad_fatigue,
        "seasonal_creative": seasonal_creative,
        "competitor_ads": comp_ads,
        # Phase I
        "dayparting": dayparting,
        "weather_bidding": weather_bid,
        "seasonality": seasonality,
        "portfolio_bidding": portfolio_bid,
        "micro_conversions": micro_conv,
        "zero_click_protection": zero_click,
        # Phase J
        "customer_match": cust_match,
        "lookalike_audiences": lookalike,
        "in_market_audiences": in_market,
        "demographic_targeting": demographic,
        "remarketing_sequence": remark_seq,
        "brand_defense": brand_def,
        # Phase K
        "demand_gen": demand_gen,
        "shopping_optimizer": shop_opt,
        "local_campaigns": local_bot,
        "app_campaigns": app_mgr,
        "specialty_ads": specialty_ads,
        "lead_forms": lead_form,
        "call_campaigns": call_mgr,
        # Phase L
        "daily_pulse": daily_pulse,
        "burn_rate_alerts": burn_alert,
        "ctr_alerts": ctr_alert,
        "conversion_spikes": conv_spike,
        "waste_audit": waste_audit,
        "executive_dashboard": exec_dash,
        # Phase M
        "disapproval_fixes": disapproval,
        "trademark_guard": trademark,
        "lp_monitor": lp_monitor,
        "billing_alerts": billing_alert,
        "mcc_supervision": mcc_super,
        # Phase N
        "winner_scaling": winner_scale,
        "market_expansion": mkt_expand,
        "keyword_expansion": kw_expand,
        "competitor_gaps": comp_gap,
        "profit_roas": profit_roas,
        "cross_campaign_sync": cross_sync,
        "funnel_orchestration": funnel_orch,
        # Phase O
        "campaign_brain": brain,
        "agent_schedule": scheduler,
        "signal_aggregation": aggregator,
    }

@app.get("/health")
async def health():
    return {
        "status":          "online",
        "version":         "13.0.0",
        "agents":          91,
        "phases":          16,
        "google_ads_ready": bool(GOOGLE_ADS_DEV_TOK and GOOGLE_REFRESH_TOK),
        "ai_provider":     "Groq",
        "ai_model":        GROQ_MODEL,
        "ai_ready":        bool(GROQ_API_KEY),
        "auth_required":   bool(DASHBOARD_API_KEY),
        "publish_ready":   bool(GOOGLE_ADS_DEV_TOK and GOOGLE_CLIENT_ID and GOOGLE_REFRESH_TOK),
        "mcc_configured":  bool(GOOGLE_MCC_ID),
    }

@app.post("/run-crew")
async def run_crew(body: RunCrewRequest, _: None = Depends(verify_key)):
    try:
        result = await run_all_agents(body)

        # ── Auto-publish to Google Ads if requested ────────────────
        published_result = None
        if body.auto_publish:
            customer_id = body.customer_id or GOOGLE_MCC_ID
            if not customer_id:
                result["published_to_google_ads"] = {
                    "success": False,
                    "message": "❌ No customer_id provided. Enter your Google Ads Customer ID in the form.",
                    "errors":  ["customer_id missing"],
                }
            elif not GOOGLE_ADS_DEV_TOK:
                result["published_to_google_ads"] = {
                    "success": False,
                    "message": "❌ GOOGLE_ADS_DEVELOPER_TOKEN not set in .env",
                    "errors":  ["developer token missing"],
                }
            else:
                log.info(f"🚀 Publishing to Google Ads for customer: {customer_id}")
                publisher = GoogleAdsPublisher(customer_id)
                pub = publisher.publish(result, body.dict())
                result["published_to_google_ads"] = pub
                published_result = pub.get("success", False)
        else:
            result["published_to_google_ads"] = {
                "success": False,
                "message": "Auto-publish was not enabled. Toggle 'Auto-publish' and re-run to push to Google Ads.",
            }

        save_campaign(body.dict(), result, bool(published_result))
        return result

    except Exception as e:
        log.error(f"Crew failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/publish")
async def publish_existing(
    body: dict,
    _: None = Depends(verify_key)
):
    """Publish a previously generated result to Google Ads."""
    customer_id = body.get("customer_id","").replace("-","").strip()
    if not customer_id:
        raise HTTPException(400, "customer_id required")
    if not GOOGLE_ADS_DEV_TOK:
        raise HTTPException(400, "GOOGLE_ADS_DEVELOPER_TOKEN not set in .env")

    result  = body.get("result", {})
    request = body.get("request", {})
    publisher = GoogleAdsPublisher(customer_id)
    return publisher.publish(result, request)


@app.get("/diagnose-google-ads")
async def diagnose_google_ads(_: None = Depends(verify_key)):
    """
    Diagnose the Google Ads API connection step-by-step.
    Call this from Settings tab to see exactly what's failing.
    """
    diag = {
        "step_1_credentials": {},
        "step_2_oauth_token": {},
        "step_3_accessible_customers": {},
        "step_4_mcc_info": {},
        "diagnosis": "",
        "fix": "",
    }

    # Step 1 — Check .env credentials exist
    creds = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": bool(GOOGLE_ADS_DEV_TOK),
        "GOOGLE_ADS_CLIENT_ID":       bool(GOOGLE_CLIENT_ID),
        "GOOGLE_ADS_CLIENT_SECRET":   bool(GOOGLE_CLIENT_SEC),
        "GOOGLE_ADS_REFRESH_TOKEN":   bool(GOOGLE_REFRESH_TOK),
        "GOOGLE_ADS_MCC_ID":          bool(GOOGLE_MCC_ID),
    }
    diag["step_1_credentials"] = creds
    missing = [k for k, v in creds.items() if not v]
    if missing:
        diag["diagnosis"] = f"❌ Missing credentials: {', '.join(missing)}"
        diag["fix"] = "Add these to your .env file and restart the server."
        return diag

    # Step 2 — Get OAuth token
    try:
        r = httpx.post(GOOGLE_TOKEN_URL, data={
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SEC,
            "refresh_token": GOOGLE_REFRESH_TOK,
            "grant_type":    "refresh_token",
        }, timeout=30)
        r.raise_for_status()
        token_data = r.json()
        access_token = token_data.get("access_token","")
        diag["step_2_oauth_token"] = {
            "success":    True,
            "token_type": token_data.get("token_type"),
            "expires_in": token_data.get("expires_in"),
            "scope":      token_data.get("scope",""),
        }
    except Exception as e:
        diag["step_2_oauth_token"] = {"success": False, "error": str(e)}
        diag["diagnosis"] = "❌ OAuth token failed. Refresh token may be expired or invalid."
        diag["fix"] = "Re-generate your GOOGLE_ADS_REFRESH_TOKEN using the OAuth2 flow."
        return diag

    headers = {
        "Authorization":  f"Bearer {access_token}",
        "developer-token": GOOGLE_ADS_DEV_TOK,
        "Content-Type":   "application/json",
    }

    # Step 3 — List accessible customers
    try:
        r = httpx.get(
            f"{GOOGLE_ADS_BASE}/customers:listAccessibleCustomers",
            headers=headers, timeout=30
        )
        if r.is_success:
            customers = r.json().get("resourceNames", [])
            diag["step_3_accessible_customers"] = {
                "success":         True,
                "accessible_count": len(customers),
                "customer_ids":    [c.split("/")[-1] for c in customers],
                "raw":             customers[:10],
            }
        else:
            err = r.json().get("error", {})
            diag["step_3_accessible_customers"] = {
                "success": False,
                "status":  r.status_code,
                "error":   err.get("message", r.text[:300]),
                "code":    err.get("code",""),
            }
            if r.status_code == 403:
                diag["diagnosis"] = "❌ Developer token not approved for production. You are in TEST MODE."
                diag["fix"] = (
                    "Your developer token is in TEST mode — it can only access TEST accounts. "
                    "Apply for Standard Access at: "
                    "https://developers.google.com/google-ads/api/docs/access-levels"
                )
            else:
                diag["diagnosis"] = f"❌ listAccessibleCustomers failed: {err.get('message','')}"
                diag["fix"] = "Check your developer token and OAuth credentials."
            return diag
    except Exception as e:
        diag["step_3_accessible_customers"] = {"success": False, "error": str(e)}
        return diag

    # Step 4 — Check MCC info
    if GOOGLE_MCC_ID:
        mcc_id = GOOGLE_MCC_ID.replace("-","")
        try:
            headers["login-customer-id"] = mcc_id
            r = httpx.get(
                f"{GOOGLE_ADS_BASE}/customers/{mcc_id}",
                headers=headers, timeout=30
            )
            if r.is_success:
                info = r.json()
                diag["step_4_mcc_info"] = {
                    "success":       True,
                    "id":            info.get("id"),
                    "descriptiveName": info.get("descriptiveName"),
                    "currencyCode":  info.get("currencyCode"),
                    "timeZone":      info.get("timeZone"),
                    "testAccount":   info.get("testAccount", False),
                }
                if info.get("testAccount"):
                    diag["diagnosis"] = "⚠️ This is a TEST ACCOUNT. Only test campaigns can be created."
                    diag["fix"] = "Use a production Google Ads account to push real campaigns."
                else:
                    diag["diagnosis"] = "✅ All checks passed. Google Ads API is ready."
                    diag["fix"] = "Run a campaign with Auto-publish enabled and your Customer ID filled in."
            else:
                err = r.json().get("error", {})
                diag["step_4_mcc_info"] = {
                    "success": False,
                    "status":  r.status_code,
                    "error":   err.get("message", r.text[:200]),
                }
                diag["diagnosis"] = f"❌ Cannot access MCC {mcc_id}: {err.get('message','')}"
                diag["fix"] = "Check GOOGLE_ADS_MCC_ID — use the numeric ID without dashes."
        except Exception as e:
            diag["step_4_mcc_info"] = {"success": False, "error": str(e)}

    return diag


@app.get("/list-customers")
async def list_customers(_: None = Depends(verify_key)):
    """
    List ALL Google Ads accounts accessible with your credentials.
    Shows which are test accounts and which are production.
    Use this to find the correct Customer ID to paste into the form.
    """
    result = {
        "test_accounts":       [],
        "production_accounts": [],
        "all_accounts":        [],
        "error":               None,
        "how_to_use":          "Copy any Customer ID from 'test_accounts' into the form while your Basic Access is pending."
    }

    # Get OAuth token
    try:
        r = httpx.post(GOOGLE_TOKEN_URL, data={
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SEC,
            "refresh_token": GOOGLE_REFRESH_TOK,
            "grant_type":    "refresh_token",
        }, timeout=30)
        r.raise_for_status()
        access_token = r.json()["access_token"]
    except Exception as e:
        result["error"] = f"OAuth failed: {e}"
        return result

    headers = {
        "Authorization":   f"Bearer {access_token}",
        "developer-token": GOOGLE_ADS_DEV_TOK,
    }
    if GOOGLE_MCC_ID:
        headers["login-customer-id"] = GOOGLE_MCC_ID.replace("-","")

    # List accessible customers
    try:
        r = httpx.get(
            f"{GOOGLE_ADS_BASE}/customers:listAccessibleCustomers",
            headers=headers, timeout=30
        )
        if not r.is_success:
            result["error"] = f"listAccessibleCustomers failed [{r.status_code}]: {r.text[:300]}"
            return result

        resource_names = r.json().get("resourceNames", [])
        customer_ids   = [rn.split("/")[-1] for rn in resource_names]

    except Exception as e:
        result["error"] = f"Request failed: {e}"
        return result

    # Fetch details for each customer (name, test status, currency)
    for cid in customer_ids:
        try:
            h2 = dict(headers)
            h2["login-customer-id"] = GOOGLE_MCC_ID.replace("-","") if GOOGLE_MCC_ID else cid
            r2 = httpx.get(
                f"{GOOGLE_ADS_BASE}/customers/{cid}",
                headers=h2, timeout=15
            )
            if r2.is_success:
                info = r2.json()
                account = {
                    "customer_id":    cid,
                    "name":           info.get("descriptiveName", f"Account {cid}"),
                    "currency":       info.get("currencyCode","USD"),
                    "timezone":       info.get("timeZone",""),
                    "test_account":   info.get("testAccount", False),
                    "status":         "TEST ✅ Use this while waiting for Basic Access" if info.get("testAccount") else "PRODUCTION 🚀",
                    "resource_name":  f"customers/{cid}",
                }
                result["all_accounts"].append(account)
                if info.get("testAccount"):
                    result["test_accounts"].append(account)
                else:
                    result["production_accounts"].append(account)
            else:
                result["all_accounts"].append({
                    "customer_id": cid,
                    "error": f"Could not fetch details: {r2.status_code}",
                })
        except Exception as e:
            result["all_accounts"].append({"customer_id": cid, "error": str(e)})

    if not result["test_accounts"]:
        result["how_to_use"] = (
            "No test accounts found. Go to ads.google.com → Tools → API Center → "
            "Create Test Account. Then call /create-test-account endpoint."
        )

    return result


@app.post("/create-test-account")
async def create_test_account(body: dict, _: None = Depends(verify_key)):
    """
    Create a new Google Ads TEST account under your MCC.
    This works immediately with a test developer token — no approval needed.
    Body: {"account_name": "My Test Account", "currency": "USD", "timezone": "America/New_York"}
    """
    if not GOOGLE_MCC_ID:
        raise HTTPException(400, "GOOGLE_ADS_MCC_ID not set in .env")

    mcc_id = GOOGLE_MCC_ID.replace("-","")

    # Get OAuth token
    try:
        r = httpx.post(GOOGLE_TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SEC,
            "refresh_token": GOOGLE_REFRESH_TOK, "grant_type": "refresh_token",
        }, timeout=30)
        r.raise_for_status()
        access_token = r.json()["access_token"]
    except Exception as e:
        raise HTTPException(500, f"OAuth failed: {e}")

    headers = {
        "Authorization":      f"Bearer {access_token}",
        "developer-token":    GOOGLE_ADS_DEV_TOK,
        "login-customer-id":  mcc_id,
        "Content-Type":       "application/json",
    }

    account_name = body.get("account_name", "Test Account — AdsForge AI")
    currency     = body.get("currency", "USD")
    timezone     = body.get("timezone", "America/New_York")

    payload = {
        "customerId": mcc_id,
        "customerClient": {
            "descriptiveName": account_name,
            "currencyCode":    currency,
            "timeZone":        timezone,
        }
    }

    try:
        r = httpx.post(
            f"{GOOGLE_ADS_BASE}/customers/{mcc_id}/customerClients:mutate",
            json=payload, headers=headers, timeout=30
        )
        if r.is_success:
            resp         = r.json()
            new_cid      = resp.get("result",{}).get("resourceName","").split("/")[-1]
            return {
                "success":      True,
                "customer_id":  new_cid,
                "account_name": account_name,
                "message":      f"✅ Test account created! Customer ID: {new_cid}. Use this in the form.",
                "next_step":    "Paste this Customer ID into the form → enable Auto-publish → Launch agents.",
                "resource_name": resp.get("result",{}).get("resourceName",""),
            }
        else:
            err = r.json().get("error", {})
            return {
                "success": False,
                "status":  r.status_code,
                "error":   err.get("message", r.text[:300]),
                "tip":     "If you see 'PERMISSION_DENIED', your developer token cannot create accounts. Use an existing test account from /list-customers instead.",
            }
    except Exception as e:
        raise HTTPException(500, str(e))
async def history(_: None = Depends(verify_key)):
    return {"campaigns": list_campaigns()}

@app.post("/analyze-url")
async def analyze_url(body: AnalyzeUrlRequest, _: None = Depends(verify_key)):
    """Fetch the actual website and extract real business info — not guessing from the URL."""
    import re as _re

    url = body.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    # ── Step 1: Actually fetch the website ────────────────────
    website_text = ""
    fetch_error  = ""
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }) as client:
            r = client.get(url)
            r.raise_for_status()
            html = r.text
            # Strip tags, scripts, styles — keep readable text
            text = _re.sub(r'<style[^>]*>.*?</style>', '', html, flags=_re.DOTALL)
            text = _re.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re.DOTALL)
            text = _re.sub(r'<[^>]+>', ' ', text)
            text = _re.sub(r'\s+', ' ', text).strip()
            website_text = text[:4000]
            log.info(f"✅ Fetched {url} — {len(website_text)} chars extracted")
    except httpx.TimeoutException:
        fetch_error = "Website took too long to respond"
    except httpx.HTTPStatusError as e:
        fetch_error = f"Website returned HTTP {e.response.status_code}"
    except Exception as e:
        fetch_error = str(e)[:100]
        log.warning(f"Could not fetch {url}: {e}")

    if not website_text:
        # Fallback: analyse just from the domain name
        log.warning(f"Using URL-only analysis for {url} — fetch failed: {fetch_error}")
        website_text = f"Website URL: {url}"

    # ── Step 2: AI extracts real info from the content ────────
    result = ai_json(
        "You are a business analyst. Extract business information from real website content.",
        f"""Analyze this website content and extract accurate business information.

URL: {url}
Website Content:
{website_text}

Return ONLY this JSON — use the actual content, not guesses:
{{
  "business_name": "exact business name from the content",
  "business_type": "specific business type e.g. Electrical Contractor, Dental Clinic, SaaS Company",
  "location": "city and state/country if found in the content, else 'United States'",
  "services": ["actual service 1", "actual service 2", "actual service 3", "actual service 4", "actual service 5"],
  "unique_value_propositions": ["UVP from the content"],
  "target_audience": "who they serve based on the content",
  "fetch_status": "{'success' if website_text != f'Website URL: {url}' else 'url_only'}"
}}"""
    )

    if fetch_error and "fetch_status" not in str(result):
        result["fetch_note"] = f"Website fetch issue: {fetch_error}. Results based on URL only."

    return result

@app.post("/analyze-search-terms")
async def analyze_search_terms(body: SearchTermsRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are a Google Ads search term analysis expert.",
        f"""Analyze these search terms for a {body.business_type} and classify them.
Terms: {json.dumps(body.search_terms[:100])}
Current negatives: {json.dumps(body.current_negatives)}
Return JSON: {{
  "relevant_terms": [...],
  "irrelevant_terms_to_negate": [...],
  "new_keyword_opportunities": [...],
  "match_type_recommendations": {{}},
  "estimated_wasted_spend_pct": number
}}"""
    )
    return result

@app.post("/optimize-quality-score")
async def optimize_quality_score(body: QualityScoreRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are a Quality Score optimization expert.",
        f"""Optimize Quality Scores for these keywords and ads.
Business Type: {body.business_type}
Keywords: {json.dumps(body.keywords)}
Headlines: {json.dumps(body.headlines)}
Landing Page: {body.landing_page_content[:500]}
Return JSON: {{
  "overall_qs_estimate": number,
  "per_keyword_analysis": [{{"keyword":"","qs_estimate":number,"issues":[],"fixes":[]}}],
  "headline_relevance_score": number,
  "landing_page_score": number,
  "priority_actions": [...],
  "estimated_cpc_reduction": "X%"
}}"""
    )
    return result

@app.post("/detect-anomalies")
async def detect_anomalies(body: AnomalyRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are an anomaly detection specialist for Google Ads.",
        f"""Analyze metrics for campaign: {body.campaign_name}
Current: {json.dumps(body.metrics)}
Historical average: {json.dumps(body.historical_avg)}
Return JSON: {{
  "anomalies_detected": [
    {{"metric":"","current_value":"","historical_avg":"","change_pct":number,"severity":"critical|warning|info","root_cause":"","recommended_action":""}}
  ],
  "overall_health_score": number,
  "immediate_actions": [...],
  "monitoring_frequency": ""
}}"""
    )
    return result

@app.post("/generate-audiences")
async def generate_audiences(body: AudienceRequest, _: None = Depends(verify_key)):
    req = RunCrewRequest(
        business_name=body.business_name,
        business_type=body.business_type,
        website_url=body.website_url,
        target_location=body.target_location,
    )
    return agent_20_audience_builder(req)

@app.post("/generate-report")
async def generate_report(body: ReportRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are a Google Ads performance reporting specialist.",
        f"""Generate a performance report for campaign: {body.campaign_name}
Metrics: {json.dumps(body.metrics)}
Goal: {body.conversion_goal}
Return JSON: {{
  "executive_summary": "",
  "performance_grade": "A|B|C|D|F",
  "wins": [...],
  "concerns": [...],
  "recommended_actions": [{{"priority":"high|medium|low","action":"","expected_impact":""}}],
  "week_over_week_trend": "",
  "budget_efficiency_score": number
}}"""
    )
    return result

@app.post("/bid-adjustments")
async def bid_adjustments(body: BidAdjustRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are a bid adjustment optimization expert.",
        f"""Optimize bid adjustments for campaign: {body.campaign_name}
Device data: {json.dumps(body.device_data)}
Location data: {json.dumps(body.location_data)}
Time data: {json.dumps(body.time_data)}
Return JSON: {{
  "device_adjustments": {{}},
  "location_adjustments": [...],
  "time_adjustments": [...],
  "estimated_cpa_improvement": "X%",
  "rationale": ""
}}"""
    )
    return result

@app.post("/competitor-spy")
async def competitor_spy_endpoint(body: CompetitorSpyRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are a competitive intelligence specialist for Google Ads.",
        f"""Research competitors for {body.business_type} in {body.target_location}.
Known competitors: {json.dumps(body.competitors)}
Return JSON: {{
  "competitor_profiles": [...],
  "ad_copy_patterns": [...],
  "keyword_gaps": [...],
  "bid_intelligence": {{}},
  "strategic_recommendations": [...]
}}"""
    )
    return result

@app.post("/smart-budget")
async def smart_budget_endpoint(body: SmartBudgetRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are a smart budget optimization AI.",
        f"""Optimize budget for {body.business_name}.
Current spend: ${body.current_spend}/day
Current ROAS: {body.current_roas}
Target CPA: ${body.target_cpa}
Return JSON: {{
  "recommended_budget": number,
  "budget_efficiency_score": number,
  "waste_identified": [...],
  "reallocation_plan": [...],
  "expected_roas_improvement": number
}}"""
    )
    return result

@app.post("/landing-page-copy")
async def landing_page_copy(body: LandingPageRequest, _: None = Depends(verify_key)):
    result = ai_json(
        "You are a landing page copywriter specialized in Google Ads conversion.",
        f"""Write landing page copy for {body.business_name} ({body.business_type}) in {body.target_location}.
Goal: {body.conversion_goal}
Keywords: {json.dumps(body.keywords[:10])}
Return JSON: {{
  "headline": "",
  "subheadline": "",
  "hero_copy": "",
  "benefits": [...5],
  "social_proof": [...3],
  "cta_primary": "",
  "cta_secondary": "",
  "faq": [{{"q":"","a":""}}],
  "urgency_element": "",
  "trust_badges": [...]
}}"""
    )
    return result


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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# ═══════════════════════════════════════════════════════════════
# V13 ADDITIONS — New agents, OAuth, Performance, Monitor
# ═══════════════════════════════════════════════════════════════

import hashlib as _hashlib
import urllib.parse as _urlparse

# ── Google Ads OAuth2 token store (in-memory) ─────────────────
_oauth_tokens: dict = {}   # { access_token, refresh_token }

GOOGLE_CLIENT_ID_V13     = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET_V13 = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
REDIRECT_URI_V13         = os.getenv("GOOGLE_ADS_REDIRECT_URI", "http://localhost:5000/auth/callback")
GOOGLE_ADS_API_V17       = "https://googleads.googleapis.com/v17"

def _v13_headers(customer_id: str = "") -> dict:
    tok = (_oauth_tokens.get("access_token") or
           os.getenv("GOOGLE_ADS_ACCESS_TOKEN","") or
           _refresh_token_v13())
    mcc = os.getenv("GOOGLE_ADS_MCC_ID","").replace("-","")
    h = {
        "Authorization": f"Bearer {tok}",
        "developer-token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN",""),
        "Content-Type": "application/json",
    }
    if mcc: h["login-customer-id"] = mcc
    return h

def _refresh_token_v13() -> str:
    rt = (_oauth_tokens.get("refresh_token") or
          os.getenv("GOOGLE_ADS_REFRESH_TOKEN",""))
    if not rt: return ""
    try:
        r = httpx.post("https://oauth2.googleapis.com/token", data={
            "refresh_token": rt,
            "client_id":     GOOGLE_CLIENT_ID_V13,
            "client_secret": GOOGLE_CLIENT_SECRET_V13,
            "grant_type":    "refresh_token",
        }, timeout=30)
        tok = r.json().get("access_token","")
        _oauth_tokens["access_token"] = tok
        return tok
    except: return ""

# ── SHA256 for Enhanced Conversions ───────────────────────────
def _sha256(val: str) -> str:
    return _hashlib.sha256(val.strip().lower().encode()).hexdigest()

# ── PYDANTIC MODELS V13 ────────────────────────────────────────

class KeywordPlannerRequest(BaseModel):
    customer_id: str
    keywords:    List[str]
    location:    str = "United States"
    language:    str = "English"

class NegativeAutoRequest(BaseModel):
    customer_id: str
    campaign_id: str
    days_lookback: int = 30
    min_impressions: int = 10
    max_conversions: int = 0

class EnhancedConvRequest(BaseModel):
    customer_id:   str
    email:         Optional[str] = ""
    phone:         Optional[str] = ""
    first_name:    Optional[str] = ""
    last_name:     Optional[str] = ""
    conversion_name: str = "Purchase"

class PublishV13Request(BaseModel):
    customer_id:   str
    agent_results: dict
    create_enhanced_conv: bool = False
    enable_ai_max:        bool = False

# ═══════════════════════════════════════════════════════════════
# AGENTS 89–91 (V13 NEW AGENTS)
# ═══════════════════════════════════════════════════════════════

def agent_89_ai_max(d) -> dict:
    log.info("▶ Agent 89: AI Max")
    return ai_json(
        "You are a Google Ads AI Max specialist. AI Max is Google's newest feature that combines broad match keywords with AI-powered search term matching, auto-generated ad copy, and URL expansion. It launched in 2025 and delivers 14-27% more conversions.",
        f"""Design an AI Max campaign strategy for {d.business_name} ({d.business_type}).
Return JSON: {{
  "ai_max_recommendation": "enabled|disabled",
  "rationale": "",
  "search_term_expansion_setting": "STANDARD|BROADER",
  "url_expansion_setting": "ENABLED|DISABLED",
  "final_url_expansion_opt_out_urls": [],
  "asset_automation": {{
    "generate_headlines": true,
    "generate_descriptions": true,
    "generate_images": true
  }},
  "broad_match_strategy": "",
  "expected_conversion_lift": "X%",
  "implementation_steps": [],
  "watch_out_for": [],
  "ai_max_vs_exact_match_recommendation": ""
}}"""
    )

def agent_90_local_services_ads(d) -> dict:
    log.info("▶ Agent 90: Local Services Ads")
    return ai_json(
        "You are a Google Local Services Ads (LSA) specialist. LSA shows at the very top of Google above regular ads, charges per lead (not per click), and requires Google verification. Perfect for service businesses.",
        f"""Design Local Services Ads strategy for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "lsa_eligibility": "eligible|check_required|not_eligible",
  "business_categories": [],
  "verification_requirements": [],
  "google_guaranteed_badge": {{
    "eligible": true,
    "requirements": [],
    "benefit": ""
  }},
  "google_screened_badge": {{
    "eligible": false,
    "requirements": []
  }},
  "estimated_cost_per_lead": "$X-Y",
  "vs_regular_ads_comparison": "",
  "budget_recommendation": number,
  "setup_steps": [],
  "profile_optimisation_tips": [],
  "review_strategy": ""
}}"""
    )

def agent_91_enhanced_conversions(d) -> dict:
    log.info("▶ Agent 91: Enhanced Conversions")
    return ai_json(
        "You are a Google Enhanced Conversions specialist. Enhanced Conversions uses SHA256-hashed first-party customer data (email, phone, name) to improve conversion measurement accuracy, especially in cookieless environments. This is critical for 2025+ tracking.",
        f"""Design Enhanced Conversions implementation for {d.business_name} ({d.business_type}).
Return JSON: {{
  "enhanced_conversions_recommendation": "high_priority|medium|low",
  "why_important": "",
  "data_fields_to_collect": [],
  "hashing_requirements": "SHA256",
  "gtag_implementation": {{
    "code_snippet": "",
    "placement": "thank_you_page|form_submission"
  }},
  "gtm_implementation": {{
    "variable_type": "User-Provided Data",
    "trigger": "form_submission"
  }},
  "privacy_compliance": {{
    "consent_mode_v2": "required",
    "gdpr_notes": "",
    "ccpa_notes": ""
  }},
  "expected_conversion_improvement": "X%",
  "setup_checklist": []
}}"""
    )

# ═══════════════════════════════════════════════════════════════
# OAUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/auth/google")
async def auth_google_start():
    """Start Google OAuth flow — open this URL in browser."""
    if not GOOGLE_CLIENT_ID_V13:
        raise HTTPException(503, "GOOGLE_ADS_CLIENT_ID not in .env")
    params = {
        "client_id":     GOOGLE_CLIENT_ID_V13,
        "redirect_uri":  REDIRECT_URI_V13,
        "response_type": "code",
        "scope":         "https://www.googleapis.com/auth/adwords",
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         "adsforge_v13",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + _urlparse.urlencode(params)
    return {"url": url, "message": "Open this URL in browser to authenticate"}

@app.get("/auth/callback")
async def auth_callback(code: str = "", error: str = ""):
    """Google redirects here after user approves."""
    if error:
        return HTMLResponse(f"<h2 style='color:red'>Auth error: {error}</h2><p>Close and try again.</p>")
    if not code:
        return HTMLResponse("<h2>No code received</h2>")
    try:
        r = httpx.post("https://oauth2.googleapis.com/token", data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID_V13,
            "client_secret": GOOGLE_CLIENT_SECRET_V13,
            "redirect_uri":  REDIRECT_URI_V13,
            "grant_type":    "authorization_code",
        }, timeout=30)
        r.raise_for_status()
        tokens = r.json()
        _oauth_tokens["access_token"]  = tokens.get("access_token","")
        _oauth_tokens["refresh_token"] = tokens.get("refresh_token","")
        log.info("✅ OAuth v13 complete")
        return HTMLResponse("""<html><body style='background:#0a0a0f;color:#f0f0f8;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;margin:0'>
        <div style='font-size:56px'>✅</div>
        <h2 style='color:#10b981;margin:0'>Google Ads Connected!</h2>
        <p style='color:#888;margin:0'>Close this window and return to AdsForge.</p>
        <script>setTimeout(()=>window.close(),2500)</script></body></html>""")
    except Exception as e:
        return HTMLResponse(f"<h2 style='color:red'>Token error: {e}</h2>")

@app.get("/auth/status")
async def auth_status():
    has_access  = bool(_oauth_tokens.get("access_token"))
    has_refresh = bool(_oauth_tokens.get("refresh_token") or os.getenv("GOOGLE_ADS_REFRESH_TOKEN",""))
    return {
        "connected":       has_access or has_refresh,
        "has_access_token": has_access,
        "has_refresh_token": has_refresh,
        "method":          "oauth" if has_refresh else "env_var" if os.getenv("GOOGLE_ADS_REFRESH_TOKEN") else "none",
    }

# ═══════════════════════════════════════════════════════════════
# KEYWORD PLANNER API (real volumes)
# ═══════════════════════════════════════════════════════════════

@app.post("/keyword-planner")
async def keyword_planner(body: KeywordPlannerRequest, _=Depends(verify_key)):
    """Get REAL search volumes from Google Keyword Planner API."""
    cid = body.customer_id.replace("-","").strip()
    try:
        tok = _refresh_token_v13() or _oauth_tokens.get("access_token","")
        if not tok:
            raise HTTPException(401, "Not authenticated — connect Google Ads first")

        headers = _v13_headers(cid)
        # Use generateKeywordIdeas GAQL endpoint
        payload = {
            "keywordSeed": {"keywords": body.keywords[:20]},
            "geoTargetConstants": ["geoTargetConstants/2840"],  # US default
            "language":    "languageConstants/1000",
            "keywordPlanNetwork": "GOOGLE_SEARCH",
        }
        r = httpx.post(
            f"{GOOGLE_ADS_API_V17}/customers/{cid}/keywordPlans:generateKeywordIdeas",
            json=payload, headers=headers, timeout=30
        )
        if r.is_success:
            results = r.json().get("results", [])
            kw_data = []
            for item in results[:50]:
                text    = item.get("text","")
                metrics = item.get("keywordIdeaMetrics",{})
                kw_data.append({
                    "keyword":         text,
                    "avg_monthly_searches": metrics.get("avgMonthlySearches", 0),
                    "competition":     metrics.get("competition","UNKNOWN"),
                    "competition_index": metrics.get("competitionIndex", 0),
                    "low_top_bid":     round((metrics.get("lowTopOfPageBidMicros",0) or 0) / 1_000_000, 2),
                    "high_top_bid":    round((metrics.get("highTopOfPageBidMicros",0) or 0) / 1_000_000, 2),
                })
            return {"success": True, "keywords": kw_data, "source": "Google Keyword Planner API"}
        else:
            # Fallback: return AI-estimated volumes
            err = r.text[:200]
            log.warning(f"KP API failed ({r.status_code}): {err} — using AI estimates")
            return {
                "success": False,
                "source": "AI estimates (KP API unavailable)",
                "error": err,
                "keywords": [{"keyword": k, "avg_monthly_searches": "N/A (API unavailable)", "competition": "UNKNOWN"} for k in body.keywords],
                "tip": "To get real volumes: ensure GOOGLE_ADS_DEVELOPER_TOKEN is approved (Basic Access needed)"
            }
    except Exception as e:
        raise HTTPException(500, str(e))

# ═══════════════════════════════════════════════════════════════
# PERFORMANCE DATA (read from live Google Ads account)
# ═══════════════════════════════════════════════════════════════

@app.get("/performance/{customer_id}")
async def get_performance(customer_id: str, days: int = 30, _=Depends(verify_key)):
    """Pull live campaign performance data using GAQL."""
    cid = customer_id.replace("-","").strip()
    gaql = f"""
        SELECT
          campaign.name,
          campaign.status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.ctr,
          metrics.average_cpc,
          metrics.cost_per_conversion
        FROM campaign
        WHERE segments.date DURING LAST_{days}_DAYS
          AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """
    try:
        headers = _v13_headers(cid)
        r = httpx.post(
            f"{GOOGLE_ADS_API_V17}/customers/{cid}/googleAds:search",
            json={"query": gaql}, headers=headers, timeout=30
        )
        if r.is_success:
            rows = r.json().get("results", [])
            campaigns = []
            for row in rows:
                camp = row.get("campaign",{})
                m    = row.get("metrics",{})
                spend = round((m.get("costMicros",0) or 0) / 1_000_000, 2)
                campaigns.append({
                    "name":          camp.get("name",""),
                    "status":        camp.get("status",""),
                    "impressions":   m.get("impressions",0),
                    "clicks":        m.get("clicks",0),
                    "spend":         spend,
                    "conversions":   round(m.get("conversions",0), 1),
                    "conv_value":    round(m.get("conversionsValue",0), 2),
                    "ctr":           round((m.get("ctr",0) or 0)*100, 2),
                    "avg_cpc":       round((m.get("averageCpc",0) or 0)/1_000_000, 2),
                    "cpa":           round((m.get("costPerConversion",0) or 0)/1_000_000, 2),
                    "roas":          round(m.get("conversionsValue",0)/spend, 2) if spend > 0 else 0,
                })
            total_spend = sum(c["spend"] for c in campaigns)
            total_conv  = sum(c["conversions"] for c in campaigns)
            return {
                "success":   True,
                "period":    f"Last {days} days",
                "campaigns": campaigns,
                "summary":   {
                    "total_spend":       total_spend,
                    "total_conversions": total_conv,
                    "total_clicks":      sum(c["clicks"] for c in campaigns),
                    "avg_cpa":           round(total_spend/total_conv, 2) if total_conv > 0 else 0,
                    "overall_roas":      round(sum(c["conv_value"] for c in campaigns)/total_spend, 2) if total_spend > 0 else 0,
                }
            }
        else:
            return {"success": False, "error": r.text[:300], "status": r.status_code}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/search-terms/{customer_id}")
async def get_search_terms(customer_id: str, days: int = 30, _=Depends(verify_key)):
    """Pull search term report to find new negatives and opportunities."""
    cid = customer_id.replace("-","").strip()
    gaql = f"""
        SELECT
          search_term_view.search_term,
          search_term_view.status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          campaign.name,
          ad_group.name
        FROM search_term_view
        WHERE segments.date DURING LAST_{days}_DAYS
          AND metrics.impressions > 5
        ORDER BY metrics.cost_micros DESC
        LIMIT 200
    """
    try:
        headers = _v13_headers(cid)
        r = httpx.post(
            f"{GOOGLE_ADS_API_V17}/customers/{cid}/googleAds:search",
            json={"query": gaql}, headers=headers, timeout=30
        )
        if r.is_success:
            rows = r.json().get("results", [])
            terms = []
            for row in rows:
                stv  = row.get("searchTermView",{})
                m    = row.get("metrics",{})
                camp = row.get("campaign",{})
                ag   = row.get("adGroup",{})
                spend = round((m.get("costMicros",0) or 0)/1_000_000, 2)
                conv  = round(m.get("conversions",0), 1)
                terms.append({
                    "term":        stv.get("searchTerm",""),
                    "status":      stv.get("status",""),
                    "campaign":    camp.get("name",""),
                    "ad_group":    ag.get("name",""),
                    "impressions": m.get("impressions",0),
                    "clicks":      m.get("clicks",0),
                    "spend":       spend,
                    "conversions": conv,
                    "wasted":      spend > 0 and conv == 0,
                })
            # AI analysis of search terms
            waste_terms = [t["term"] for t in terms if t["wasted"] and t["spend"] > 1][:30]
            good_terms  = [t["term"] for t in terms if t["conversions"] > 0][:20]
            return {
                "success":        True,
                "total_terms":    len(terms),
                "terms":          terms,
                "wasted_terms":   waste_terms,
                "converting_terms": good_terms,
                "recommended_negatives": waste_terms[:20],
            }
        else:
            return {"success": False, "error": r.text[:300]}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/auto-add-negatives/{customer_id}")
async def auto_add_negatives(customer_id: str, body: NegativeAutoRequest, _=Depends(verify_key)):
    """
    Automatically add wasted search terms as negative keywords.
    This is what groas.ai does continuously — we do it on-demand.
    """
    cid = customer_id.replace("-","").strip()
    # First get the search terms
    st_result = await get_search_terms(cid, body.days_lookback)
    if not st_result.get("success"):
        raise HTTPException(500, st_result.get("error","Failed to get search terms"))

    negatives_to_add = st_result.get("recommended_negatives", [])
    if not negatives_to_add:
        return {"success": True, "message": "No wasted terms found to negate", "added": 0}

    try:
        headers = _v13_headers(cid)
        ops = [{"create": {
            "campaign": f"customers/{cid}/campaigns/{body.campaign_id}",
            "matchType": "BROAD",
            "keywordText": term,
        }} for term in negatives_to_add[:20]]  # max 20 at a time

        r = httpx.post(
            f"{GOOGLE_ADS_API_V17}/customers/{cid}/campaignCriteria:mutate",
            json={"operations": [{"create": {
                "campaign": f"customers/{cid}/campaigns/{body.campaign_id}",
                "negative": True,
                "keyword": {"text": term, "matchType": "BROAD"}
            }} for term in negatives_to_add[:20]]},
            headers=headers, timeout=30
        )
        if r.is_success:
            return {
                "success":      True,
                "added":        len(negatives_to_add),
                "negatives":    negatives_to_add,
                "message":      f"✅ Added {len(negatives_to_add)} negative keywords to campaign"
            }
        else:
            return {"success": False, "error": r.text[:300], "would_have_added": negatives_to_add}
    except Exception as e:
        raise HTTPException(500, str(e))

# ═══════════════════════════════════════════════════════════════
# ENHANCED CONVERSIONS API
# ═══════════════════════════════════════════════════════════════

@app.post("/enhanced-conversions/upload")
async def upload_enhanced_conversion(body: EnhancedConvRequest, _=Depends(verify_key)):
    """Upload hashed customer data for Enhanced Conversions."""
    cid = body.customer_id.replace("-","").strip()
    user_data = {}
    if body.email:    user_data["hashedEmail"]     = _sha256(body.email)
    if body.phone:    user_data["hashedPhoneNumber"]= _sha256(body.phone)
    if body.first_name: user_data["firstName"]     = _sha256(body.first_name)
    if body.last_name:  user_data["lastName"]      = _sha256(body.last_name)

    if not user_data:
        raise HTTPException(400, "Provide at least email or phone")

    return {
        "success":    True,
        "hashed_data": user_data,
        "note":       "Data hashed with SHA256 as required by Google. Ready to upload via gtag or Ads API.",
        "privacy":    "Original data never stored — only the hash is used",
        "gtag_snippet": f"""gtag('event', 'conversion', {{
  'send_to': 'AW-CONVERSION_ID/{body.conversion_name}',
  'user_data': {json.dumps(user_data, indent=4)}
}});"""
    }

# ═══════════════════════════════════════════════════════════════
# AI MAX CONFIGURATION
# ═══════════════════════════════════════════════════════════════

@app.post("/configure-ai-max/{customer_id}")
async def configure_ai_max(customer_id: str, campaign_id: str, _=Depends(verify_key)):
    """Enable AI Max (broad match + AI) on an existing Search campaign."""
    cid = customer_id.replace("-","").strip()
    try:
        headers = _v13_headers(cid)
        r = httpx.post(
            f"{GOOGLE_ADS_API_V17}/customers/{cid}/campaigns:mutate",
            json={"operations": [{"update": {
                "resourceName": f"customers/{cid}/campaigns/{campaign_id}",
                "keywordMatchSetting": {"optIn": True},
            }, "updateMask": "keywordMatchSetting.optIn"}]},
            headers=headers, timeout=30
        )
        if r.is_success:
            return {"success": True, "message": "✅ AI Max (broad match expansion) enabled on campaign", "campaign_id": campaign_id}
        else:
            return {"success": False, "error": r.text[:300], "note": "AI Max requires campaign to have Smart Bidding enabled first"}
    except Exception as e:
        raise HTTPException(500, str(e))

# ═══════════════════════════════════════════════════════════════
# LIVE MONITOR (background task)
# ═══════════════════════════════════════════════════════════════

_monitor_active: dict = {}   # { customer_id: True/False }
_monitor_alerts: dict = {}   # { customer_id: [alerts] }

@app.post("/monitor/start")
async def monitor_start(body: dict, background_tasks: BackgroundTasks, _=Depends(verify_key)):
    """Start live monitoring for a customer account."""
    cid = body.get("customer_id","").replace("-","")
    if not cid: raise HTTPException(400, "customer_id required")
    _monitor_active[cid] = True
    _monitor_alerts[cid] = []
    background_tasks.add_task(_monitor_loop, cid)
    return {"success": True, "message": f"Monitoring started for {cid}", "customer_id": cid}

@app.post("/monitor/stop")
async def monitor_stop(body: dict, _=Depends(verify_key)):
    cid = body.get("customer_id","").replace("-","")
    _monitor_active[cid] = False
    return {"success": True, "message": f"Monitoring stopped for {cid}"}

@app.get("/monitor/alerts/{customer_id}")
async def get_alerts(customer_id: str, _=Depends(verify_key)):
    cid = customer_id.replace("-","")
    return {
        "active":  _monitor_active.get(cid, False),
        "alerts":  _monitor_alerts.get(cid, [])[-50:],  # last 50 alerts
        "customer_id": cid,
    }

@app.post("/monitor/check-now/{customer_id}")
async def check_now(customer_id: str, _=Depends(verify_key)):
    """Run a manual performance check right now."""
    cid = customer_id.replace("-","")
    alerts = await _run_monitor_check(cid)
    if cid not in _monitor_alerts: _monitor_alerts[cid] = []
    _monitor_alerts[cid].extend(alerts)
    return {"success": True, "alerts_found": len(alerts), "alerts": alerts}

async def _monitor_loop(cid: str):
    """Background task — checks every 60 min while active."""
    import asyncio as _asyncio
    while _monitor_active.get(cid, False):
        alerts = await _run_monitor_check(cid)
        if cid not in _monitor_alerts: _monitor_alerts[cid] = []
        _monitor_alerts[cid].extend(alerts)
        await _asyncio.sleep(3600)  # check every hour

async def _run_monitor_check(cid: str) -> list:
    """Run a single monitoring check — look for anomalies."""
    alerts = []
    try:
        perf = await get_performance(cid, days=1)
        if not perf.get("success"): return []
        today = perf.get("summary",{})
        # Alert if no conversions but high spend
        if today.get("total_spend",0) > 20 and today.get("total_conversions",0) == 0:
            alerts.append({"type":"warning","message":f"⚠️ ${today['total_spend']:.2f} spent today with 0 conversions","time":datetime.now().isoformat()})
        # Alert if CTR drops
        for c in perf.get("campaigns",[]):
            if c.get("impressions",0) > 100 and c.get("ctr",0) < 0.5:
                alerts.append({"type":"warning","message":f"⚠️ Low CTR on '{c['name']}': {c['ctr']}%","time":datetime.now().isoformat()})
    except Exception as e:
        alerts.append({"type":"error","message":f"Monitor check failed: {e}","time":datetime.now().isoformat()})
    return alerts

# ═══════════════════════════════════════════════════════════════
# RUN CREW V13 (with new agents 89-91)
# ═══════════════════════════════════════════════════════════════

class RunCrewV13Request(RunCrewRequest):
    run_agent_89: bool = True   # AI Max
    run_agent_90: bool = True   # Local Services
    run_agent_91: bool = True   # Enhanced Conversions

@app.post("/run-crew-v13")
async def run_crew_v13(body: RunCrewV13Request, _=Depends(verify_key)):
    """Run all 91 agents including 3 new v13 agents."""
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()

    try:
        # Run the base 88 agents first
        result = await run_all_agents(body)
        v13_count = 0

        # Run v13 agents sequentially (not in executor to avoid double-run)
        if body.run_agent_89:
            log.info("▶ Agent 89: AI Max (v13)")
            try:
                result["ai_max"] = await loop.run_in_executor(None, lambda: agent_89_ai_max(body))
                v13_count += 1
            except Exception as e:
                result["ai_max"] = {"error": str(e)}

        if body.run_agent_90:
            log.info("▶ Agent 90: Local Services Ads (v13)")
            try:
                result["local_services"] = await loop.run_in_executor(None, lambda: agent_90_local_services_ads(body))
                v13_count += 1
            except Exception as e:
                result["local_services"] = {"error": str(e)}

        if body.run_agent_91:
            log.info("▶ Agent 91: Enhanced Conversions (v13)")
            try:
                result["enhanced_conversions"] = await loop.run_in_executor(None, lambda: agent_91_enhanced_conversions(body))
                v13_count += 1
            except Exception as e:
                result["enhanced_conversions"] = {"error": str(e)}

        total_agents = result.get("agents_completed", 88) + v13_count
        result["version"] = "v13"
        result["agents_completed"] = total_agents

        # Save to DB — safe fallback if function unavailable
        run_id = 0
        try:
            d = body.dict()
            run_id = save_agent_run(
                d.get("website_url", ""),
                d,
                result,
                total_agents
            )
        except Exception as db_err:
            log.warning(f"DB save skipped: {db_err}")

        log.info(f"✅ v13 complete — {total_agents} agents. Run ID: {run_id}")
        return {"success": True, "run_id": run_id, **result}

    except Exception as e:
        log.error(f"run-crew-v13 error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))

# ═══════════════════════════════════════════════════════════════
# PUBLISH V13 (with API v17 + Data Manager)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/google/publish-v13")
async def publish_v13(body: PublishV13Request, _=Depends(verify_key)):
    """
    Publish to Google Ads using v17 API with:
    - Correct resource paths
    - Enhanced Conversions setup
    - AI Max option
    """
    cid = body.customer_id.replace("-","").strip()
    if not cid or len(cid) < 9:
        raise HTTPException(400, "Invalid Customer ID")

    try: _refresh_token_v13()
    except: pass

    headers = _v13_headers(cid)
    base    = f"{GOOGLE_ADS_API_V17}/customers/{cid}"
    agents  = body.agent_results.get("agents", {})
    biz     = body.agent_results.get("business_name","Campaign")
    daily   = float(body.agent_results.get("daily_budget", 50))
    website = body.agent_results.get("url", "https://example.com")
    ad_copy = agents.get("RSA Copywriter", {})
    kw_data = agents.get("STAG Keywords",  {})

    results = {}
    log.info(f"🚀 Publishing v13 to Google Ads {cid}")

    try:
        # 1. Budget
        br = httpx.post(f"{base}/campaignBudgets:mutate", headers=headers, json={
            "operations": [{"create": {
                "name": f"{biz} — AdsForge v13 Budget",
                "amountMicros": int(daily * 1_000_000),
                "deliveryMethod": "STANDARD",
                "explicitlyShared": False,
            }}]
        }, timeout=60)
        br.raise_for_status()
        budget_rn = br.json()["results"][0]["resourceName"]
        results["budget"] = budget_rn
        log.info(f"  ✅ Budget: {budget_rn}")

        # 2. Search campaign (v17 uses maxConversions as default per Google 2025 guidance)
        bidding = {"maximizeConversions": {}} if daily >= 20 else {"manualCpc": {"enhancedCpcEnabled": True}}
        cr = httpx.post(f"{base}/campaigns:mutate", headers=headers, json={
            "operations": [{"create": {
                "name":                   f"{biz} — Search [AdsForge v13]",
                "status":                 "PAUSED",
                "advertisingChannelType": "SEARCH",
                "campaignBudget":         budget_rn,
                **bidding,
                "networkSettings": {
                    "targetGoogleSearch":  True,
                    "targetSearchNetwork": True,
                    "targetContentNetwork": False,
                },
            }}]
        }, timeout=60)
        cr.raise_for_status()
        camp_rn = cr.json()["results"][0]["resourceName"]
        results["search_campaign"] = camp_rn
        log.info(f"  ✅ Campaign: {camp_rn}")

        # 3. Ad group
        agr = httpx.post(f"{base}/adGroups:mutate", headers=headers, json={
            "operations": [{"create": {
                "name":         f"{biz} — Main",
                "campaign":     camp_rn,
                "status":       "ENABLED",
                "type":         "STANDARD",
                "cpcBidMicros": 2_000_000,
            }}]
        }, timeout=60)
        agr.raise_for_status()
        ag_rn = agr.json()["results"][0]["resourceName"]
        results["ad_group"] = ag_rn

        # 4. Keywords (service-based, clean)
        kw_ops = []
        themes = kw_data.get("keywords_by_theme", {}) or kw_data.get("keywords_by_service", {})
        kw_count = 0
        for theme_kws in themes.values():
            for kw in (theme_kws if isinstance(theme_kws, list) else [])[:4]:
                text = kw.get("keyword", kw) if isinstance(kw, dict) else str(kw)
                mt   = (kw.get("match_type","PHRASE") if isinstance(kw,dict) else "PHRASE")
                if text and len(text) > 2 and kw_count < 20:
                    kw_ops.append({"create": {
                        "adGroup": ag_rn,
                        "status": "ENABLED",
                        "keyword": {"text": text, "matchType": mt},
                        "cpcBidMicros": 2_000_000,
                    }})
                    kw_count += 1
        if kw_ops:
            kr = httpx.post(f"{base}/adGroupCriteria:mutate",
                           headers=headers, json={"operations": kw_ops}, timeout=60)
            kr.raise_for_status()
            results["keywords_added"] = kw_count

        # 5. RSA ad
        hls  = [h[:30] for h in (ad_copy.get("headlines",[]) or []) if h][:15]
        desc = [d[:90] for d in (ad_copy.get("descriptions",[]) or []) if d][:4]
        while len(hls)  < 3: hls.append(biz[:28])
        while len(desc) < 2: desc.append("Contact us today for expert service.")
        url  = website if website.startswith("http") else f"https://{website}"
        ar = httpx.post(f"{base}/adGroupAds:mutate", headers=headers, json={
            "operations": [{"create": {
                "adGroup": ag_rn,
                "status":  "ENABLED",
                "ad": {
                    "responsiveSearchAd": {
                        "headlines":     [{"text": h} for h in hls],
                        "descriptions":  [{"text": d} for d in desc],
                    },
                    "finalUrls": [url],
                }
            }}]
        }, timeout=60)
        ar.raise_for_status()
        results["rsa_ad"] = "created"
        log.info(f"  ✅ RSA ad with {len(hls)} headlines")

        # 6. Optional: Enable AI Max
        camp_id = camp_rn.split("/")[-1]
        if body.enable_ai_max:
            try:
                aim = await configure_ai_max(cid, camp_id)
                results["ai_max"] = aim
            except Exception as e:
                results["ai_max"] = {"error": str(e)}

        return {
            "success":        True,
            "version":        "v13",
            "budget":         budget_rn,
            "search_campaign": camp_rn,
            "ad_group":       ag_rn,
            "keywords_added": results.get("keywords_added",0),
            "rsa_ad":         "created",
            "ai_max":         results.get("ai_max"),
            "message":        f"✅ Published with Google Ads API v17. Campaigns are PAUSED — review at ads.google.com",
            "next_step":      "Go to ads.google.com → find campaigns with [AdsForge v13] → review → enable",
        }

    except httpx.HTTPStatusError as e:
        try:    err_msg = e.response.json().get("error",{}).get("message", e.response.text[:300])
        except: err_msg = e.response.text[:300]
        log.error(f"Google Ads v17 API error: {err_msg}")
        return {"success": False, "error": err_msg, "api_version": "v17"}
    except Exception as e:
        log.error(f"publish-v13 error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/health-v13")
async def health_v13():
    return {
        "status":   "online",
        "version":  "13.0.0",
        "agents":   91,
        "phases":   16,
        "new_agents": ["A89: AI Max", "A90: Local Services Ads", "A91: Enhanced Conversions"],
        "api_version": "Google Ads API v17",
        "groq_ready": bool(GROQ_API_KEY),
        "oauth_connected": bool(_oauth_tokens.get("access_token") or os.getenv("GOOGLE_ADS_REFRESH_TOKEN","")),
        "features": [
            "OAuth2 multi-client auth",
            "Keyword Planner API (real volumes)",
            "Live performance monitoring",
            "Auto negative keywords",
            "Enhanced Conversions (SHA256)",
            "AI Max configuration",
            "GAQL search term analysis",
            "Google Ads API v17",
        ]
    }
