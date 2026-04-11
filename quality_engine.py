# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║   ADSFORGE AI — QUALITY ENGINE                                  ║
║   The intelligence layer — validates every piece of data        ║
║   before it goes near Google Ads                                ║
╚══════════════════════════════════════════════════════════════════╝

This is what separates good systems from bad ones.
groas.ai's real advantage is not the UI — it's that bad data
never reaches the campaign. This module enforces that.
"""

import re
import json
import logging
from typing import List, Dict, Tuple, Optional

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# SECTION 1: KEYWORD QUALITY RULES
# These are the rules your manager was talking about.
# ─────────────────────────────────────────────────────────────────

# Words that should NEVER appear in keywords.
# Location → handled at campaign geo-targeting level
# Cost/price → goes in ad copy, not keywords
# Superlatives → penalised by Google Quality Score
# These make your Quality Score worse, not better.

# ── KEYWORD QUALITY RULES ─────────────────────────────────────────
# Manager rule: Keywords should be SERVICE-based (what you offer)
# Location keywords like "near me", "local", city names ARE VALID
# Price keywords like "cheap", "affordable" ARE VALID (intent signals)
# Only block: purely informational queries and job seekers

FORBIDDEN_IN_KEYWORDS = {
    # Purely informational — zero purchase intent, add as negatives instead
    "informational": [
        "what is", "what are", "how to", "how do", "how does",
        "why is", "define", "definition", "meaning of",
        "wikipedia", "wiki",
        "diy", "do it yourself", "yourself",
        "tutorial", "explained", "guide for beginners",
    ],

    # Job seekers — completely irrelevant traffic, 100% waste
    "jobs": [
        "jobs", "careers", "hiring", "vacancy", "vacancies",
        "employment", "salary", "salaries", "apply now",
        "apply online", "work from home", "internship",
    ],
}

# NOTE: These are intentionally NOT flagged:
# "near me"    — high-intent local search, valid keyword
# "local"      — describes service type, valid
# "cheap"      — price intent signal, valid
# "affordable" — price intent, valid
# "best"       — valid in many contexts
# City names   — location modifier keywords often convert well
# "quote"      — very high purchase intent signal

# All forbidden words flattened for fast lookup
ALL_FORBIDDEN = set()
for category, words in FORBIDDEN_IN_KEYWORDS.items():
    ALL_FORBIDDEN.update(words)


def validate_keyword(keyword: str) -> Dict:
    """
    Check a single keyword for quality issues.
    Returns: { valid: bool, issues: list, score: int (0-100), fixed: str }
    """
    kw = keyword.lower().strip()
    issues = []
    score = 100

    # Check 1: Forbidden words
    for word in ALL_FORBIDDEN:
        if word in kw:
            # Find which category
            for cat, words in FORBIDDEN_IN_KEYWORDS.items():
                if word in words:
                    issues.append({
                        "type": cat,
                        "word": word,
                        "fix": _get_fix_advice(cat, word),
                    })
                    score -= 30
                    break

    # Check 2: Too short (single word is usually too broad)
    words = kw.split()
    if len(words) == 1:
        issues.append({
            "type": "too_broad",
            "word": kw,
            "fix": f"Add a qualifier. '{kw}' is too broad — try '{kw} service' or '{kw} treatment'",
        })
        score -= 20

    # Check 3: Too long (7+ words = very low volume)
    if len(words) > 6:
        issues.append({
            "type": "too_long",
            "word": kw,
            "fix": "Shorten to 3-5 words for better volume",
        })
        score -= 15

    # City/country checking removed — location keywords ARE valid
    # "electrician brooksville fl" = perfectly valid keyword with high intent

    score = max(0, score)
    return {
        "keyword":   keyword,
        "valid":     len(issues) == 0,
        "score":     score,
        "issues":    issues,
        "fixed":     _auto_fix_keyword(keyword, issues),
    }


def _get_fix_advice(category: str, word: str) -> str:
    fixes = {
        "location":      f"Remove '{word}' — set location in campaign geo-targeting settings",
        "price":         f"Remove '{word}' — put price/offer language in your ad copy or promotion extensions",
        "superlatives":  f"Remove '{word}' — Google penalises superlatives; put this in ad copy instead",
        "informational": f"Remove '{word}' — add it to your NEGATIVE keyword list instead",
        "jobs":          f"Remove '{word}' — add it to your NEGATIVE keyword list to block job seekers",
    }
    return fixes.get(category, f"Remove '{word}' from keyword")


def _auto_fix_keyword(keyword: str, issues: List[Dict]) -> str:
    """Attempt to auto-fix a keyword by removing bad words."""
    fixed = keyword.lower().strip()
    for issue in issues:
        bad_word = issue.get("word", "")
        if bad_word:
            fixed = fixed.replace(bad_word, "").strip()
    # Clean up extra spaces
    fixed = " ".join(fixed.split())
    return fixed if fixed and fixed != keyword.lower() else keyword


def validate_keyword_list(keywords: List) -> Dict:
    """
    Validate a whole list of keywords.
    Returns full quality report.
    """
    results = []
    for kw in keywords:
        text = kw.get("keyword", kw) if isinstance(kw, dict) else str(kw)
        result = validate_keyword(text)
        if isinstance(kw, dict):
            result["match_type"] = kw.get("match_type", "PHRASE")
        results.append(result)

    valid    = [r for r in results if r["valid"]]
    invalid  = [r for r in results if not r["valid"]]
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0

    return {
        "total":         len(results),
        "valid":         len(valid),
        "invalid":       len(invalid),
        "avg_quality_score": round(avg_score),
        "quality_grade": _grade(avg_score),
        "results":       results,
        "clean_keywords": valid,
        "problem_keywords": invalid,
        "auto_fixed":    [r for r in invalid if r["fixed"] != r["keyword"]],
    }


def _grade(score: float) -> str:
    if score >= 90: return "A — Excellent"
    if score >= 75: return "B — Good"
    if score >= 60: return "C — Acceptable"
    if score >= 40: return "D — Needs Work"
    return "F — Major Issues"


# ─────────────────────────────────────────────────────────────────
# SECTION 2: AD COPY VALIDATION
# Google has strict character limits. Exceeding them = disapproval.
# ─────────────────────────────────────────────────────────────────

HEADLINE_MAX    = 30   # characters
DESCRIPTION_MAX = 90   # characters
HEADLINE_MIN    = 3    # at minimum 3 headlines needed
HEADLINE_MAX_N  = 15   # max 15 headlines in RSA
DESC_MIN        = 2    # at minimum 2 descriptions
DESC_MAX_N      = 4    # max 4 descriptions

def validate_ad_copy(headlines: List[str], descriptions: List[str]) -> Dict:
    """
    Validate RSA ad copy against Google's strict requirements.
    This is what prevents disapprovals.
    """
    hl_results = []
    for i, hl in enumerate(headlines):
        hl = str(hl).strip()
        result = {
            "index":      i + 1,
            "text":       hl,
            "length":     len(hl),
            "valid":      len(hl) <= HEADLINE_MAX and len(hl) >= 1,
            "issues":     [],
        }
        if len(hl) > HEADLINE_MAX:
            result["issues"].append(f"Too long ({len(hl)} chars, max {HEADLINE_MAX}). Cut {len(hl) - HEADLINE_MAX} chars.")
            result["fixed"] = hl[:HEADLINE_MAX]
        if "!" in hl and hl.count("!") > 1:
            result["issues"].append("Only 1 exclamation mark allowed per ad (across all headlines).")
        if hl.upper() == hl and len(hl) > 4:
            result["issues"].append("All-caps detected — Google may disapprove this.")
        hl_results.append(result)

    desc_results = []
    for i, desc in enumerate(descriptions):
        desc = str(desc).strip()
        result = {
            "index":      i + 1,
            "text":       desc,
            "length":     len(desc),
            "valid":      len(desc) <= DESCRIPTION_MAX and len(desc) >= 1,
            "issues":     [],
        }
        if len(desc) > DESCRIPTION_MAX:
            result["issues"].append(f"Too long ({len(desc)} chars, max {DESCRIPTION_MAX}). Cut {len(desc) - DESCRIPTION_MAX} chars.")
            result["fixed"] = desc[:DESCRIPTION_MAX]
        desc_results.append(result)

    # Count issues
    hl_issues  = [r for r in hl_results  if r["issues"]]
    desc_issues= [r for r in desc_results if r["issues"]]

    # Auto-fix headlines that are too long
    clean_headlines = []
    for r in hl_results:
        text = r.get("fixed", r["text"])
        if len(text) <= HEADLINE_MAX:
            clean_headlines.append(text)

    # Pad if not enough
    while len(clean_headlines) < HEADLINE_MIN:
        clean_headlines.append("Contact Us Today")

    clean_descriptions = []
    for r in desc_results:
        text = r.get("fixed", r["text"])
        if len(text) <= DESCRIPTION_MAX:
            clean_descriptions.append(text)

    while len(clean_descriptions) < DESC_MIN:
        clean_descriptions.append("Get in touch with our expert team today.")

    return {
        "headline_count":     len(headlines),
        "description_count":  len(descriptions),
        "headline_issues":    len(hl_issues),
        "description_issues": len(desc_issues),
        "headline_results":   hl_results,
        "description_results": desc_results,
        "ready_to_publish":   len(hl_issues) == 0 and len(desc_issues) == 0 and len(headlines) >= HEADLINE_MIN,
        "clean_headlines":    clean_headlines[:HEADLINE_MAX_N],
        "clean_descriptions": clean_descriptions[:DESC_MAX_N],
        "publish_verdict":    "✅ Ready" if len(hl_issues) == 0 and len(desc_issues) == 0 else "❌ Fix issues first",
    }


# ─────────────────────────────────────────────────────────────────
# SECTION 3: CAMPAIGN STRUCTURE VALIDATION
# Are the campaigns set up in a way that will actually work?
# ─────────────────────────────────────────────────────────────────

def validate_campaign_structure(structure: Dict, daily_budget: float) -> Dict:
    """
    Check the campaign structure makes sense before publishing.
    """
    issues = []
    warnings = []
    score = 100

    campaigns = structure.get("campaigns", []) or structure.get("allocation", [])

    # Check 1: Budget is realistic
    if daily_budget < 5:
        issues.append({
            "severity": "critical",
            "issue": f"Daily budget ${daily_budget} is too low",
            "fix": "Minimum recommended budget is $5/day per campaign. Below this, Google won't show ads enough to learn.",
        })
        score -= 40

    if daily_budget < 20:
        warnings.append({
            "severity": "warning",
            "issue": f"${daily_budget}/day is very limited",
            "fix": "For meaningful results, aim for at least $20-30/day. Smart Bidding needs ~50 conversions/month to work properly.",
        })
        score -= 10

    # Check 2: Not too many campaigns for the budget
    num_campaigns = len(campaigns)
    if num_campaigns > 0:
        per_campaign = daily_budget / num_campaigns
        if per_campaign < 5:
            issues.append({
                "severity": "critical",
                "issue": f"${daily_budget}/day split across {num_campaigns} campaigns = ${per_campaign:.2f}/campaign — too little",
                "fix": f"Either increase budget or reduce to {max(1, int(daily_budget/10))} campaigns maximum.",
            })
            score -= 30

    # Check 3: Has Search campaign (required for intent-based keywords)
    has_search = any(
        "search" in str(c.get("type","") + c.get("campaign","") + c.get("name","")).lower()
        for c in campaigns
    )
    if not has_search:
        warnings.append({
            "severity": "warning",
            "issue": "No Search campaign detected",
            "fix": "Add a Search campaign — this is the most important campaign type for intent-based keywords.",
        })
        score -= 20

    # Check 4: Bidding strategy matches conversion data availability
    for camp in campaigns:
        strategy = str(camp.get("bid_strategy","") + camp.get("bidding","")).lower()
        if "target cpa" in strategy or "target_cpa" in strategy:
            warnings.append({
                "severity": "warning",
                "issue": f"Target CPA set from day 1 — this requires conversion history",
                "fix": "Start with Manual CPC or Maximize Clicks for 2-4 weeks to gather data, THEN switch to Target CPA.",
            })
            score -= 10
            break

    return {
        "score":           max(0, score),
        "grade":           _grade(max(0, score)),
        "ready":           score >= 70 and len(issues) == 0,
        "critical_issues": issues,
        "warnings":        warnings,
        "recommendation":  _campaign_recommendation(score, issues, warnings),
    }


def _campaign_recommendation(score, issues, warnings):
    if score >= 90:
        return "✅ Campaign structure looks solid. Safe to publish."
    if score >= 70:
        return f"⚠️ {len(warnings)} warning(s) to review before publishing. Not critical but worth fixing."
    return f"❌ {len(issues)} critical issue(s) must be fixed before publishing to avoid wasted budget."


# ─────────────────────────────────────────────────────────────────
# SECTION 4: FULL AGENT OUTPUT QUALITY CHECK
# Run this on every agent result before saving or publishing
# ─────────────────────────────────────────────────────────────────

def check_agent_output_quality(agent_name: str, result: Dict) -> Dict:
    """
    Check quality of a single agent's output.
    Returns quality score, issues, and whether it's usable.
    """
    if not result or not isinstance(result, dict):
        return {"usable": False, "score": 0, "reason": "Empty or invalid result"}

    if "error" in result:
        return {"usable": False, "score": 0, "reason": result["error"]}

    # Agent-specific checks
    checks = {
        "STAG Keywords":    _check_keyword_agent,
        "Brand Segment":    _check_keyword_agent,
        "Negative Mining":  _check_negative_agent,
        "Intent Cluster":   _check_cluster_agent,
        "RSA Copywriter":   _check_rsa_agent,
        "PMax Assets":      _check_pmax_agent,
        "Budget Allocator": _check_budget_agent,
        "ROI Forecaster":   _check_roi_agent,
    }

    checker = checks.get(agent_name)
    if checker:
        return checker(result)

    # Generic check: does result have at least some content?
    non_empty = sum(1 for v in result.values() if v and v != [] and v != {} and v != "")
    score = min(100, non_empty * 15)
    return {
        "usable": score >= 30,
        "score":  score,
        "fields": non_empty,
        "reason": f"{non_empty} non-empty fields returned",
    }


def _check_keyword_agent(result: Dict) -> Dict:
    """Check keyword agent produced valid service-based keywords."""
    all_keywords = []

    # Extract from various possible structures
    if "keywords_by_theme" in result:
        for theme_kws in result["keywords_by_theme"].values():
            if isinstance(theme_kws, list):
                all_keywords.extend(theme_kws)
    if "brand_keywords" in result:
        all_keywords.extend(result["brand_keywords"])
    if "non_brand_keywords" in result:
        all_keywords.extend(result["non_brand_keywords"])
    if "clusters" in result:
        for c in result.get("clusters", []):
            all_keywords.extend(c.get("keywords", []))

    if not all_keywords:
        return {"usable": False, "score": 0, "reason": "No keywords found in agent output"}

    # Validate each keyword
    validation = validate_keyword_list(all_keywords)
    usable = validation["valid"] > 0

    return {
        "usable":            usable,
        "score":             validation["avg_quality_score"],
        "grade":             validation["quality_grade"],
        "total_keywords":    validation["total"],
        "valid_keywords":    validation["valid"],
        "invalid_keywords":  validation["invalid"],
        "clean_keywords":    validation["clean_keywords"],
        "reason":            f"{validation['valid']}/{validation['total']} keywords passed quality check",
        "validation_detail": validation,
    }


def _check_negative_agent(result: Dict) -> Dict:
    negatives = (
        result.get("campaign_negatives", []) +
        result.get("informational_negatives", []) +
        result.get("job_seeker_negatives", [])
    )
    count = len([n for n in negatives if n and isinstance(n, str)])
    return {
        "usable": count >= 5,
        "score":  min(100, count * 5),
        "count":  count,
        "reason": f"{count} negative keywords generated",
    }


def _check_cluster_agent(result: Dict) -> Dict:
    clusters = result.get("clusters", [])
    valid = [c for c in clusters if c.get("keywords") and c.get("name")]
    return {
        "usable": len(valid) >= 2,
        "score":  min(100, len(valid) * 25),
        "clusters": len(valid),
        "reason": f"{len(valid)} valid intent clusters",
    }


def _check_rsa_agent(result: Dict) -> Dict:
    headlines    = result.get("headlines", [])
    descriptions = result.get("descriptions", [])
    validation   = validate_ad_copy(headlines, descriptions)
    return {
        "usable":             validation["ready_to_publish"],
        "score":              100 if validation["ready_to_publish"] else 50,
        "headline_count":     len(headlines),
        "description_count":  len(descriptions),
        "headline_issues":    validation["headline_issues"],
        "description_issues": validation["description_issues"],
        "ready_to_publish":   validation["ready_to_publish"],
        "clean_headlines":    validation["clean_headlines"],
        "clean_descriptions": validation["clean_descriptions"],
        "reason":             validation["publish_verdict"],
    }


def _check_pmax_agent(result: Dict) -> Dict:
    hl   = result.get("headlines", [])
    desc = result.get("descriptions", [])
    has_cta = bool(result.get("cta"))
    has_images = bool(result.get("image_concepts"))
    score = 0
    if len(hl) >= 3:   score += 30
    if len(desc) >= 2: score += 30
    if has_cta:        score += 20
    if has_images:     score += 20
    return {
        "usable":     score >= 60,
        "score":      score,
        "headlines":  len(hl),
        "descriptions": len(desc),
        "has_cta":    has_cta,
        "has_images": has_images,
        "reason":     f"PMax assets score: {score}/100",
    }


def _check_budget_agent(result: Dict) -> Dict:
    allocation = result.get("allocation", [])
    pcts = [a.get("pct", a.get("percentage", 0)) for a in allocation if isinstance(a, dict)]
    total_pct = sum(p for p in pcts if isinstance(p, (int, float)))
    valid = 90 <= total_pct <= 110  # allow slight rounding
    return {
        "usable":     valid,
        "score":      100 if valid else 40,
        "total_pct":  total_pct,
        "campaigns":  len(allocation),
        "reason":     f"Budget allocation totals {total_pct}% ({'OK' if valid else 'should be ~100%'})",
    }


def _check_roi_agent(result: Dict) -> Dict:
    has_months = bool(result.get("month1") or result.get("monthly_projections"))
    has_roas   = bool(result.get("projected_roas") or result.get("target_roas"))
    score = (50 if has_months else 0) + (50 if has_roas else 0)
    return {
        "usable": score >= 50,
        "score":  score,
        "has_projections": has_months,
        "has_roas": has_roas,
        "reason": f"ROI forecast {'complete' if score == 100 else 'partial'}",
    }


# ─────────────────────────────────────────────────────────────────
# SECTION 5: FULL SYSTEM QUALITY REPORT
# Run this after all 88 agents complete
# ─────────────────────────────────────────────────────────────────

def full_quality_report(agent_results: Dict) -> Dict:
    """
    Run quality checks on all agent outputs.
    Returns a complete quality report before anything goes to Google Ads.
    """
    agents = agent_results.get("agents", {})
    report = {
        "business":      agent_results.get("business_name", ""),
        "checked_at":    __import__("datetime").datetime.now().isoformat(),
        "agents_checked": 0,
        "agents_passed":  0,
        "agents_failed":  0,
        "overall_score":  0,
        "publish_ready":  False,
        "critical_blocks": [],
        "warnings":       [],
        "agent_scores":   {},
        "keyword_report": None,
        "ad_copy_report": None,
        "campaign_report": None,
    }

    scores = []

    for agent_name, result in agents.items():
        check = check_agent_output_quality(agent_name, result)
        report["agents_checked"] += 1
        report["agent_scores"][agent_name] = check

        if check.get("usable", False):
            report["agents_passed"] += 1
        else:
            report["agents_failed"] += 1
            if check.get("score", 0) < 30:
                report["critical_blocks"].append({
                    "agent":  agent_name,
                    "reason": check.get("reason", "Low quality output"),
                })

        scores.append(check.get("score", 0))

    # Overall score
    report["overall_score"] = round(sum(scores) / len(scores)) if scores else 0
    report["overall_grade"] = _grade(report["overall_score"])

    # Specific quality reports for key agents
    if "STAG Keywords" in agents:
        kw_agent = agents["STAG Keywords"]
        all_kws = []
        if isinstance(kw_agent, dict) and "keywords_by_theme" in kw_agent:
            for kws in kw_agent["keywords_by_theme"].values():
                if isinstance(kws, list):
                    all_kws.extend(kws)
        if all_kws:
            report["keyword_report"] = validate_keyword_list(all_kws)

    if "RSA Copywriter" in agents:
        rsa = agents["RSA Copywriter"]
        if isinstance(rsa, dict):
            report["ad_copy_report"] = validate_ad_copy(
                rsa.get("headlines", []),
                rsa.get("descriptions", [])
            )

    if "Campaign Architect" in agents:
        report["campaign_report"] = validate_campaign_structure(
            agents["Campaign Architect"],
            agent_results.get("daily_budget", 50)
        )

    # Final publish decision
    has_critical = len(report["critical_blocks"]) > 0
    kw_ok  = report["keyword_report"] and report["keyword_report"]["valid"] > 0 if report["keyword_report"] else True
    ad_ok  = report["ad_copy_report"] and report["ad_copy_report"]["ready_to_publish"] if report["ad_copy_report"] else True
    camp_ok = report["campaign_report"] and report["campaign_report"]["ready"] if report["campaign_report"] else True

    report["publish_ready"] = not has_critical and kw_ok and ad_ok and camp_ok
    report["publish_verdict"] = (
        "✅ READY TO PUBLISH — All quality checks passed"
        if report["publish_ready"]
        else "❌ NOT READY — Fix critical issues before publishing"
    )

    return report
