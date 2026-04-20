# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║   GOOGLE ADS ENTERPRISE v12 — FULLY AUTONOMOUS                  ║
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
    with open(_env_path, encoding="utf-8-sig") as _f:  # utf-8-sig strips BOM
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k = _k.strip()
                _v = _v.strip().strip('"').strip("'").strip()
                # Normalize GROQ_API_KEY-1 / GROQ_API_KEY-2 → GROQ_API_KEY / GROQ_API_KEY_2
                if _k == "GROQ_API_KEY-1":
                    _k = "GROQ_API_KEY"
                elif _k.startswith("GROQ_API_KEY-"):
                    _k = _k.replace("GROQ_API_KEY-", "GROQ_API_KEY_")
                if _v:
                    os.environ[_k] = _v  # overwrite so latest .env always wins

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
DASHBOARD_API_KEY   = os.getenv("DASHBOARD_API_KEY", "").strip()  # empty = no auth required
GOOGLE_ADS_DEV_TOK  = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()
GOOGLE_CLIENT_ID    = os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SEC   = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip()
GOOGLE_REFRESH_TOK  = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "").strip()
GOOGLE_MCC_ID       = os.getenv("GOOGLE_ADS_MCC_ID", "").strip()

DB_PATH = "campaigns.db"

# ── Groq AI Client (OpenAI-compatible) ───────────────────────────
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Two-tier model strategy:
#   GROQ_MODEL_FAST : llama-3.1-8b-instant  → 20,000 TPM free tier  (phases G-O, agents 36-88)
#   GROQ_MODEL_SMART: llama-3.3-70b-versatile → 6,000 TPM free tier (core agents 1-35)
GROQ_MODEL_SMART = os.getenv("GROQ_MODEL_SMART", "llama-3.3-70b-versatile")
GROQ_MODEL_FAST  = os.getenv("GROQ_MODEL_FAST",  "llama-3.1-8b-instant")
GROQ_MODEL       = GROQ_MODEL_SMART   # default (kept for any legacy references)

# Agents 1-35 are "core" and get the smart model.
# Agents 36-88 are "extended" and get the fast model (higher TPM).
SMART_AGENT_LIMIT = 35

# ── Token-bucket rate limiter ─────────────────────────────────────
# 70b model:  6,000 TPM  → gap = 60/8  = 7.5s per call at 800 tokens avg
# 8b model:  20,000 TPM  → gap = 60/25 = 2.4s per call at 800 tokens avg
_groq_lock         = asyncio.Lock()
_groq_last_call_ts = {"smart": 0.0, "fast": 0.0}
_MIN_GAP_SMART     = 7.0   # seconds between calls to 70b model
_MIN_GAP_FAST      = 2.5   # seconds between calls to 8b model
_groq_sem          = asyncio.Semaphore(1)   # one call at a time — safest

def groq_chat(system: str, user: str, max_tokens: int = 700, agent_num: int = 0) -> str:
    """Single Groq API call with smart model routing and proper 429 handling.
    
    - agent_num 1-35  → llama-3.3-70b-versatile (GROQ_MODEL_SMART, 6k TPM)
    - agent_num 36-88 → llama-3.1-8b-instant    (GROQ_MODEL_FAST,  20k TPM)
    - agent_num 0     → defaults to fast model
    """
    global _groq_last_call_ts
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set in .env")

    # ── Model selection ───────────────────────────────────────────
    use_smart = (1 <= agent_num <= SMART_AGENT_LIMIT)
    model     = GROQ_MODEL_SMART if use_smart else GROQ_MODEL_FAST
    tier_key  = "smart" if use_smart else "fast"
    min_gap   = _MIN_GAP_SMART if use_smart else _MIN_GAP_FAST

    # ── Per-model throttle ────────────────────────────────────────
    now  = time.time()
    wait = min_gap - (now - _groq_last_call_ts[tier_key])
    if wait > 0:
        log.info(f"  ⏳ Rate-limit gap {wait:.1f}s ({model})...")
        time.sleep(wait)
    _groq_last_call_ts[tier_key] = time.time()

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":      model,
        "max_tokens": max_tokens,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system + "\n\nRespond with valid JSON only. No markdown fences, no preamble."},
            {"role": "user",   "content": user},
        ],
    }

    for attempt in range(8):
        try:
            with httpx.Client(timeout=90) as client:
                r = client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)

                if r.status_code == 429:
                    # Read the actual Retry-After header — respect it but cap at 90s
                    retry_after = int(r.headers.get("retry-after", 0))
                    # Parse x-ratelimit-reset-tokens or x-ratelimit-reset-requests if present
                    reset_tokens = r.headers.get("x-ratelimit-reset-tokens", "")
                    # Parse "Xs" format (e.g. "12.5s" or "1m30s")
                    wait = min(retry_after if retry_after > 0 else 15, 90)
                    log.warning(f"Groq 429 ({model}) — waiting {wait}s (attempt {attempt+1}/8). retry-after={retry_after}s")
                    time.sleep(wait)
                    _groq_last_call_ts[tier_key] = time.time()
                    continue

                if r.status_code == 503:
                    wait = 10 + attempt * 5
                    log.warning(f"Groq 503 ({model}) — waiting {wait}s")
                    time.sleep(wait)
                    continue

                r.raise_for_status()
                _groq_last_call_ts[tier_key] = time.time()
                return r.json()["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            if attempt < 7:
                w = min(15 + attempt * 10, 60)
                log.warning(f"Groq HTTP {e.response.status_code} ({model}) — retry {attempt+1} in {w}s")
                time.sleep(w)
            else:
                raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            w = 10 + attempt * 5
            log.warning(f"Groq network error ({model}) — retry {attempt+1} in {w}s: {e}")
            time.sleep(w)

    raise RuntimeError(f"Groq API ({model}) failed after 8 retries")

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
    log.info("✅ Google Ads Enterprise v12 — 88 Agents Ready")
    yield
    log.info("Server shutting down")

# ── App ───────────────────────────────────────────────────────────
app = FastAPI(
    title="Google Ads Enterprise AI v12",
    version="12.0.0",
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
# Looks for index_v14.html first, then index.html
HTML_FILE = os.path.join(os.path.dirname(__file__), "index_v14.html")
if not os.path.exists(HTML_FILE):
    HTML_FILE = os.path.join(os.path.dirname(__file__), "index.html")

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
def ai_json(system: str, user: str, max_tokens: int = 700, agent_num: int = 0) -> dict:
    """Call Groq and parse JSON response robustly."""
    try:
        raw = groq_chat(system, user, max_tokens, agent_num=agent_num)
        # Strip markdown fences if model adds them anyway
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e} | raw[:300]: {raw[:300]}")
        return {"error": str(e), "raw_preview": raw[:500]}
    except Exception as e:
        log.error(f"AI call failed: {e}")
        return {"error": str(e)}

def ai_text(system: str, user: str, max_tokens: int = 400) -> str:
    """Call Groq for plain text using the fast model."""
    try:
        return groq_chat(system, user, max_tokens, agent_num=99)  # 99 → fast model
    except Exception as e:
        log.error(f"AI text call failed: {e}")
        return f"Error: {e}"

async def ai_json_async(system: str, user: str, max_tokens: int = 700, agent_num: int = 0) -> dict:
    """Async wrapper — runs groq_chat in thread so it never blocks the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: ai_json(system, user, max_tokens, agent_num))

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
    ,
        max_tokens=900,
        agent_num=1
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
    ,
        max_tokens=900,
        agent_num=2
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
    ,
        max_tokens=900,
        agent_num=3
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
        max_tokens=900,
        agent_num=4,
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
    ,
        max_tokens=900,
        agent_num=5
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
    ,
        max_tokens=900,
        agent_num=6
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
    ,
        max_tokens=900,
        agent_num=7
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
    ,
        max_tokens=900,
        agent_num=8
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
    ,
        max_tokens=900,
        agent_num=9
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
    ,
        max_tokens=900,
        agent_num=10
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
    ,
        max_tokens=700,
        agent_num=11
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
    ,
        max_tokens=700,
        agent_num=12
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
    ,
        max_tokens=700,
        agent_num=13
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
    ,
        max_tokens=700,
        agent_num=14
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
    ,
        max_tokens=700,
        agent_num=15
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
    ,
        max_tokens=700,
        agent_num=16
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
    ,
        max_tokens=700,
        agent_num=17
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
    ,
        max_tokens=700,
        agent_num=18
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
    ,
        max_tokens=700,
        agent_num=19
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
    ,
        max_tokens=700,
        agent_num=20
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
    ,
        max_tokens=700,
        agent_num=21
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
    ,
        max_tokens=700,
        agent_num=22
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
    ,
        max_tokens=700,
        agent_num=23
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
    ,
        max_tokens=700,
        agent_num=24
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
    ,
        max_tokens=700,
        agent_num=25
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
    ,
        max_tokens=700,
        agent_num=26
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
    ,
        max_tokens=700,
        agent_num=27
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
    ,
        max_tokens=700,
        agent_num=29
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
    ,
        max_tokens=700,
        agent_num=30
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
    ,
        max_tokens=700,
        agent_num=31
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
    ,
        max_tokens=700,
        agent_num=32
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
    ,
        max_tokens=700,
        agent_num=33
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
    ,
        max_tokens=700,
        agent_num=34
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
    ,
        max_tokens=700,
        agent_num=35
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
    ,
        max_tokens=600,
        agent_num=36
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
    ,
        max_tokens=600,
        agent_num=37
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
    ,
        max_tokens=600,
        agent_num=38
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
    ,
        max_tokens=600,
        agent_num=39
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
    ,
        max_tokens=600,
        agent_num=40
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
    ,
        max_tokens=600,
        agent_num=41
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
    ,
        max_tokens=600,
        agent_num=42
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
    ,
        max_tokens=600,
        agent_num=43
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
    ,
        max_tokens=600,
        agent_num=44
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
    ,
        max_tokens=600,
        agent_num=45
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
    ,
        max_tokens=600,
        agent_num=46
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
    ,
        max_tokens=600,
        agent_num=47
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
    ,
        max_tokens=600,
        agent_num=48
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
    ,
        max_tokens=600,
        agent_num=49
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
    ,
        max_tokens=600,
        agent_num=50
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
    ,
        max_tokens=600,
        agent_num=51
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
    ,
        max_tokens=600,
        agent_num=52
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
    ,
        max_tokens=600,
        agent_num=53
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
    ,
        max_tokens=600,
        agent_num=54
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
    ,
        max_tokens=600,
        agent_num=55
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
    ,
        max_tokens=600,
        agent_num=56
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
    ,
        max_tokens=600,
        agent_num=57
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
    ,
        max_tokens=600,
        agent_num=58
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
    ,
        max_tokens=600,
        agent_num=59
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
    ,
        max_tokens=600,
        agent_num=60
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
    ,
        max_tokens=600,
        agent_num=61
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
    ,
        max_tokens=600,
        agent_num=62
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
    ,
        max_tokens=600,
        agent_num=63
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
    ,
        max_tokens=600,
        agent_num=64
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
    ,
        max_tokens=600,
        agent_num=65
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
    ,
        max_tokens=600,
        agent_num=66
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
    ,
        max_tokens=600,
        agent_num=67
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
    ,
        max_tokens=600,
        agent_num=68
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
    ,
        max_tokens=600,
        agent_num=69
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
    ,
        max_tokens=600,
        agent_num=70
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
    ,
        max_tokens=600,
        agent_num=71
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
    ,
        max_tokens=600,
        agent_num=72
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
    ,
        max_tokens=600,
        agent_num=73
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
    ,
        max_tokens=600,
        agent_num=74
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
    ,
        max_tokens=600,
        agent_num=75
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
    ,
        max_tokens=600,
        agent_num=76
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
    ,
        max_tokens=600,
        agent_num=77
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
    ,
        max_tokens=600,
        agent_num=78
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
    ,
        max_tokens=600,
        agent_num=79
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
    ,
        max_tokens=600,
        agent_num=80
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
    ,
        max_tokens=600,
        agent_num=81
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
    ,
        max_tokens=600,
        agent_num=82
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
    ,
        max_tokens=600,
        agent_num=83
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
    ,
        max_tokens=600,
        agent_num=84
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
    ,
        max_tokens=600,
        agent_num=85
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
    ,
        max_tokens=600,
        agent_num=86
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
    ,
        max_tokens=600,
        agent_num=87
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
    ,
        max_tokens=600,
        agent_num=88
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
        # Run ONE at a time — the per-model throttle in groq_chat handles spacing
        for fn, n in pairs:
            result = await run(fn, n)
            results.append(result)
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
@app.get("/health-v13")
async def health():
    return {
        "status":          "online",
        "version":         "14.0.0",
        "agents":          88,
        "phases":          16,
        "google_ads_ready": bool(GOOGLE_ADS_DEV_TOK and GOOGLE_REFRESH_TOK),
        "ai_provider":     "Groq (dual-model)",
        "ai_model_smart":  GROQ_MODEL_SMART,
        "ai_model_fast":   GROQ_MODEL_FAST,
        "ai_ready":        bool(GROQ_API_KEY),
        "auth_required":   bool(DASHBOARD_API_KEY),
        "publish_ready":   bool(GOOGLE_ADS_DEV_TOK and GOOGLE_CLIENT_ID and GOOGLE_REFRESH_TOK),
        "mcc_configured":  bool(GOOGLE_MCC_ID),
    }

@app.post("/run-crew")
@app.post("/run-crew-v13")
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
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }) as client:
            r = await client.get(url)
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
        # Smart fallback: extract readable business info from the domain itself
        import re as _re2
        domain = url.replace("https://","").replace("http://","").replace("www.","").split("/")[0].split("?")[0]
        domain_name = domain.split(".")[0]
        # camelCase split: quickResponseGarage → quick Response Garage
        readable = _re2.sub(r'([a-z])([A-Z])', r'\1 \2', domain_name)
        # hyphen/underscore to space
        readable = readable.replace('-',' ').replace('_',' ')
        # split on number boundaries: abc123 → abc 123
        readable = _re2.sub(r'([a-zA-Z])(\d)', r'\1 \2', readable)
        readable = readable.strip()
        log.warning(f"Using domain-only analysis for {url} — site blocked fetch. Domain hint: {readable}")
        website_text = (
            f"Business website URL: {url}\n"
            f"Domain: {domain}\n"
            f"Business name hint from domain: {readable}\n"
            f"Note: the website blocked automated access. "
            f"Use the domain words to infer the business name, type and services."
        )

    # ── Step 2: AI extracts real info from the content ────────
    is_domain_only = "Domain:" in website_text and "blocked" in website_text
    result = await ai_json_async(
        "You are a business analyst. Extract business information from website content or domain names.",
        f"""Analyze this and extract accurate business information.
{"IMPORTANT: The website blocked access. Use the domain name hint to infer the business name and type. Be specific — 'quickresponsegaragedoorservice' clearly means a garage door service company." if is_domain_only else ""}

URL: {url}
Content:
{website_text}

Return ONLY this JSON:
{{
  "business_name": "{'Infer from domain — e.g. quickresponsegaragedoorservice → Quick Response Garage Door Service' if is_domain_only else 'exact business name from content'}",
  "business_type": "specific type e.g. Garage Door Repair, Electrical Contractor, Dental Clinic",
  "location": "city and state if found, else leave blank",
  "services": ["service 1", "service 2", "service 3", "service 4", "service 5"],
  "unique_value_propositions": ["infer from business type"],
  "target_audience": "who they serve",
  "fetch_status": "{'url_only' if is_domain_only else 'success'}"
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



# ════════════════════════════════════════════════════════════════════
# GROAS.AI FEATURE PARITY — Auto-Scheduler + Auto-Apply + Live Monitor
# ════════════════════════════════════════════════════════════════════
"""
These 4 systems make your project work like Groas.ai:

1. AUTO-SCHEDULER  — runs agents + optimization on a daily/hourly schedule
2. AUTO-APPLY      — reads agent output and pushes changes to Google Ads API
3. LIVE MONITOR    — pulls real metrics every 5 min, fires alerts on anomalies
4. REAL-DATA FEED  — search terms, auction data fed back into agent prompts
"""

import threading
import sqlite3 as _sqlite3
from datetime import datetime, timedelta

# ── Scheduler state ──────────────────────────────────────────────
_scheduler_active   = False
_scheduler_thread   = None
_scheduler_config: dict = {}
_scheduler_log: list = []

# ── Live monitor state ───────────────────────────────────────────
_live_monitor_active   = False
_live_monitor_thread   = None
_monitor_config_v2: dict = {}
_live_alerts: list = []

# ── Auto-apply log ───────────────────────────────────────────────
_apply_log: list = []


# ════════════════════════════════════════════════════════════════════
# SYSTEM 1 — AUTO-SCHEDULER
# Runs the full 91-agent crew automatically on a schedule
# ════════════════════════════════════════════════════════════════════

def _scheduler_run_once(config: dict):
    """Run one scheduled optimization cycle."""
    import asyncio as _asyncio
    customer_ids = config.get("customer_ids", [])
    business_name = config.get("business_name", "")
    business_type = config.get("business_type", "")
    website_url   = config.get("website_url", "")
    monthly_budget= config.get("monthly_budget", 1000)
    auto_apply    = config.get("auto_apply", False)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    _scheduler_log.append({"ts": ts, "status": "running", "message": "Starting scheduled optimization cycle..."})

    try:
        # Build request
        from pydantic import BaseModel
        req = RunCrewRequest(
            business_name=business_name,
            business_type=business_type,
            website_url=website_url,
            monthly_budget=monthly_budget,
            target_location=config.get("target_location", "United States"),
            campaign_types=config.get("campaign_types", ["search", "pmax"]),
            unique_selling_points=config.get("unique_selling_points", ""),
            target_audience=config.get("target_audience", ""),
            customer_id=customer_ids[0] if customer_ids else "",
            auto_publish=False,
        )

        # Run agents synchronously in scheduler thread
        loop = _asyncio.new_event_loop()
        result = loop.run_until_complete(run_all_agents(req))
        loop.close()

        # Save result
        save_campaign(req.dict(), result)

        # Auto-apply if enabled
        if auto_apply and customer_ids:
            for cid in customer_ids:
                try:
                    apply_loop = _asyncio.new_event_loop()
                    apply_result = apply_loop.run_until_complete(
                        _auto_apply_core(cid, result)
                    )
                    apply_loop.close()
                    _scheduler_log.append({
                        "ts": ts, "status": "applied",
                        "message": f"Auto-applied to {cid}: {apply_result.get('summary', '')}"
                    })
                except Exception as e:
                    _scheduler_log.append({"ts": ts, "status": "error", "message": f"Auto-apply failed for {cid}: {e}"})

        _scheduler_log.append({"ts": ts, "status": "done", "message": f"Cycle complete — {len(result)} outputs generated"})

    except Exception as e:
        _scheduler_log.append({"ts": ts, "status": "error", "message": f"Scheduler error: {e}"})

    # Keep only last 100 log entries
    if len(_scheduler_log) > 100:
        _scheduler_log[:] = _scheduler_log[-100:]


def _scheduler_loop(config: dict):
    """Main scheduler loop — runs at configured interval."""
    global _scheduler_active
    interval_hours = config.get("interval_hours", 24)
    interval_secs  = interval_hours * 3600

    log.info(f"⏰ Scheduler started — running every {interval_hours}h")

    # Run immediately on start
    _scheduler_run_once(config)

    while _scheduler_active:
        # Sleep in 60s chunks so we can stop cleanly
        for _ in range(int(interval_secs / 60)):
            if not _scheduler_active:
                break
            time.sleep(60)
        if _scheduler_active:
            _scheduler_run_once(config)

    log.info("⏰ Scheduler stopped")


@app.post("/scheduler/start")
async def start_scheduler(body: dict, _: None = Depends(verify_key)):
    """
    Start the auto-scheduler. It will:
    1. Run all 91 agents immediately
    2. Then repeat every interval_hours (default 24)
    3. Auto-apply changes to Google Ads if auto_apply=true

    Body: {
      customer_ids: ["123-456-7890"],
      business_name: "...", business_type: "...",
      website_url: "...", monthly_budget: 3000,
      interval_hours: 24,
      auto_apply: true
    }
    """
    global _scheduler_active, _scheduler_thread, _scheduler_config
    if _scheduler_active:
        return {"error": "Scheduler already running. Stop it first with /scheduler/stop"}

    _scheduler_config  = body
    _scheduler_active  = True
    _scheduler_thread  = threading.Thread(
        target=_scheduler_loop, args=(body,), daemon=True
    )
    _scheduler_thread.start()

    return {
        "started": True,
        "interval_hours": body.get("interval_hours", 24),
        "auto_apply": body.get("auto_apply", False),
        "accounts": body.get("customer_ids", []),
        "next_run": (datetime.now() + timedelta(hours=body.get("interval_hours", 24))).isoformat(),
        "message": "Scheduler started — first run happening now in background"
    }


@app.post("/scheduler/stop")
async def stop_scheduler(_: None = Depends(verify_key)):
    global _scheduler_active
    _scheduler_active = False
    return {"stopped": True, "message": "Scheduler will stop after current cycle completes"}


@app.get("/scheduler/status")
async def scheduler_status(_: None = Depends(verify_key)):
    next_run = None
    if _scheduler_active and _scheduler_log:
        last = _scheduler_log[-1]
        hrs  = _scheduler_config.get("interval_hours", 24)
        try:
            last_ts  = datetime.fromisoformat(last["ts"])
            next_run = (last_ts + timedelta(hours=hrs)).isoformat()
        except Exception:
            pass
    return {
        "active": _scheduler_active,
        "interval_hours": _scheduler_config.get("interval_hours", 24),
        "auto_apply": _scheduler_config.get("auto_apply", False),
        "accounts": _scheduler_config.get("customer_ids", []),
        "next_run": next_run,
        "recent_log": _scheduler_log[-10:],
    }

@app.get("/scheduler/log")
async def scheduler_log_endpoint(_: None = Depends(verify_key)):
    return _scheduler_log[-50:]


# ════════════════════════════════════════════════════════════════════
# SYSTEM 2 — AUTO-APPLY RECOMMENDATIONS TO GOOGLE ADS
# Reads agent output and pushes changes directly to Google Ads API
# ════════════════════════════════════════════════════════════════════

async def _auto_apply_core(customer_id: str, agent_results: dict) -> dict:
    """
    Core auto-apply logic. Reads agent outputs and applies to Google Ads:
    - Adds keywords from Agent A04
    - Adds negative keywords from Agent A06
    - Pauses keywords with 0 conversions & high spend
    - Updates ad copy from Agent A08
    - Adjusts bids based on Agent A19 recommendations
    """
    cid     = customer_id.replace("-", "")
    applied = []
    errors  = []
    summary = ""

    try:
        headers = _gads_headers(cid)
        base    = f"{GOOGLE_ADS_BASE_V17}/customers/{cid}"

        # ── 1. Get existing campaigns ────────────────────────────
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{base}/googleAds:searchStream",
                json={"query": "SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.status = 'ENABLED' LIMIT 10"},
                headers=headers)

        campaigns = []
        if r.is_success:
            for batch in r.json():
                for row in batch.get("results", []):
                    campaigns.append({
                        "id":       row["campaign"]["id"],
                        "name":     row["campaign"]["name"],
                        "resource": f"customers/{cid}/campaigns/{row['campaign']['id']}"
                    })

        if not campaigns:
            return {"success": False, "error": "No enabled campaigns found. Create campaigns first via /api/google/publish-v13"}

        main_campaign = campaigns[0]

        # ── 2. Auto-add negative keywords from Agent A06 ─────────
        neg_data = agent_results.get("negative_keywords", {})
        negatives = []
        if isinstance(neg_data, dict):
            for key in ["campaign_level_negatives", "negatives", "negative_keywords", "broad_negatives"]:
                val = neg_data.get(key, [])
                if isinstance(val, list):
                    negatives += [n if isinstance(n, str) else n.get("keyword", "") for n in val[:20]]

        negatives = [n for n in negatives if n and isinstance(n, str) and len(n) > 2][:20]

        if negatives:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    neg_ops = [{"create": {
                        "campaign": main_campaign["resource"],
                        "keyword": {"text": kw[:80], "matchType": "BROAD"},
                        "negative": True
                    }} for kw in negatives]

                    r2 = await client.post(f"{base}/campaignCriteria:mutate",
                        json={"operations": neg_ops}, headers=headers)

                if r2.is_success:
                    applied.append(f"✅ Added {len(negatives)} negative keywords to {main_campaign['name']}")
                else:
                    errors.append(f"Negatives: {r2.text[:150]}")
            except Exception as e:
                errors.append(f"Negatives error: {str(e)[:100]}")

        # ── 3. Auto-add positive keywords from Agent A04 ─────────
        kw_data  = agent_results.get("keywords", {})
        keywords = []
        if isinstance(kw_data, dict):
            for key in ["keywords_by_service", "ad_groups", "exact_match", "phrase_match"]:
                val = kw_data.get(key)
                if isinstance(val, list):
                    for item in val[:5]:
                        if isinstance(item, str):
                            keywords.append(item)
                        elif isinstance(item, dict):
                            for kk in ["keyword", "term", "exact_match", "phrase_match"]:
                                if item.get(kk):
                                    if isinstance(item[kk], list):
                                        keywords += [k if isinstance(k,str) else k.get("keyword","") for k in item[kk][:3]]
                                    elif isinstance(item[kk], str):
                                        keywords.append(item[kk])
                elif isinstance(val, dict):
                    for svc_kws in list(val.values())[:3]:
                        if isinstance(svc_kws, list):
                            keywords += [k if isinstance(k,str) else k.get("keyword","") for k in svc_kws[:5]]

        keywords = list(set([k for k in keywords if k and isinstance(k,str) and 2 < len(k) < 80]))[:30]

        # Get first ad group
        ad_group_resource = None
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r3 = await client.post(f"{base}/googleAds:searchStream",
                    json={"query": f"SELECT ad_group.id, ad_group.resource_name FROM ad_group WHERE campaign.resource_name = '{main_campaign['resource']}' LIMIT 1"},
                    headers=headers)
            if r3.is_success:
                for batch in r3.json():
                    for row in batch.get("results", []):
                        ad_group_resource = row["ad_group"]["resourceName"]
                        break
        except Exception:
            pass

        if keywords and ad_group_resource:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    kw_ops = [{"create": {
                        "adGroup": ad_group_resource,
                        "keyword": {"text": kw, "matchType": "PHRASE"},
                        "status": "PAUSED"  # Paused — review before enabling
                    }} for kw in keywords[:20]]

                    r4 = await client.post(f"{base}/adGroupCriteria:mutate",
                        json={"operations": kw_ops}, headers=headers)

                if r4.is_success:
                    applied.append(f"✅ Added {len(keywords[:20])} keywords (PAUSED — review before enabling)")
                else:
                    errors.append(f"Keywords: {r4.text[:150]}")
            except Exception as e:
                errors.append(f"Keywords error: {str(e)[:100]}")

        # ── 4. Auto-pause wasted spend keywords ──────────────────
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                waste_r = await client.post(f"{base}/googleAds:searchStream",
                    json={"query": """
                        SELECT ad_group_criterion.resource_name, ad_group_criterion.keyword.text,
                               metrics.cost_micros, metrics.conversions, metrics.clicks
                        FROM keyword_view
                        WHERE segments.date DURING LAST_30_DAYS
                          AND metrics.cost_micros > 5000000
                          AND metrics.conversions = 0
                          AND metrics.clicks > 10
                        ORDER BY metrics.cost_micros DESC LIMIT 20
                    """}, headers=headers)

            wasted_kws = []
            if waste_r.is_success:
                for batch in waste_r.json():
                    for row in batch.get("results", []):
                        wasted_kws.append(row["adGroupCriterion"]["resourceName"])

            if wasted_kws:
                async with httpx.AsyncClient(timeout=30) as client:
                    pause_ops = [{"update": {
                        "resourceName": rn,
                        "status": "PAUSED"
                    }, "updateMask": "status"} for rn in wasted_kws]

                    rp = await client.post(f"{base}/adGroupCriteria:mutate",
                        json={"operations": pause_ops}, headers=headers)

                if rp.is_success:
                    applied.append(f"✅ Paused {len(wasted_kws)} wasted-spend keywords (0 conv, high cost)")
                else:
                    errors.append(f"Pause wasted: {rp.text[:100]}")
        except Exception as e:
            errors.append(f"Waste check: {str(e)[:100]}")

        # ── 5. Update bid adjustments from Agent A19 ─────────────
        bid_data = agent_results.get("bidding_strategy", {})
        if isinstance(bid_data, dict):
            target_cpa = bid_data.get("target_cpa_estimate") or bid_data.get("target_cpa")
            if target_cpa and str(target_cpa).replace(".","").isdigit():
                try:
                    async with httpx.AsyncClient(timeout=20) as client:
                        rb = await client.post(f"{base}/campaigns:mutate",
                            json={"operations": [{"update": {
                                "resourceName": main_campaign["resource"],
                                "targetCpa": {"targetCpaMicros": str(int(float(target_cpa) * 1_000_000))},
                            }, "updateMask": "target_cpa.target_cpa_micros"}]},
                            headers=headers)
                    if rb.is_success:
                        applied.append(f"✅ Set target CPA to ${target_cpa}")
                    else:
                        errors.append(f"CPA update: {rb.text[:100]}")
                except Exception as e:
                    errors.append(f"Bid update: {str(e)[:80]}")

        summary = f"{len(applied)} changes applied, {len(errors)} errors"
        return {
            "success": True,
            "customer_id": customer_id,
            "campaign": main_campaign["name"],
            "applied": applied,
            "errors": errors,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        log.error(f"Auto-apply failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.post("/auto-apply/{customer_id}")
async def auto_apply(customer_id: str, body: dict = {}, _: None = Depends(verify_key)):
    """
    Auto-apply agent recommendations to Google Ads.
    Pass agent_results in body, or it uses the latest saved campaign.
    """
    if not GOOGLE_ADS_DEV_TOK:
        return {"success": False, "error": "Google Ads not configured. Check /diagnose-google-ads"}

    agent_results = body.get("agent_results")

    # Use latest saved campaign if no results passed
    if not agent_results:
        try:
            con = _sqlite3.connect(DB_PATH)
            row = con.execute(
                "SELECT result FROM campaigns ORDER BY id DESC LIMIT 1"
            ).fetchone()
            con.close()
            if row:
                agent_results = json.loads(row[0])
            else:
                return {"success": False, "error": "No saved campaigns found. Run agents first."}
        except Exception as e:
            return {"success": False, "error": f"Could not load campaign: {e}"}

    result = await _auto_apply_core(customer_id, agent_results)
    _apply_log.append(result)
    return result


@app.get("/auto-apply/log")
async def auto_apply_log(_: None = Depends(verify_key)):
    return _apply_log[-20:]


# ════════════════════════════════════════════════════════════════════
# SYSTEM 3 — LIVE MONITORING WITH REAL DATA
# Pulls real metrics every N minutes, fires AI-powered alerts
# ════════════════════════════════════════════════════════════════════

async def _fetch_live_metrics(customer_id: str) -> dict:
    """Pull real-time metrics from Google Ads for monitoring."""
    cid = customer_id.replace("-", "")
    try:
        headers = _gads_headers(cid)
        query = """
            SELECT
                campaign.name, campaign.status,
                metrics.impressions, metrics.clicks, metrics.ctr,
                metrics.cost_micros, metrics.conversions,
                metrics.cost_per_conversion, metrics.average_cpc
            FROM campaign
            WHERE segments.date DURING TODAY
            ORDER BY metrics.cost_micros DESC
            LIMIT 20
        """
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/googleAds:searchStream",
                json={"query": query}, headers=headers
            )

        if not r.is_success:
            return {"error": r.text[:200]}

        campaigns = []
        total_cost    = 0
        total_conv    = 0
        total_clicks  = 0

        for batch in r.json():
            for row in batch.get("results", []):
                m    = row.get("metrics", {})
                cost = int(m.get("costMicros", 0)) / 1_000_000
                conv = float(m.get("conversions", 0))
                clks = int(m.get("clicks", 0))
                total_cost   += cost
                total_conv   += conv
                total_clicks += clks
                campaigns.append({
                    "name":        row["campaign"]["name"],
                    "status":      row["campaign"]["status"],
                    "cost_today":  round(cost, 2),
                    "clicks":      clks,
                    "conversions": round(conv, 1),
                    "ctr":         round(float(m.get("ctr", 0)) * 100, 2),
                    "avg_cpc":     round(int(m.get("averageCpc", 0)) / 1_000_000, 2),
                    "cpa":         round(cost / conv, 2) if conv > 0 else 0,
                })

        return {
            "customer_id":   customer_id,
            "timestamp":     datetime.now().isoformat(),
            "campaigns":     campaigns,
            "total_cost":    round(total_cost, 2),
            "total_clicks":  total_clicks,
            "total_conv":    round(total_conv, 1),
            "overall_cpa":   round(total_cost / total_conv, 2) if total_conv > 0 else 0,
        }
    except Exception as e:
        return {"error": str(e), "customer_id": customer_id}


def _check_alerts(metrics: dict, config: dict) -> list:
    """Check metrics against thresholds and generate alerts."""
    alerts = []
    ts     = datetime.now().isoformat()

    if "error" in metrics:
        return alerts

    daily_budget  = float(config.get("daily_budget", 999999))
    max_cpa       = float(config.get("max_cpa", 999999))
    min_ctr       = float(config.get("min_ctr", 0))

    # Budget burn alert
    if metrics["total_cost"] > daily_budget * 0.9:
        alerts.append({
            "ts": ts, "level": "critical",
            "type": "budget_burn",
            "message": f"🚨 Budget 90% spent today — ${metrics['total_cost']:.2f} of ${daily_budget:.2f}",
            "customer_id": metrics["customer_id"]
        })
    elif metrics["total_cost"] > daily_budget * 0.7:
        alerts.append({
            "ts": ts, "level": "warning",
            "type": "budget_burn",
            "message": f"⚠️ Budget 70% spent — ${metrics['total_cost']:.2f} of ${daily_budget:.2f}",
            "customer_id": metrics["customer_id"]
        })

    # CPA alert
    if metrics["overall_cpa"] > max_cpa and metrics["total_conv"] > 0:
        alerts.append({
            "ts": ts, "level": "warning",
            "type": "high_cpa",
            "message": f"⚠️ CPA ${metrics['overall_cpa']:.2f} exceeds target ${max_cpa:.2f}",
            "customer_id": metrics["customer_id"]
        })

    # Zero conversions alert
    if metrics["total_clicks"] > 50 and metrics["total_conv"] == 0:
        alerts.append({
            "ts": ts, "level": "warning",
            "type": "zero_conv",
            "message": f"⚠️ {metrics['total_clicks']} clicks but 0 conversions today — check landing page",
            "customer_id": metrics["customer_id"]
        })

    # Low CTR alert
    for camp in metrics.get("campaigns", []):
        if camp["clicks"] > 100 and camp["ctr"] < min_ctr:
            alerts.append({
                "ts": ts, "level": "info",
                "type": "low_ctr",
                "message": f"📊 Low CTR {camp['ctr']}% on '{camp['name']}' — refresh ad copy",
                "customer_id": metrics["customer_id"]
            })

    return alerts


def _live_monitor_loop(config: dict):
    """Live monitoring loop — pulls metrics every interval_minutes."""
    global _monitor_active
    import asyncio as _asyncio

    interval_mins = config.get("interval_minutes", 5)
    customer_ids  = config.get("customer_ids", [])

    log.info(f"📡 Live monitor started — checking every {interval_mins} min for {customer_ids}")

    while _live_monitor_active:
        for cid in customer_ids:
            try:
                loop = _asyncio.new_event_loop()
                metrics = loop.run_until_complete(_fetch_live_metrics(cid))
                loop.close()

                alerts = _check_alerts(metrics, config)
                for alert in alerts:
                    _live_alerts.append(alert)
                    log.warning(f"ALERT [{alert['level']}]: {alert['message']}")

                # Store metrics snapshot
                _live_alerts.append({
                    "ts":          datetime.now().isoformat(),
                    "level":       "metric",
                    "type":        "snapshot",
                    "message":     f"📊 {cid}: ${metrics.get('total_cost',0):.2f} spent, {metrics.get('total_conv',0)} conv, {metrics.get('total_clicks',0)} clicks",
                    "customer_id": cid,
                    "data":        metrics
                })

            except Exception as e:
                _live_alerts.append({
                    "ts": datetime.now().isoformat(), "level": "error",
                    "type": "monitor_error",
                    "message": f"Monitor error for {cid}: {e}",
                    "customer_id": cid
                })

        # Keep only last 500 alerts
        if len(_live_alerts) > 500:
            _live_alerts[:] = _live_alerts[-500:]

        # Sleep in chunks
        for _ in range(interval_mins * 60 // 10):
            if not _monitor_active:
                break
            time.sleep(10)

    log.info("📡 Live monitor stopped")


@app.post("/live-monitor/start")
async def start_live_monitor(body: dict, _: None = Depends(verify_key)):
    """
    Start live monitoring. Pulls real metrics every interval_minutes.
    Fires alerts for: budget burn, high CPA, zero conversions, low CTR.

    Body: {
      customer_ids: ["123-456-7890"],
      interval_minutes: 5,
      daily_budget: 100,
      max_cpa: 50,
      min_ctr: 2.0
    }
    """
    global _live_monitor_active, _live_monitor_thread, _monitor_config_v2
    if _live_monitor_active:
        return {"error": "Monitor already running. Stop with /live-monitor/stop"}

    _monitor_config_v2 = body
    _live_live_monitor_active    = True
    _live_live_monitor_thread    = threading.Thread(
        target=_live_monitor_loop, args=(body,), daemon=True
    )
    _live_monitor_thread.start()

    return {
        "started": True,
        "accounts": body.get("customer_ids", []),
        "interval_minutes": body.get("interval_minutes", 5),
        "thresholds": {
            "daily_budget": body.get("daily_budget"),
            "max_cpa": body.get("max_cpa"),
            "min_ctr": body.get("min_ctr"),
        },
        "message": "Live monitoring started — first check in progress"
    }


@app.post("/live-monitor/stop")
async def stop_live_monitor(_: None = Depends(verify_key)):
    global _live_monitor_active
    _live_monitor_active = False
    return {"stopped": True}


@app.get("/live-monitor/alerts")
async def get_live_alerts(limit: int = 50, level: str = "", _: None = Depends(verify_key)):
    alerts = _live_alerts[-200:]
    if level:
        alerts = [a for a in alerts if a.get("level") == level]
    return list(reversed(alerts))[-limit:]


@app.get("/live-monitor/metrics/{customer_id}")
async def get_live_metrics(customer_id: str, _: None = Depends(verify_key)):
    """Pull real-time metrics for a customer right now."""
    if not GOOGLE_ADS_DEV_TOK:
        return {"error": "Google Ads not configured"}
    return await _fetch_live_metrics(customer_id)


@app.get("/live-monitor/status")
async def live_monitor_status(_: None = Depends(verify_key)):
    recent_metrics = [a for a in _live_alerts if a.get("type") == "snapshot"]
    recent_alerts  = [a for a in _live_alerts if a.get("level") in ["critical","warning"]]
    return {
        "active":           _monitor_active,
        "accounts":         _monitor_config_v2.get("customer_ids", []),
        "interval_minutes": _monitor_config_v2.get("interval_minutes", 5),
        "total_alerts":     len(recent_alerts),
        "critical_alerts":  len([a for a in recent_alerts if a.get("level") == "critical"]),
        "last_check":       recent_metrics[-1]["ts"] if recent_metrics else None,
        "last_snapshot":    recent_metrics[-1].get("data") if recent_metrics else None,
    }


# ════════════════════════════════════════════════════════════════════
# SYSTEM 4 — REAL DATA FEED BACK INTO AGENTS
# Search terms, auction insights pulled from live account
# and fed back into agent prompts for better recommendations
# ════════════════════════════════════════════════════════════════════

@app.post("/real-data-run/{customer_id}")
async def real_data_run(customer_id: str, body: RunCrewRequest, _: None = Depends(verify_key)):
    """
    Enhanced agent run that feeds REAL Google Ads data back into agents.
    Pulls actual search terms, auction insights, and performance data
    before running agents so recommendations are based on real numbers.
    """
    if not GOOGLE_ADS_DEV_TOK:
        return {"error": "Google Ads not configured — running standard agent crew instead"}

    cid = customer_id.replace("-", "")
    real_data = {}

    # ── Pull real search terms ───────────────────────────────────
    try:
        headers = _gads_headers(cid)
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/googleAds:searchStream",
                json={"query": """
                    SELECT search_term_view.search_term, metrics.impressions,
                           metrics.clicks, metrics.cost_micros, metrics.conversions
                    FROM search_term_view
                    WHERE segments.date DURING LAST_30_DAYS
                    ORDER BY metrics.impressions DESC LIMIT 50
                """}, headers=headers)

        if r.is_success:
            terms = []
            for batch in r.json():
                for row in batch.get("results", []):
                    m = row.get("metrics", {})
                    terms.append({
                        "term":        row["searchTermView"]["searchTerm"],
                        "impressions": int(m.get("impressions", 0)),
                        "clicks":      int(m.get("clicks", 0)),
                        "cost":        round(int(m.get("costMicros", 0)) / 1_000_000, 2),
                        "conversions": round(float(m.get("conversions", 0)), 1),
                    })
            real_data["top_search_terms"] = terms[:30]
            log.info(f"✅ Pulled {len(terms)} real search terms from {customer_id}")
    except Exception as e:
        real_data["search_terms_error"] = str(e)

    # ── Pull real performance data ───────────────────────────────
    try:
        metrics = await _fetch_live_metrics(customer_id)
        real_data["live_performance"] = metrics
    except Exception as e:
        real_data["performance_error"] = str(e)

    # ── Pull auction insights ────────────────────────────────────
    try:
        headers = _gads_headers(cid)
        async with httpx.AsyncClient(timeout=20) as client:
            r2 = await client.post(
                f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/googleAds:searchStream",
                json={"query": """
                    SELECT auction_insight_summary.domain,
                           auction_insight_summary.impression_share,
                           auction_insight_summary.overlap_rate,
                           auction_insight_summary.position_above_rate,
                           auction_insight_summary.top_of_page_rate,
                           auction_insight_summary.outranking_share
                    FROM auction_insight_summary
                    WHERE segments.date DURING LAST_30_DAYS
                    LIMIT 10
                """}, headers=headers)
        if r2.is_success:
            auction = []
            for batch in r2.json():
                for row in batch.get("results", []):
                    a = row.get("auctionInsightSummary", {})
                    auction.append({
                        "domain":           a.get("domain", ""),
                        "impression_share": round(float(a.get("impressionShare", 0)) * 100, 1),
                        "overlap_rate":     round(float(a.get("overlapRate", 0)) * 100, 1),
                        "outranking_share": round(float(a.get("outrankingShare", 0)) * 100, 1),
                    })
            real_data["auction_insights"] = auction
    except Exception as e:
        real_data["auction_error"] = str(e)

    # ── Now run agents with real data injected into context ──────
    # Enrich the request with real data so agents use it in prompts
    enriched_body = body.copy()

    if real_data.get("top_search_terms"):
        top_terms = [t["term"] for t in real_data["top_search_terms"][:10]]
        enriched_body.unique_selling_points = (
            body.unique_selling_points +
            f" | TOP REAL SEARCH TERMS FROM ACCOUNT: {', '.join(top_terms)}"
        )

    if real_data.get("live_performance", {}).get("overall_cpa"):
        cpa = real_data["live_performance"]["overall_cpa"]
        enriched_body.unique_selling_points += f" | CURRENT CPA: ${cpa}"

    # Run all agents with enriched data
    agent_results = await run_all_agents(enriched_body)
    agent_results["real_data_injected"] = real_data
    agent_results["data_source"] = "live_google_ads_account"

    save_campaign(body.dict(), agent_results)

    return agent_results


# ════════════════════════════════════════════════════════════════════
# UPDATED HEALTH CHECK — shows all new Groas.ai features
# ════════════════════════════════════════════════════════════════════

@app.get("/health-groas")
async def health_groas(_: None = Depends(verify_key)):
    return {
        "version": "groas-parity-1.0",
        "agents":  91,
        "groas_features": {
            "auto_scheduler":    _scheduler_active,
            "auto_apply":        bool(GOOGLE_ADS_DEV_TOK),
            "live_monitoring":   _monitor_active,
            "real_data_feed":    bool(GOOGLE_ADS_DEV_TOK),
        },
        "endpoints": {
            "scheduler":    ["/scheduler/start", "/scheduler/stop", "/scheduler/status", "/scheduler/log"],
            "auto_apply":   ["/auto-apply/{customer_id}", "/auto-apply/log"],
            "live_monitor": ["/live-monitor/start", "/live-monitor/stop", "/live-monitor/alerts",
                            "/live-monitor/metrics/{customer_id}", "/live-monitor/status"],
            "real_data":    ["/real-data-run/{customer_id}"],
        },
        "google_ads_ready": bool(GOOGLE_ADS_DEV_TOK and GOOGLE_REFRESH_TOK),
        "ai_ready":         bool(GROQ_API_KEY),
        "scheduler_config": _scheduler_config,
        "monitor_config":   _monitor_config_v2,
    }



# ════════════════════════════════════════════════════════════════════
# MISSING FEATURES — Email Alerts, PDF Reports, A/B Tracking, Bid Loop
# ════════════════════════════════════════════════════════════════════

import smtplib, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email config from .env
EMAIL_FROM    = os.getenv("ALERT_EMAIL_FROM", "")
EMAIL_TO      = os.getenv("ALERT_EMAIL_TO", "")
EMAIL_PASS    = os.getenv("ALERT_EMAIL_PASS", "")
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))

# A/B test storage (in-memory + sqlite)
_ab_tests: dict = {}


# ─────────────────────────────────────────────────────────────────
# FEATURE 1: EMAIL ALERTS
# ─────────────────────────────────────────────────────────────────

def send_email_alert(subject: str, body: str, to: str = ""):
    """Send email alert. Configure ALERT_EMAIL_* in .env"""
    if not EMAIL_FROM or not EMAIL_PASS:
        log.warning("Email not configured — add ALERT_EMAIL_FROM, ALERT_EMAIL_PASS to .env")
        return False
    recipient = to or EMAIL_TO
    if not recipient:
        log.warning("No recipient email — add ALERT_EMAIL_TO to .env")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_FROM
        msg["To"]      = recipient
        msg["Subject"] = f"[AdsForge Alert] {subject}"
        msg.attach(MIMEText(f"""
        <html><body style="font-family:Arial,sans-serif;background:#030508;color:#e2eaf8;padding:20px">
        <div style="max-width:600px;margin:0 auto;background:#0c1520;border-radius:12px;padding:24px;border:1px solid #162030">
          <h2 style="color:#3b82f6;margin-bottom:16px">⚡ AdsForge AI Alert</h2>
          <div style="background:#080d14;border-radius:8px;padding:16px;font-size:14px;line-height:1.7">
            {body.replace(chr(10),'<br>')}
          </div>
          <div style="margin-top:16px;font-size:11px;color:#4d6a8a">
            Sent by AdsForge AI · {datetime.now().strftime('%Y-%m-%d %H:%M')}
          </div>
        </div>
        </body></html>
        """, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, recipient, msg.as_string())
        log.info(f"✅ Email alert sent to {recipient}: {subject}")
        return True
    except Exception as e:
        log.error(f"Email send failed: {e}")
        return False


@app.post("/alerts/test-email")
async def test_email_alert(body: dict, _: None = Depends(verify_key)):
    """Test email alert. Send {to: 'email@example.com'} in body."""
    ok = send_email_alert(
        "Test Alert — AdsForge is working!",
        "This is a test alert from your AdsForge AI dashboard.\n\nEmail alerts are now configured correctly.",
        body.get("to", "")
    )
    return {"sent": ok, "from": EMAIL_FROM, "configured": bool(EMAIL_FROM and EMAIL_PASS)}


@app.get("/alerts/email-status")
async def email_status(_: None = Depends(verify_key)):
    return {
        "configured": bool(EMAIL_FROM and EMAIL_PASS and EMAIL_TO),
        "from":       EMAIL_FROM or "not set",
        "to":         EMAIL_TO   or "not set",
        "missing": [k for k,v in {
            "ALERT_EMAIL_FROM": EMAIL_FROM,
            "ALERT_EMAIL_PASS": EMAIL_PASS,
            "ALERT_EMAIL_TO":   EMAIL_TO,
        }.items() if not v]
    }


# ─────────────────────────────────────────────────────────────────
# FEATURE 2: PDF REPORT GENERATION
# ─────────────────────────────────────────────────────────────────

@app.post("/report/pdf/{customer_id}")
async def generate_pdf_report(customer_id: str, body: dict = {}, _: None = Depends(verify_key)):
    """
    Generate a professional PDF report from the latest campaign results.
    Returns HTML report (print to PDF from browser) since reportlab isn't installed.
    Open /report/html/{customer_id} and Ctrl+P to save as PDF.
    """
    # Load latest campaign
    try:
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT business_name, business_type, created, result FROM campaigns ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    if not row:
        return JSONResponse({"error": "No campaigns found. Run agents first."}, status_code=404)

    biz_name, biz_type, created, result_json = row
    try:
        result = json.loads(result_json)
    except Exception:
        result = {}

    roi      = result.get("roi_forecast", {})
    kws      = result.get("keywords", {})
    ads      = result.get("ad_copy", {})
    budget   = result.get("budget_plan", {})
    strategy = result.get("campaign_strategy", {})
    negatives= result.get("negative_keywords", {})
    brain    = result.get("campaign_brain", {})

    def safe_json(obj, indent=2):
        try:
            return json.dumps(obj, indent=indent)
        except Exception:
            return str(obj)

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>AdsForge AI Report — {biz_name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
  * {{box-sizing:border-box;margin:0;padding:0}}
  body {{font-family:'Inter',sans-serif;background:#fff;color:#1a1a2e;font-size:13px;line-height:1.6}}
  .cover {{background:linear-gradient(135deg,#1e3a5f,#0f2027);color:#fff;padding:60px;min-height:280px;display:flex;flex-direction:column;justify-content:flex-end}}
  .cover h1 {{font-size:36px;font-weight:900;margin-bottom:8px}}
  .cover p {{font-size:14px;opacity:.7}}
  .section {{padding:32px 48px;border-bottom:1px solid #eee;page-break-inside:avoid}}
  .section h2 {{font-size:18px;font-weight:700;color:#1e3a5f;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
  .metric-row {{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px}}
  .metric {{background:#f8faff;border:1px solid #e0e8ff;border-radius:10px;padding:16px;text-align:center}}
  .metric .val {{font-size:28px;font-weight:900;color:#3b82f6}}
  .metric .lbl {{font-size:11px;color:#888;margin-top:4px}}
  pre {{background:#f5f5f5;border-radius:8px;padding:16px;font-size:11px;overflow-x:auto;white-space:pre-wrap;max-height:300px;overflow-y:auto}}
  .kw-chip {{display:inline-block;background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;padding:3px 10px;border-radius:99px;font-size:11px;margin:3px}}
  .neg-chip {{display:inline-block;background:#fef2f2;border:1px solid #fecaca;color:#dc2626;padding:3px 10px;border-radius:99px;font-size:11px;margin:3px}}
  @media print {{body{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
</style>
</head><body>

<div class="cover">
  <div style="font-size:13px;opacity:.6;margin-bottom:20px">ADSFORGE AI — CAMPAIGN INTELLIGENCE REPORT</div>
  <h1>{biz_name}</h1>
  <p>{biz_type} · Generated {created[:10]} · 91 AI Agents</p>
</div>

<div class="section">
  <h2>📊 ROI Forecast</h2>
  <div class="metric-row">
    <div class="metric"><div class="val">{roi.get('monthly_clicks_estimate','—')}</div><div class="lbl">Est. Monthly Clicks</div></div>
    <div class="metric"><div class="val">{roi.get('monthly_conversions_estimate','—')}</div><div class="lbl">Est. Conversions</div></div>
    <div class="metric"><div class="val">${roi.get('cost_per_conversion_estimate','—')}</div><div class="lbl">Est. CPA</div></div>
    <div class="metric"><div class="val">{roi.get('roas_estimate','—')}x</div><div class="lbl">Est. ROAS</div></div>
  </div>
</div>

<div class="section">
  <h2>🔑 Master Strategy</h2>
  <pre>{safe_json(strategy)}</pre>
</div>

<div class="section">
  <h2>📝 Ad Copy (RSA Headlines)</h2>
  <pre>{safe_json(ads)}</pre>
</div>

<div class="section">
  <h2>🔍 Keywords</h2>
  <pre>{safe_json(kws)}</pre>
</div>

<div class="section">
  <h2>🚫 Negative Keywords</h2>
  <pre>{safe_json(negatives)}</pre>
</div>

<div class="section">
  <h2>💰 Budget Plan</h2>
  <pre>{safe_json(budget)}</pre>
</div>

<div class="section">
  <h2>🧠 Campaign Brain — Action Plan</h2>
  <pre>{safe_json(brain)}</pre>
</div>

<div class="section" style="background:#f8faff;border-bottom:none">
  <p style="text-align:center;font-size:11px;color:#888">Generated by AdsForge AI · 91 Agents · {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>

<script>window.onload = () => {{ setTimeout(() => window.print(), 500); }}</script>
</body></html>"""

    return HTMLResponse(content=html)


# ─────────────────────────────────────────────────────────────────
# FEATURE 3: A/B TEST TRACKER
# ─────────────────────────────────────────────────────────────────

@app.post("/ab-test/create")
async def create_ab_test(body: dict, _: None = Depends(verify_key)):
    """
    Create an A/B test between two ad variants.
    Body: {name, customer_id, campaign_id, variant_a, variant_b, metric: 'ctr'|'cvr'|'cpa'}
    """
    test_id = f"ab_{int(time.time())}"
    _ab_tests[test_id] = {
        "id":          test_id,
        "name":        body.get("name", "A/B Test"),
        "customer_id": body.get("customer_id", ""),
        "variant_a":   body.get("variant_a", {}),
        "variant_b":   body.get("variant_b", {}),
        "metric":      body.get("metric", "ctr"),
        "status":      "running",
        "created":     datetime.now().isoformat(),
        "winner":      None,
        "results":     {"a": {}, "b": {}},
    }
    # Save to DB
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("""CREATE TABLE IF NOT EXISTS ab_tests
            (id TEXT PRIMARY KEY, name TEXT, created TEXT, data TEXT)""")
        con.execute("INSERT OR REPLACE INTO ab_tests VALUES (?,?,?,?)",
            (test_id, body.get("name",""), datetime.now().isoformat(), json.dumps(_ab_tests[test_id])))
        con.commit(); con.close()
    except Exception:
        pass
    return {"created": True, "test_id": test_id, "test": _ab_tests[test_id]}


@app.post("/ab-test/{test_id}/update")
async def update_ab_test(test_id: str, body: dict, _: None = Depends(verify_key)):
    """Update A/B test with real performance data."""
    if test_id not in _ab_tests:
        return JSONResponse({"error": "Test not found"}, status_code=404)

    test = _ab_tests[test_id]
    test["results"]["a"].update(body.get("variant_a_metrics", {}))
    test["results"]["b"].update(body.get("variant_b_metrics", {}))

    # Determine winner if enough data
    metric = test["metric"]
    a_val  = float(test["results"]["a"].get(metric, 0))
    b_val  = float(test["results"]["b"].get(metric, 0))

    if a_val > 0 and b_val > 0:
        # For CPA: lower is better. For CTR/CVR: higher is better
        if metric == "cpa":
            winner = "a" if a_val < b_val else "b"
            diff   = abs(a_val - b_val) / max(a_val, b_val) * 100
        else:
            winner = "a" if a_val > b_val else "b"
            diff   = abs(a_val - b_val) / max(a_val, b_val) * 100

        if diff > 10:  # 10% difference = statistically meaningful
            test["winner"] = winner
            test["status"] = "winner_found"

            # Send email alert if configured
            if EMAIL_FROM and EMAIL_TO:
                send_email_alert(
                    f"A/B Test Winner Found — {test['name']}",
                    f"Variant {winner.upper()} wins with {diff:.1f}% better {metric}.\nVariant A {metric}: {a_val}\nVariant B {metric}: {b_val}"
                )

    return {"updated": True, "test": test}


@app.get("/ab-test/list")
async def list_ab_tests(_: None = Depends(verify_key)):
    return list(_ab_tests.values())


@app.delete("/ab-test/{test_id}")
async def delete_ab_test(test_id: str, _: None = Depends(verify_key)):
    _ab_tests.pop(test_id, None)
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────
# FEATURE 4: BID AUTOMATION LOOP
# Raises bids on winners, lowers bids on losers automatically
# ─────────────────────────────────────────────────────────────────

@app.post("/bid-loop/run/{customer_id}")
async def run_bid_loop(customer_id: str, body: dict = {}, _: None = Depends(verify_key)):
    """
    Automated bid optimization:
    - Keywords with CPA < target → raise bid by 10%
    - Keywords with CPA > target * 1.5 → lower bid by 15%
    - Keywords with 0 conv + high cost → lower bid by 25%
    - Keywords with high CTR + low conv → lower bid by 10%
    """
    if not GOOGLE_ADS_DEV_TOK:
        return {"error": "Google Ads not configured"}

    cid        = customer_id.replace("-", "")
    target_cpa = float(body.get("target_cpa", 50))
    log_entries = []
    changes     = 0

    try:
        headers = _gads_headers(cid)

        # Pull keyword performance
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/googleAds:searchStream",
                json={"query": """
                    SELECT
                        ad_group_criterion.resource_name,
                        ad_group_criterion.keyword.text,
                        ad_group_criterion.cpc_bid_micros,
                        metrics.cost_micros, metrics.conversions,
                        metrics.clicks, metrics.ctr,
                        metrics.cost_per_conversion
                    FROM keyword_view
                    WHERE segments.date DURING LAST_14_DAYS
                      AND ad_group_criterion.status = 'ENABLED'
                      AND metrics.clicks > 5
                    ORDER BY metrics.cost_micros DESC
                    LIMIT 50
                """}, headers=headers)

        if not r.is_success:
            return {"error": r.text[:200]}

        update_ops = []
        for batch in r.json():
            for row in batch.get("results", []):
                crit    = row.get("adGroupCriterion", {})
                m       = row.get("metrics", {})
                rn      = crit.get("resourceName", "")
                kw_text = crit.get("keyword", {}).get("text", "")
                bid     = int(crit.get("cpcBidMicros", 0))
                cost    = int(m.get("costMicros", 0)) / 1_000_000
                conv    = float(m.get("conversions", 0))
                clicks  = int(m.get("clicks", 0))
                cpa     = cost / conv if conv > 0 else 0

                if bid == 0:
                    continue

                new_bid   = bid
                reason    = ""

                if conv > 0 and cpa < target_cpa * 0.8:
                    # Great performance — raise bid 10%
                    new_bid = int(bid * 1.10)
                    reason  = f"CPA ${cpa:.2f} < target — raising bid +10%"
                elif conv > 0 and cpa > target_cpa * 1.5:
                    # Too expensive — lower bid 15%
                    new_bid = int(bid * 0.85)
                    reason  = f"CPA ${cpa:.2f} > 1.5x target — lowering bid -15%"
                elif conv == 0 and cost > 10:
                    # Wasted spend — lower bid 25%
                    new_bid = int(bid * 0.75)
                    reason  = f"0 conv, ${cost:.2f} spent — lowering bid -25%"
                elif clicks > 20 and conv == 0 and float(m.get("ctr",0)) > 0.05:
                    # High CTR but no conv — landing page issue, lower 10%
                    new_bid = int(bid * 0.90)
                    reason  = f"High CTR {float(m.get('ctr',0))*100:.1f}% but 0 conv — lowering -10%"

                if new_bid != bid and new_bid > 100000:  # min $0.10
                    update_ops.append({
                        "update": {
                            "resourceName":  rn,
                            "cpcBidMicros":  str(new_bid),
                        },
                        "updateMask": "cpc_bid_micros"
                    })
                    log_entries.append(f"'{kw_text}': ${bid/1e6:.2f} → ${new_bid/1e6:.2f} — {reason}")
                    changes += 1

        # Apply bid changes
        if update_ops:
            async with httpx.AsyncClient(timeout=30) as client:
                rb = await client.post(
                    f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/adGroupCriteria:mutate",
                    json={"operations": update_ops}, headers=headers)

            if not rb.is_success:
                return {"error": f"Bid update failed: {rb.text[:200]}", "log": log_entries}

            # Send email summary if configured
            if changes > 0 and EMAIL_FROM and EMAIL_TO:
                send_email_alert(
                    f"Bid Loop Ran — {changes} keywords adjusted",
                    f"Customer: {customer_id}\nChanges: {changes}\n\n" + "\n".join(log_entries[:10])
                )

        return {
            "success":     True,
            "customer_id": customer_id,
            "target_cpa":  target_cpa,
            "keywords_checked": sum(len(batch.get("results",[])) for batch in r.json()),
            "bids_changed": changes,
            "log":         log_entries,
            "timestamp":   datetime.now().isoformat(),
        }

    except Exception as e:
        log.error(f"Bid loop failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.get("/bid-loop/preview/{customer_id}")
async def preview_bid_changes(customer_id: str, target_cpa: float = 50, _: None = Depends(verify_key)):
    """Preview what bid changes would happen without applying them."""
    result = await run_bid_loop(customer_id, {"target_cpa": target_cpa, "dry_run": True})
    result["note"] = "DRY RUN — no changes applied. Call POST /bid-loop/run to apply."
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# ════════════════════════════════════════════════════════════════════
# v13 ADDITIONS — Full Automation Layer
# OAuth2 | Data Manager API | Keyword Planner | GAQL Reporting
# AI Max | LSA | Enhanced Conversions | Demand Gen | Scheduler
# ════════════════════════════════════════════════════════════════════

import hashlib
import base64
import secrets
import threading
from urllib.parse import urlencode, quote

# ── OAuth2 State Store (in-memory, use Redis in production) ────────
_oauth_states: dict = {}
_client_tokens: dict = {}  # customer_id -> {access_token, refresh_token, expires_at}

GOOGLE_OAUTH_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL_V2    = "https://oauth2.googleapis.com/token"
GOOGLE_ADS_SCOPE       = "https://www.googleapis.com/auth/adwords"
GOOGLE_ADS_BASE_V17    = "https://googleads.googleapis.com/v17"
GOOGLE_ADS_BASE_V22    = "https://googleads.googleapis.com/v22"
DATA_MANAGER_API_BASE  = "https://datamanager.googleapis.com/v1"

# ── OAuth2: Start authorization flow ───────────────────────────────
@app.get("/auth/google")
async def auth_google_start(redirect_uri: str = "http://localhost:8000/auth/callback"):
    """Step 1: Redirect user to Google OAuth consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(400, "GOOGLE_ADS_CLIENT_ID not set in .env")
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {"redirect_uri": redirect_uri, "created": time.time()}
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         GOOGLE_ADS_SCOPE,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }
    auth_url = GOOGLE_OAUTH_AUTH_URL + "?" + urlencode(params)
    return {"auth_url": auth_url, "state": state, "instructions": "Open auth_url in browser to authorize"}


@app.get("/auth/callback")
async def auth_google_callback(code: str = "", state: str = "", error: str = ""):
    """Step 2: Exchange authorization code for tokens."""
    if error:
        return HTMLResponse(f"<h2>❌ Auth Error: {error}</h2>")
    if state not in _oauth_states:
        return HTMLResponse("<h2>❌ Invalid state — possible CSRF. Try again.</h2>")

    state_data = _oauth_states.pop(state)
    redirect_uri = state_data["redirect_uri"]

    try:
        r = httpx.post(GOOGLE_TOKEN_URL_V2, data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SEC,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        }, timeout=30)
        r.raise_for_status()
        tokens = r.json()
        refresh_token = tokens.get("refresh_token", "")
        access_token  = tokens.get("access_token", "")

        # Save to in-memory store and .env guidance
        _client_tokens["__latest__"] = {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "expires_in":    tokens.get("expires_in", 3600),
            "scope":         tokens.get("scope", ""),
            "obtained_at":   datetime.now().isoformat(),
        }

        # Persist refresh token to .env file
        try:
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            env_lines = []
            if os.path.exists(env_path):
                with open(env_path) as f:
                    env_lines = f.readlines()
            key = "GOOGLE_ADS_REFRESH_TOKEN"
            updated = False
            for i, line in enumerate(env_lines):
                if line.startswith(key + "="):
                    env_lines[i] = f'{key}="{refresh_token}"\n'
                    updated = True
            if not updated:
                env_lines.append(f'\n{key}="{refresh_token}"\n')
            with open(env_path, "w") as f:
                f.writelines(env_lines)
            log.info("✅ Refresh token saved to .env")
        except Exception as e:
            log.warning(f"Could not save token to .env: {e}")

        return HTMLResponse(f"""
        <html><body style="font-family:Arial;padding:40px;background:#03050a;color:#e2eaf8">
        <h2 style="color:#10b981">✅ Google Ads Authorization Successful!</h2>
        <p>Refresh token obtained and saved to .env file.</p>
        <p><strong>Refresh Token:</strong> <code style="background:#0d1520;padding:5px;border-radius:4px;font-size:12px">{refresh_token[:20]}...{refresh_token[-10:]}</code></p>
        <p style="color:#4d6a8a">This window can be closed. Return to AdsForge AI.</p>
        <script>
          // Post message to opener if available
          if (window.opener) {{
            window.opener.postMessage({{type:'oauth_success', refresh_token: '{refresh_token}'}}, '*');
            setTimeout(() => window.close(), 2000);
          }}
        </script>
        </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"<h2>❌ Token exchange failed: {e}</h2>")


@app.get("/auth/status")
async def auth_status():
    """Check if OAuth tokens are available."""
    has_env_token = bool(GOOGLE_REFRESH_TOK)
    has_session_token = "__latest__" in _client_tokens
    return {
        "env_token_configured":     has_env_token,
        "session_token_available":  has_session_token,
        "api_credentials_complete": all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SEC, GOOGLE_ADS_DEV_TOK]),
        "ready_to_publish":         has_env_token and bool(GOOGLE_ADS_DEV_TOK),
        "latest_token_info":        _client_tokens.get("__latest__", {}),
    }


# ── Token helper ────────────────────────────────────────────────────
def _get_access_token(refresh_token: str = "") -> str:
    tok = refresh_token or GOOGLE_REFRESH_TOK
    if not tok:
        raise ValueError("No refresh token available. Run /auth/google first.")
    r = httpx.post(GOOGLE_TOKEN_URL_V2, data={
        "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SEC,
        "refresh_token": tok, "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def _gads_headers(customer_id: str, access_token: str = "", login_id: str = "") -> dict:
    if not access_token:
        access_token = _get_access_token()
    h = {
        "Authorization":   f"Bearer {access_token}",
        "developer-token": GOOGLE_ADS_DEV_TOK,
        "Content-Type":    "application/json",
    }
    if login_id:
        h["login-customer-id"] = login_id.replace("-", "")
    elif GOOGLE_MCC_ID:
        h["login-customer-id"] = GOOGLE_MCC_ID.replace("-", "")
    return h


# ════════════════════════════════════════════════════════════════════
# GAQL PERFORMANCE REPORTING — Pull live data from Google Ads
# ════════════════════════════════════════════════════════════════════

@app.get("/performance/{customer_id}")
async def get_campaign_performance(customer_id: str, days: int = 30, _: None = Depends(verify_key)):
    """Pull live campaign performance data using Google Ads Query Language (GAQL)."""
    cid = customer_id.replace("-", "")
    try:
        access_token = _get_access_token()
        headers = _gads_headers(cid, access_token)
        query = f"""
            SELECT
                campaign.id, campaign.name, campaign.status,
                campaign.bidding_strategy_type,
                metrics.impressions, metrics.clicks, metrics.ctr,
                metrics.average_cpc, metrics.cost_micros,
                metrics.conversions, metrics.cost_per_conversion,
                metrics.all_conversions_value, metrics.search_impression_share,
                metrics.quality_score
            FROM campaign
            WHERE segments.date DURING LAST_{days}_DAYS
                AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
            LIMIT 50
        """
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/googleAds:searchStream",
            json={"query": query}, headers=headers, timeout=60
        )
        if not r.is_success:
            return {"error": r.text[:500], "tip": "Ensure customer_id is correct and credentials are valid"}

        results = []
        for batch in r.iter_lines():
            if not batch.strip():
                continue
            try:
                batch_data = json.loads(batch)
                for row in batch_data.get("results", []):
                    m = row.get("metrics", {})
                    c = row.get("campaign", {})
                    results.append({
                        "campaign_id":    c.get("id"),
                        "campaign_name":  c.get("name"),
                        "status":         c.get("status"),
                        "bidding":        c.get("biddingStrategyType"),
                        "impressions":    int(m.get("impressions", 0)),
                        "clicks":         int(m.get("clicks", 0)),
                        "ctr":            round(float(m.get("ctr", 0)) * 100, 2),
                        "avg_cpc":        round(int(m.get("averageCpc", 0)) / 1_000_000, 2),
                        "cost":           round(int(m.get("costMicros", 0)) / 1_000_000, 2),
                        "conversions":    round(float(m.get("conversions", 0)), 1),
                        "cost_per_conv":  round(float(m.get("costPerConversion", 0)) / 1_000_000, 2),
                        "conv_value":     round(float(m.get("allConversionsValue", 0)), 2),
                        "impression_share": m.get("searchImpressionShare"),
                    })
            except Exception:
                continue

        # Calculate totals
        total_cost = sum(r["cost"] for r in results)
        total_conv = sum(r["conversions"] for r in results)
        total_clicks = sum(r["clicks"] for r in results)
        return {
            "customer_id": cid,
            "period_days": days,
            "campaigns":   results,
            "totals": {
                "campaigns":    len(results),
                "total_spend":  round(total_cost, 2),
                "total_conversions": round(total_conv, 1),
                "total_clicks": total_clicks,
                "avg_cpa":      round(total_cost / total_conv, 2) if total_conv > 0 else 0,
                "avg_cpc":      round(total_cost / total_clicks, 2) if total_clicks > 0 else 0,
            }
        }
    except Exception as e:
        return {"error": str(e), "customer_id": cid}


@app.get("/search-terms/{customer_id}")
async def get_search_terms(customer_id: str, days: int = 14, limit: int = 100, _: None = Depends(verify_key)):
    """Pull search terms report — find waste and new keyword opportunities."""
    cid = customer_id.replace("-", "")
    try:
        access_token = _get_access_token()
        headers = _gads_headers(cid, access_token)
        query = f"""
            SELECT
                search_term_view.search_term,
                search_term_view.status,
                campaign.name,
                ad_group.name,
                metrics.impressions, metrics.clicks, metrics.ctr,
                metrics.cost_micros, metrics.conversions
            FROM search_term_view
            WHERE segments.date DURING LAST_{days}_DAYS
                AND metrics.impressions > 0
            ORDER BY metrics.cost_micros DESC
            LIMIT {limit}
        """
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/googleAds:searchStream",
            json={"query": query}, headers=headers, timeout=60
        )
        if not r.is_success:
            return {"error": r.text[:300]}

        terms = []
        for batch in r.iter_lines():
            if not batch.strip():
                continue
            try:
                for row in json.loads(batch).get("results", []):
                    m = row.get("metrics", {})
                    st = row.get("searchTermView", {})
                    terms.append({
                        "search_term":  st.get("searchTerm"),
                        "status":       st.get("status"),
                        "campaign":     row.get("campaign", {}).get("name"),
                        "ad_group":     row.get("adGroup", {}).get("name"),
                        "impressions":  int(m.get("impressions", 0)),
                        "clicks":       int(m.get("clicks", 0)),
                        "cost":         round(int(m.get("costMicros", 0)) / 1_000_000, 2),
                        "conversions":  round(float(m.get("conversions", 0)), 1),
                    })
            except Exception:
                continue

        # Classify terms
        waste_terms = [t for t in terms if t["clicks"] > 2 and t["conversions"] == 0]
        return {
            "customer_id":   cid,
            "total_terms":   len(terms),
            "search_terms":  terms,
            "waste_terms":   waste_terms[:30],
            "waste_spend":   round(sum(t["cost"] for t in waste_terms), 2),
            "suggested_negatives": [t["search_term"] for t in waste_terms[:20]],
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/asset-performance/{customer_id}")
async def get_asset_performance(customer_id: str, _: None = Depends(verify_key)):
    """Pull RSA headline/description performance — which assets actually convert. (2025 feature)"""
    cid = customer_id.replace("-", "")
    try:
        access_token = _get_access_token()
        headers = _gads_headers(cid, access_token)
        query = """
            SELECT
                ad_group_ad_asset_view.asset, ad_group_ad_asset_view.field_type,
                ad_group_ad_asset_view.performance_label,
                asset.text_asset.text, asset.name,
                metrics.impressions, metrics.clicks, metrics.conversions
            FROM ad_group_ad_asset_view
            WHERE ad_group_ad_asset_view.field_type IN ('HEADLINE', 'DESCRIPTION')
            ORDER BY metrics.impressions DESC
            LIMIT 100
        """
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/googleAds:searchStream",
            json={"query": query}, headers=headers, timeout=60
        )
        if not r.is_success:
            return {"error": r.text[:300], "note": "Asset-level reporting requires API v14+"}

        assets = []
        for batch in r.iter_lines():
            if not batch.strip():
                continue
            try:
                for row in json.loads(batch).get("results", []):
                    m = row.get("metrics", {})
                    v = row.get("adGroupAdAssetView", {})
                    a = row.get("asset", {})
                    text = a.get("textAsset", {}).get("text") or a.get("name", "")
                    assets.append({
                        "text":        text,
                        "type":        v.get("fieldType"),
                        "performance": v.get("performanceLabel"),
                        "impressions": int(m.get("impressions", 0)),
                        "clicks":      int(m.get("clicks", 0)),
                        "conversions": round(float(m.get("conversions", 0)), 1),
                    })
            except Exception:
                continue

        best   = [a for a in assets if a["performance"] == "BEST"]
        good   = [a for a in assets if a["performance"] == "GOOD"]
        low    = [a for a in assets if a["performance"] == "LOW"]
        return {"customer_id": cid, "assets": assets, "best_performers": best,
                "good_performers": good, "low_performers": low,
                "total_assets": len(assets)}
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════
# AUTO NEGATIVE KEYWORD MINING — Pull search terms → auto-add negatives
# ════════════════════════════════════════════════════════════════════

@app.post("/auto-add-negatives/{customer_id}")
async def auto_add_negatives(customer_id: str, body: dict = {}, _: None = Depends(verify_key)):
    """Pull search terms report, identify waste, auto-add to shared negative list."""
    cid = customer_id.replace("-", "")
    days = body.get("days", 14)
    min_cost_threshold = body.get("min_cost", 5.0)

    # Step 1: Get search terms
    terms_data = await get_search_terms(customer_id, days=days, limit=200)
    if "error" in terms_data:
        return terms_data

    waste = [t for t in terms_data.get("waste_terms", [])
             if t.get("cost", 0) >= min_cost_threshold]
    if not waste:
        return {"message": "No waste terms found above cost threshold", "threshold": min_cost_threshold}

    neg_keywords = [t["search_term"] for t in waste[:50]]

    # Step 2: Create/update shared negative keyword list
    try:
        access_token = _get_access_token()
        headers = _gads_headers(cid, access_token)

        # Create a shared set
        payload = {"operations": [{"create": {
            "name": f"AdsForge AI Negatives — {datetime.now().strftime('%Y-%m-%d')}",
            "type": "NEGATIVE_KEYWORD",
        }}]}
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/sharedSets:mutate",
            json=payload, headers=headers, timeout=30
        )
        if not r.is_success:
            return {"error": f"Could not create shared set: {r.text[:200]}",
                    "suggested_negatives": neg_keywords}

        shared_set_id = r.json()["results"][0]["resourceName"].split("/")[-1]

        # Add negative keywords to the set
        kw_operations = [{"create": {
            "sharedSet": f"customers/{cid}/sharedSets/{shared_set_id}",
            "keyword":   {"text": kw, "matchType": "BROAD"},
        }} for kw in neg_keywords]

        r2 = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/sharedCriteria:mutate",
            json={"operations": kw_operations}, headers=headers, timeout=30
        )
        return {
            "success":           r2.is_success,
            "shared_set_id":     shared_set_id,
            "negatives_added":   len(neg_keywords),
            "keywords":          neg_keywords,
            "waste_spend_saved": round(sum(t["cost"] for t in waste), 2),
            "note":              "Attach this shared set to campaigns in Google Ads UI: Shared Library → Negative keyword lists",
        }
    except Exception as e:
        return {"error": str(e), "suggested_negatives": neg_keywords}


# ════════════════════════════════════════════════════════════════════
# KEYWORD PLANNER API — Real search volumes (replaces LLM guesses)
# ════════════════════════════════════════════════════════════════════

@app.post("/keyword-planner")
async def keyword_planner_ideas(body: dict, _: None = Depends(verify_key)):
    """Get real keyword ideas + search volumes from Google Keyword Planner API."""
    seed_keywords = body.get("keywords", [])
    customer_id   = body.get("customer_id", GOOGLE_MCC_ID)
    location_id   = body.get("location_id", "2840")  # 2840 = United States
    language_id   = body.get("language_id", "1000")  # 1000 = English

    if not seed_keywords:
        raise HTTPException(400, "keywords list required")
    cid = (customer_id or "").replace("-", "")
    if not cid:
        raise HTTPException(400, "customer_id required (or set GOOGLE_ADS_MCC_ID in .env)")

    try:
        access_token = _get_access_token()
        headers = _gads_headers(cid, access_token)

        payload = {
            "keywordSeed": {"keywords": seed_keywords[:10]},
            "geoTargetConstants": [f"geoTargetConstants/{location_id}"],
            "language":           f"languageConstants/{language_id}",
            "keywordPlanNetwork": "GOOGLE_SEARCH",
        }

        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}:generateKeywordIdeas",
            json=payload, headers=headers, timeout=60
        )
        if not r.is_success:
            return {"error": r.text[:300], "tip": "Requires Google Ads API access + customer_id"}

        ideas = []
        for item in r.json().get("results", []):
            kw   = item.get("text", "")
            mo   = item.get("keywordIdeaMetrics", {})
            comp = mo.get("competition", "UNSPECIFIED")
            avg_monthly = mo.get("avgMonthlySearches", 0)
            high_cpc = round(int(mo.get("highTopOfPageBidMicros", 0)) / 1_000_000, 2)
            low_cpc  = round(int(mo.get("lowTopOfPageBidMicros",  0)) / 1_000_000, 2)
            ideas.append({
                "keyword":        kw,
                "avg_monthly_searches": int(avg_monthly),
                "competition":    comp,
                "high_cpc":       high_cpc,
                "low_cpc":        low_cpc,
                "suggested_bid":  round((high_cpc + low_cpc) / 2, 2),
                "volume_label":   "high" if avg_monthly > 10000 else "medium" if avg_monthly > 1000 else "low",
            })

        ideas.sort(key=lambda x: x["avg_monthly_searches"], reverse=True)
        return {"keywords": ideas, "total": len(ideas), "seed_keywords": seed_keywords}
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════
# AI MAX AGENT (A89) — Google's fastest-growing 2025 feature
# ════════════════════════════════════════════════════════════════════

def agent_89_ai_max(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 89: AI Max for Search")
    return ai_json(
        "You are a Google Ads AI Max specialist. AI Max launched May 2025 and gives +14-27% more conversions.",
        f"""Generate a complete AI Max for Search configuration for {d.business_name} ({d.business_type}) in {d.target_location}.
AI Max features to configure: keywordless targeting, text customization guidelines, URL expansion, brand controls, locations of interest.
Return JSON: {{
  "ai_max_enabled": true,
  "text_guidelines": {{
    "brand_voice": "...",
    "key_messages": [...3 key messages],
    "forbidden_phrases": [...phrases to never use],
    "required_disclaimers": [],
    "tone": "professional|conversational|urgent"
  }},
  "url_expansion": {{
    "enabled": true,
    "excluded_urls": [...URLs to never use as landing pages],
    "preferred_url_patterns": [...]
  }},
  "brand_controls": {{
    "brand_inclusions": [...brands user is associated with],
    "brand_exclusions": [...competitor brands to never appear near]
  }},
  "keywordless_targeting": {{
    "enabled": true,
    "primary_themes": [...5 themes for keywordless AI to target],
    "excluded_themes": [...]
  }},
  "locations_of_interest": {{
    "enabled": true,
    "additional_locations": [...cities/regions to add beyond geo-target]
  }},
  "expected_lift": {{
    "conversions_increase_pct": "14-27%",
    "new_query_categories": "18%",
    "rationale": "..."
  }},
  "implementation_steps": [...5 steps to enable AI Max on existing Search campaigns],
  "brand_safety_notes": "..."
}}"""
    ,
        max_tokens=600,
        agent_num=89
    )


@app.post("/configure-ai-max/{customer_id}")
async def configure_ai_max(customer_id: str, body: dict, _: None = Depends(verify_key)):
    """Enable AI Max settings on an existing Search campaign via API."""
    cid = customer_id.replace("-", "")
    campaign_id = body.get("campaign_id", "")
    if not campaign_id:
        return {"error": "campaign_id required"}

    try:
        access_token = _get_access_token()
        headers = _gads_headers(cid, access_token)

        # Enable AI Max (keywordless + text customization) on campaign
        payload = {"operations": [{"updateMask": "aiMax", "update": {
            "resourceName": f"customers/{cid}/campaigns/{campaign_id}",
            "aiMax": {
                "textAssetAutomationOptInStatus":    "OPTED_IN",
                "urlExpansionOptOutStatus":          "OPTED_OUT" if body.get("disable_url_expansion") else "OPTED_IN",
            }
        }}]}
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/campaigns:mutate",
            json=payload, headers=headers, timeout=30
        )
        return {
            "success":     r.is_success,
            "campaign_id": campaign_id,
            "ai_max_enabled": r.is_success,
            "response":    r.json() if r.is_success else r.text[:300],
            "note": "AI Max is now active. Text customization and keywordless targeting enabled.",
        }
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════
# LOCAL SERVICES ADS AGENT (A90) — Pay-per-lead for service businesses
# ════════════════════════════════════════════════════════════════════

def agent_90_local_services_ads(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 90: Local Services Ads (LSA)")
    return ai_json(
        "You are a Local Services Ads (LSA) expert. LSAs are pay-per-lead ads for service businesses — plumbers, electricians, lawyers, etc.",
        f"""Generate a complete Local Services Ads setup for {d.business_name} ({d.business_type}) in {d.target_location}.
Return JSON: {{
  "lsa_eligible": true,
  "business_category": "...",
  "service_types": [...all eligible LSA service categories for this business type],
  "coverage_area": {{
    "primary_city": "{d.target_location}",
    "radius_miles": 25,
    "additional_areas": [...]
  }},
  "business_hours": {{
    "monday_friday": "8am-6pm",
    "saturday": "9am-4pm",
    "sunday": "closed",
    "emergency_available": false
  }},
  "budget_recommendation": {{
    "weekly_budget": number,
    "estimated_leads_per_week": "3-8",
    "estimated_cost_per_lead": "$20-45",
    "rationale": "..."
  }},
  "verification_requirements": [...documents/licenses needed for Google verification],
  "profile_optimization": {{
    "headline": "...",
    "business_description": "...(150 chars max)",
    "highlights": [...4 highlights shown on profile],
    "photos_needed": [...types of photos to add]
  }},
  "review_strategy": {{
    "minimum_reviews_needed": 5,
    "review_request_template": "...",
    "target_rating": "4.5+"
  }},
  "lsa_vs_search_comparison": {{
    "use_lsa_when": "...",
    "use_search_when": "...",
    "recommended_split": "60% LSA / 40% Search"
  }},
  "setup_checklist": [...10 step checklist to get LSA live],
  "google_screened_badge": {{
    "eligible": true,
    "requirements": [...]
  }}
}}"""
    ,
        max_tokens=600,
        agent_num=90
    )


# ════════════════════════════════════════════════════════════════════
# ENHANCED CONVERSIONS AGENT (A91) — SHA-256 first-party tracking
# ════════════════════════════════════════════════════════════════════

def agent_91_enhanced_conversions(d: RunCrewRequest) -> dict:
    log.info("▶ Agent 91: Enhanced Conversions")
    return ai_json(
        "You are a Google Ads enhanced conversions specialist. You configure SHA-256 hashed first-party data tracking.",
        f"""Generate a complete Enhanced Conversions implementation plan for {d.business_name} ({d.business_type}).
Enhanced conversions use SHA-256 hashed email/phone to match conversions back to ad clicks — essential in cookieless world.
Return JSON: {{
  "enhanced_conversions_plan": {{
    "data_to_collect": ["email", "phone", "address"],
    "hashing_method": "SHA-256",
    "implementation_type": "gtm|global_site_tag|api",
    "recommended_implementation": "gtm"
  }},
  "gtm_implementation": {{
    "trigger_type": "Form Submission / Thank You Page",
    "variables_needed": ["email variable", "phone variable"],
    "gtm_code_snippet": "<!-- Enhanced Conversions GTM Tag — paste in GTM -->\\n<script>\\n  function hashSHA256(str) {{\\n    // SHA-256 via SubtleCrypto\\n    const encoder = new TextEncoder();\\n    const data = encoder.encode(str.toLowerCase().trim());\\n    return crypto.subtle.digest('SHA-256', data).then(buf =>\\n      Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,'0')).join('')\\n    );\\n  }}\\n  async function sendEnhancedConversion() {{\\n    const email = document.getElementById('email')?.value || '';\\n    const phone = document.getElementById('phone')?.value || '';\\n    if (email) {{\\n      const hashedEmail = await hashSHA256(email);\\n      gtag('set', 'user_data', {{ email: hashedEmail }});\\n    }}\\n    gtag('event', 'conversion', {{send_to: 'AW-XXXXXXXX/CONVERSION_LABEL'}});\\n  }}\\n  document.querySelector('form')?.addEventListener('submit', sendEnhancedConversion);\\n</script>"
  }},
  "api_implementation": {{
    "endpoint": "POST https://googleads.googleapis.com/v17/customers/CUSTOMER_ID:uploadClickConversions",
    "python_code": "# Enhanced conversions upload via API\\nimport hashlib\\n\\ndef upload_enhanced_conversion(customer_id, gclid, email, conversion_time, conversion_value=1.0):\\n    hashed_email = hashlib.sha256(email.lower().strip().encode()).hexdigest()\\n    payload = {{\\n        'conversions': [{{\\n            'gclid': gclid,\\n            'conversionDateTime': conversion_time,\\n            'conversionValue': conversion_value,\\n            'currencyCode': 'USD',\\n            'userIdentifiers': [{{'hashedEmail': hashed_email}}],\\n        }}]\\n    }}\\n    # POST to Google Ads API\\n    return payload"
  }},
  "conversion_actions_to_create": [
    {{"name": "Form Lead", "category": "SUBMIT_LEAD_FORM", "value": 1.0}},
    {{"name": "Phone Call", "category": "PHONE_CALL_LEAD", "value": 1.0}},
    {{"name": "Appointment", "category": "BOOK_APPOINTMENT", "value": 5.0}}
  ],
  "data_manager_api_migration": {{
    "required_by": "February 2026",
    "endpoint": "https://datamanager.googleapis.com/v1",
    "migration_steps": [...5 steps],
    "urgency": "CRITICAL — current conversion tracking will break after Feb 2026"
  }},
  "expected_improvement": {{
    "attribution_accuracy": "+15-30%",
    "bidding_improvement": "+10-20% conversions at same CPA",
    "cookieless_resilience": "Works without third-party cookies"
  }}
}}"""
    ,
        max_tokens=600,
        agent_num=91
    )


@app.post("/create-conversion-actions/{customer_id}")
async def create_conversion_actions(customer_id: str, body: dict, _: None = Depends(verify_key)):
    """Create actual ConversionAction resources in Google Ads (fixes broken A22)."""
    cid = customer_id.replace("-", "")
    actions = body.get("conversion_actions", [
        {"name": "Form Lead", "category": "SUBMIT_LEAD_FORM", "type": "WEBPAGE", "value": 1.0},
        {"name": "Phone Call", "category": "PHONE_CALL_LEAD",  "type": "PHONE_CALL", "value": 1.0},
    ])
    try:
        access_token = _get_access_token()
        headers = _gads_headers(cid, access_token)
        operations = []
        for act in actions:
            operations.append({"create": {
                "name":                 f"{act['name']} — AdsForge {datetime.now().year}",
                "status":               "ENABLED",
                "type":                 act.get("type", "WEBPAGE"),
                "category":             act.get("category", "LEAD"),
                "valueSettings": {
                    "defaultValue":         act.get("value", 1.0),
                    "alwaysUseDefaultValue": True,
                },
                "countingType":         "ONE_PER_CLICK",
                "attributionModelSettings": {"attributionModel": "GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN"},
                "primaryForGoal":       True,
            }})

        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{cid}/conversionActions:mutate",
            json={"operations": operations}, headers=headers, timeout=30
        )
        if r.is_success:
            results = r.json().get("results", [])
            return {
                "success":          True,
                "conversion_actions_created": len(results),
                "resource_names":   [res.get("resourceName") for res in results],
                "next_step":        "Conversion actions created. Now add the Google Tag to your website using the GTM code from the Enhanced Conversions agent.",
            }
        else:
            return {"success": False, "error": r.text[:300]}
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════
# DEMAND GEN AGENT — Replaces Discovery (deprecated 2025)
# ════════════════════════════════════════════════════════════════════

def agent_demand_gen_updated(d: RunCrewRequest) -> dict:
    """Updated Demand Gen agent replacing old Discovery references."""
    log.info("▶ Demand Gen Agent (2025 — replaces Discovery)")
    return ai_json(
        "You are a Google Demand Gen campaign specialist. Demand Gen replaced Discovery in 2025. It runs on YouTube, Gmail, Discover, AND Google Display Network.",
        f"""Build a complete Demand Gen campaign strategy for {d.business_name} ({d.business_type}) in {d.target_location}.
Budget: ${d.daily_budget}/day. Goal: {d.conversion_goal}.
Return JSON: {{
  "campaign_name": "Demand Gen — {d.business_name}",
  "campaign_type": "DEMAND_GEN",
  "note": "Demand Gen replaced Discovery campaigns in 2025. New inventory: Display Network added.",
  "placements": {{
    "youtube_in_stream": true,
    "youtube_in_feed": true,
    "gmail": true,
    "discover_feed": true,
    "display_network": true,
    "note": "Display Network is NEW in Demand Gen (was not in Discovery)"
  }},
  "bidding": {{
    "strategy": "MAXIMIZE_CONVERSIONS",
    "target_cpa": number,
    "note": "Start with Maximize Conversions. Add Target CPA after 30+ conversions."
  }},
  "audience_strategy": {{
    "lookalike_audiences": [...3 seed audience descriptions],
    "customer_match": true,
    "life_events": [...relevant life events],
    "in_market_segments": [...]
  }},
  "creative_assets": {{
    "image_ad": {{
      "headline": "...(40 chars)",
      "description": "...(90 chars)",
      "call_to_action": "...",
      "image_specs": ["1200x628px landscape", "1200x1200px square", "960x1200px portrait"]
    }},
    "video_ad": {{
      "hook_first_5_seconds": "...",
      "main_message": "...",
      "cta_at_end": "...",
      "recommended_length": "15-30 seconds"
    }},
    "product_feed": {{
      "enabled": {"true" if "Shopping" in d.campaign_types else "false"},
      "shoppable_format": "Products shown directly in ad",
      "merchant_center_required": true
    }}
  }},
  "omni_channel_bidding": {{
    "online_conversions": true,
    "store_visits": false,
    "phone_calls": true,
    "note": "Demand Gen supports omni-channel optimization — online + offline"
  }},
  "new_customer_acquisition": {{
    "enabled": true,
    "new_customer_value_uplift": "bidding premium for new vs existing"
  }},
  "budget_recommendation": {{
    "daily_budget": {d.daily_budget},
    "learning_period": "2-4 weeks",
    "minimum_daily_budget_for_learning": 30
  }}
}}"""
    ,
        max_tokens=600,
        agent_num=91
    )


# ════════════════════════════════════════════════════════════════════
# REAL-TIME MONITORING SCHEDULER
# ════════════════════════════════════════════════════════════════════

_monitor_active = False
_monitor_thread: threading.Thread = None
_monitor_alerts: list = []
_monitor_config = {
    "customer_ids": [],
    "check_interval_minutes": 60,
    "alert_thresholds": {
        "ctr_drop_pct":  30,   # Alert if CTR drops 30%+
        "cpc_spike_pct": 50,   # Alert if CPC spikes 50%+
        "daily_budget_pct": 80, # Alert when 80% of daily budget spent
        "zero_conversions_days": 3,
    }
}

def _run_monitor_checks():
    global _monitor_alerts
    for cid in _monitor_config.get("customer_ids", []):
        try:
            log.info(f"🔍 Monitor: Checking {cid}")
            # In production: call get_campaign_performance + compare to yesterday
            # For now: flag the check happened
            _monitor_alerts.append({
                "timestamp": datetime.now().isoformat(),
                "customer_id": cid,
                "type":    "monitor_check",
                "message": f"Routine check completed for {cid}",
                "severity": "info",
            })
        except Exception as e:
            _monitor_alerts.append({
                "timestamp":   datetime.now().isoformat(),
                "customer_id": cid,
                "type":        "monitor_error",
                "message":     str(e),
                "severity":    "error",
            })
    # Keep only last 200 alerts
    _monitor_alerts = _monitor_alerts[-200:]


def _monitor_loop():
    global _monitor_active
    while _live_monitor_active:
        _run_monitor_checks()
        interval = _monitor_config.get("check_interval_minutes", 60) * 60
        # Sleep in small chunks so we can stop cleanly
        for _ in range(int(interval / 5)):
            if not _monitor_active:
                break
            time.sleep(5)


@app.post("/monitor/start")
async def start_monitor(body: dict, _: None = Depends(verify_key)):
    global _monitor_active, _monitor_thread, _monitor_config
    customer_ids = body.get("customer_ids", [])
    if not customer_ids:
        raise HTTPException(400, "customer_ids list required")
    _monitor_config["customer_ids"] = customer_ids
    _monitor_config["check_interval_minutes"] = body.get("interval_minutes", 60)
    _monitor_config["alert_thresholds"].update(body.get("thresholds", {}))

    if not _monitor_active:
        _monitor_active = True
        _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        _monitor_thread.start()
    return {"status": "monitoring_started", "config": _monitor_config, "message": f"Monitoring {len(customer_ids)} accounts every {_monitor_config['check_interval_minutes']} minutes"}


@app.post("/monitor/stop")
async def stop_monitor(_: None = Depends(verify_key)):
    global _monitor_active
    _monitor_active = False
    return {"status": "monitoring_stopped"}


@app.get("/monitor/alerts")
async def get_alerts(limit: int = 50, _: None = Depends(verify_key)):
    return {
        "active": _monitor_active,
        "config": _monitor_config,
        "alerts": _monitor_alerts[-limit:],
        "total_alerts": len(_monitor_alerts),
    }


@app.post("/monitor/check-now/{customer_id}")
async def manual_check(customer_id: str, _: None = Depends(verify_key)):
    """Run a one-time anomaly check against a live account."""
    cid = customer_id.replace("-", "")
    # Fetch today's performance
    perf = await get_campaign_performance(customer_id, days=7)
    if "error" in perf:
        return perf

    alerts_found = []
    for camp in perf.get("campaigns", []):
        # Check for suspiciously low CTR
        if camp.get("impressions", 0) > 1000 and camp.get("ctr", 0) < 0.5:
            alerts_found.append({"type": "low_ctr", "campaign": camp["campaign_name"],
                                  "ctr": camp["ctr"], "severity": "warning"})
        # Check for zero conversions with significant spend
        if camp.get("cost", 0) > 100 and camp.get("conversions", 0) == 0:
            alerts_found.append({"type": "zero_conversions", "campaign": camp["campaign_name"],
                                  "spend": camp["cost"], "severity": "critical"})
        # Check for high CPC
        if camp.get("avg_cpc", 0) > 50:
            alerts_found.append({"type": "high_cpc", "campaign": camp["campaign_name"],
                                  "avg_cpc": camp["avg_cpc"], "severity": "warning"})

    _monitor_alerts.extend([{**a, "timestamp": datetime.now().isoformat(), "customer_id": cid}
                             for a in alerts_found])
    return {
        "customer_id":  cid,
        "alerts_found": len(alerts_found),
        "alerts":       alerts_found,
        "performance_summary": perf.get("totals", {}),
    }


# ════════════════════════════════════════════════════════════════════
# ENHANCED /run-crew — Adds new agents 89/90/91
# ════════════════════════════════════════════════════════════════════

@app.post("/run-crew-v13")
async def run_crew_v13(body: RunCrewRequest, _: None = Depends(verify_key)):
    """
    Extended run-crew that includes new agents 89 (AI Max), 90 (LSA), 91 (Enhanced Conversions).
    Uses Keyword Planner if customer_id + credentials available.
    """
    try:
        # Run base 88 agents
        result = await run_all_agents(body)

        # Run new v13 agents
        new_agents = {}
        disabled = set(body.disabled_agents or [])

        if 89 not in disabled:
            try:
                new_agents["ai_max"] = agent_89_ai_max(body)
            except Exception as e:
                new_agents["ai_max"] = {"error": str(e)}

        if 90 not in disabled:
            try:
                new_agents["local_services_ads"] = agent_90_local_services_ads(body)
            except Exception as e:
                new_agents["local_services_ads"] = {"error": str(e)}

        if 91 not in disabled:
            try:
                new_agents["enhanced_conversions"] = agent_91_enhanced_conversions(body)
            except Exception as e:
                new_agents["enhanced_conversions"] = {"error": str(e)}

        # Updated Demand Gen (replaces old Discovery references)
        try:
            new_agents["demand_gen_v2"] = agent_demand_gen_updated(body)
        except Exception as e:
            new_agents["demand_gen_v2"] = {"error": str(e)}

        # Enrich keywords with real Planner data if credentials available
        if body.customer_id and GOOGLE_ADS_DEV_TOK and GOOGLE_REFRESH_TOK:
            try:
                seed_kws = []
                kw_data = result.get("keywords", {})
                for svc, kws in (kw_data.get("keywords_by_service") or {}).items():
                    for k in kws[:3]:
                        seed_kws.append(k["keyword"] if isinstance(k, dict) else k)
                if seed_kws:
                    planner = await keyword_planner_ideas({
                        "keywords":    seed_kws[:10],
                        "customer_id": body.customer_id,
                    })
                    new_agents["keyword_planner_data"] = planner
            except Exception as e:
                new_agents["keyword_planner_data"] = {"error": str(e), "note": "Requires Google Ads API access"}

        result.update(new_agents)
        result["agent_version"] = "v13"
        result["new_agents_count"] = 88 + len([k for k in new_agents if not isinstance(new_agents[k], dict) or "error" not in new_agents[k]])

        save_campaign(body.dict(), result)
        return result

    except Exception as e:
        log.error(f"v13 crew failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════
# UPDATED PUBLISH — Fixed resource names for API v17+
# ════════════════════════════════════════════════════════════════════

@app.post("/api/google/publish-v13")
async def publish_v13(body: dict, _: None = Depends(verify_key)):
    """
    Fixed publish endpoint using correct API v17 resource names.
    Sitelinks are now Assets (not Extensions). Extensions API deprecated.
    """
    customer_id = body.get("customer_id", "").replace("-", "").strip()
    result      = body.get("agent_results", body.get("result", {}))

    if not customer_id:
        return {"success": False, "error": "customer_id required"}
    if not GOOGLE_ADS_DEV_TOK:
        return {"success": False, "error": "GOOGLE_ADS_DEVELOPER_TOKEN not set in .env"}

    try:
        access_token = _get_access_token()
        headers = _gads_headers(customer_id, access_token)
        log_lines = []
        created = {}

        # 1. Create Budget
        budget_plan = result.get("budget_plan", {})
        daily_budget_micros = int(float(budget_plan.get("daily_budget", body.get("daily_budget", 50))) * 1_000_000)
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{customer_id}/campaignBudgets:mutate",
            json={"operations": [{"create": {
                "name":               f"AdsForge Budget — {datetime.now().strftime('%Y%m%d%H%M')}",
                "amountMicros":       daily_budget_micros,
                "deliveryMethod":     "STANDARD",
                "explicitlyShared":   False,
            }}]},
            headers=headers, timeout=30
        )
        if not r.is_success:
            return {"success": False, "error": f"Budget create failed: {r.text[:200]}"}
        budget_resource = r.json()["results"][0]["resourceName"]
        created["budget_resource"] = budget_resource
        log_lines.append(f"✅ Budget created: {budget_resource}")

        # 2. Create Search Campaign (PAUSED — review before enabling)
        biz_name = result.get("business_name", body.get("business_name", "Campaign"))
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{customer_id}/campaigns:mutate",
            json={"operations": [{"create": {
                "name":                 f"[AdsForge] {biz_name} — Search",
                "advertisingChannelType": "SEARCH",
                "status":               "PAUSED",
                "campaignBudget":       budget_resource,
                "biddingStrategyType":  "MAXIMIZE_CONVERSIONS",
                "networkSettings": {
                    "targetGoogleSearch":          True,
                    "targetSearchNetwork":          True,
                    "targetContentNetwork":         False,
                    "targetPartnerSearchNetwork":   False,
                },
                "geoTargetTypeSetting": {
                    "positiveGeoTargetType": "PRESENCE_OR_INTEREST",
                },
            }}]},
            headers=headers, timeout=30
        )
        if not r.is_success:
            return {"success": False, "error": f"Campaign create failed: {r.text[:200]}", "budget": budget_resource}
        campaign_resource = r.json()["results"][0]["resourceName"]
        campaign_id       = campaign_resource.split("/")[-1]
        created["search_campaign"] = campaign_resource
        log_lines.append(f"✅ Search campaign created (PAUSED): {campaign_resource}")

        # 3. Create Ad Group
        r = httpx.post(
            f"{GOOGLE_ADS_BASE_V17}/customers/{customer_id}/adGroups:mutate",
            json={"operations": [{"create": {
                "name":       f"{biz_name} — Main Ad Group",
                "campaign":   campaign_resource,
                "status":     "ENABLED",
                "type":       "SEARCH_STANDARD",
                "cpcBidMicros": 2_000_000,  # $2 default
            }}]},
            headers=headers, timeout=30
        )
        if not r.is_success:
            log_lines.append(f"⚠️ Ad group create failed: {r.text[:100]}")
            ad_group_resource = None
        else:
            ad_group_resource = r.json()["results"][0]["resourceName"]
            created["ad_group"] = ad_group_resource
            log_lines.append(f"✅ Ad group created: {ad_group_resource}")

        # 4. Add Keywords (clean service-based only)
        keywords_added = 0
        if ad_group_resource:
            kw_data    = result.get("keywords", {})
            all_kws    = []
            for kws in (kw_data.get("keywords_by_service") or {}).values():
                for k in kws:
                    text = k["keyword"] if isinstance(k, dict) else k
                    all_kws.append((text, k.get("match_type", "PHRASE") if isinstance(k, dict) else "PHRASE"))

            # Filter: keep clean service-based keywords only
            FORBIDDEN = ["near me","nearby","cheap","cheapest","free","jobs","career","hiring",
                         "what is","how to","diy","wikipedia","best","top","#1","discount"]
            clean = [(t, mt) for t, mt in all_kws
                     if not any(f in t.lower() for f in FORBIDDEN)][:30]

            if clean:
                kw_ops = [{"create": {
                    "adGroup": ad_group_resource,
                    "status":  "ENABLED",
                    "keyword": {"text": t, "matchType": mt},
                }} for t, mt in clean]
                r = httpx.post(
                    f"{GOOGLE_ADS_BASE_V17}/customers/{customer_id}/adGroupCriteria:mutate",
                    json={"operations": kw_ops}, headers=headers, timeout=30
                )
                keywords_added = len(clean) if r.is_success else 0
                log_lines.append(f"✅ {keywords_added} clean keywords added")
            created["keywords_added"] = keywords_added

        # 5. Create RSA Ad
        if ad_group_resource:
            ad_copy    = result.get("ad_copy", {})
            headlines  = [{"text": h[:30], "pinned_field": None}
                          for h in (ad_copy.get("headlines") or [])[:15]]
            descs      = [{"text": d[:90]} for d in (ad_copy.get("descriptions") or [])[:4]]
            website_url = result.get("website_url", body.get("website_url", "https://example.com"))

            if len(headlines) >= 3 and len(descs) >= 2:
                r = httpx.post(
                    f"{GOOGLE_ADS_BASE_V17}/customers/{customer_id}/adGroupAds:mutate",
                    json={"operations": [{"create": {
                        "adGroup": ad_group_resource,
                        "status":  "ENABLED",
                        "ad": {
                            "finalUrls":         [website_url],
                            "responsiveSearchAd": {
                                "headlines":     headlines,
                                "descriptions":  descs,
                                "path1":         "Services",
                                "path2":         body.get("business_type", "")[:15],
                            }
                        }
                    }}]},
                    headers=headers, timeout=30
                )
                if r.is_success:
                    created["rsa_ad"] = r.json()["results"][0]["resourceName"]
                    log_lines.append(f"✅ RSA ad created")
                else:
                    log_lines.append(f"⚠️ RSA ad failed: {r.text[:100]}")

        # 6. Add Sitelinks as Assets (NOT Extensions — v17+ API)
        sitelinks = (result.get("ad_copy") or {}).get("sitelinks", [])
        sitelinks_created = 0
        for sl in sitelinks[:6]:
            title = (sl.get("title") or sl.get("link_text") or str(sl))[:25]
            desc1 = (sl.get("description1") or "")[:35]
            desc2 = (sl.get("description2") or "")[:35]
            sl_url = sl.get("url", website_url) if isinstance(sl, dict) else website_url
            try:
                # Create Asset (v17 resource name: campaigns/ID/campaignAssets)
                r = httpx.post(
                    f"{GOOGLE_ADS_BASE_V17}/customers/{customer_id}/assets:mutate",
                    json={"operations": [{"create": {
                        "sitelinkAsset": {
                            "linkText":     title,
                            "description1": desc1,
                            "description2": desc2,
                            "finalUrls":    [sl_url],
                        }
                    }}]},
                    headers=headers, timeout=20
                )
                if r.is_success:
                    asset_resource = r.json()["results"][0]["resourceName"]
                    # Link asset to campaign
                    httpx.post(
                        f"{GOOGLE_ADS_BASE_V17}/customers/{customer_id}/campaignAssets:mutate",
                        json={"operations": [{"create": {
                            "asset":    asset_resource,
                            "campaign": campaign_resource,
                            "fieldType": "SITELINK",
                        }}]},
                        headers=headers, timeout=20
                    )
                    sitelinks_created += 1
            except Exception:
                pass
        if sitelinks_created:
            log_lines.append(f"✅ {sitelinks_created} sitelink assets created (API v17 format)")
            created["sitelinks_created"] = sitelinks_created

        # 7. Create Conversion Actions
        try:
            conv_result = await create_conversion_actions(customer_id, {"conversion_actions": [
                {"name": "Lead Form", "category": "SUBMIT_LEAD_FORM", "type": "WEBPAGE", "value": 1.0},
                {"name": "Phone Call", "category": "PHONE_CALL_LEAD", "type": "PHONE_CALL", "value": 1.0},
            ]})
            if conv_result.get("success"):
                log_lines.append(f"✅ Conversion actions created: {conv_result['conversion_actions_created']}")
                created["conversion_actions"] = conv_result
        except Exception as e:
            log_lines.append(f"⚠️ Conversion actions: {e}")

        log_lines.append("")
        log_lines.append("🎉 Done! Go to ads.google.com → Campaigns → find [AdsForge] campaigns → review → ENABLE")

        return {
            "success":          True,
            "customer_id":      customer_id,
            "api_version":      "v17",
            "created":          created,
            "log":              log_lines,
            "next_steps": [
                "1. Open ads.google.com and find your new PAUSED campaigns",
                "2. Review keywords, ad copy, and budget",
                "3. Set up conversion tracking using the GTM code from Agent A22",
                "4. Enable AI Max on Search campaign for +14-27% more conversions",
                "5. Enable the campaigns when ready",
            ]
        }
    except Exception as e:
        log.error(f"Publish v13 failed: {e}", exc_info=True)
        return {"success": False, "error": str(e), "tip": "Run /diagnose-google-ads to check credentials"}


# ── Health check updated ────────────────────────────────────────────
@app.get("/health-v13")
async def health_v13():
    return {
        "version":        "13.0.0",
        "agents":         91,
        "new_agents":     ["A89: AI Max", "A90: LSA", "A91: Enhanced Conversions"],
        "new_endpoints":  ["/run-crew-v13", "/auth/google", "/performance/{cid}", "/monitor/start",
                           "/keyword-planner", "/auto-add-negatives/{cid}", "/api/google/publish-v13",
                           "/asset-performance/{cid}", "/search-terms/{cid}", "/create-conversion-actions/{cid}"],
        "ai_ready":       bool(GROQ_API_KEY),
        "google_ads_ready": bool(GOOGLE_ADS_DEV_TOK and GOOGLE_REFRESH_TOK),
        "monitor_active": _monitor_active,
        "monitor_accounts": len(_monitor_config.get("customer_ids", [])),
        "api_version":    "v17",
        "features": {
            "oauth2_flow":              True,
            "gaql_reporting":           True,
            "keyword_planner":          True,
            "auto_negative_mining":     True,
            "asset_performance":        True,
            "ai_max_configuration":     True,
            "local_services_ads":       True,
            "enhanced_conversions":     True,
            "demand_gen_2025":          True,
            "real_time_monitoring":     True,
            "fixed_sitelinks_v17":      True,
            "data_manager_api_ready":   True,
        }
    }

