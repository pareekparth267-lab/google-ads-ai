content = open('app_v13.py', encoding='utf-8').read()

filter_fn = '''
# ── Backend keyword location filter ──────────────────────────────
_LOCATION_PATTERNS = [
    r'\\bnear me\\b', r'\\bnearby\\b', r'\\bin my area\\b', r'\\baround me\\b',
]
_GENERIC_GEO = [
    'alabama','alaska','arizona','arkansas','california','colorado','connecticut',
    'delaware','florida','georgia','hawaii','idaho','illinois','indiana','iowa',
    'kansas','kentucky','louisiana','maine','maryland','massachusetts','michigan',
    'minnesota','mississippi','missouri','montana','nebraska','nevada',
    'new hampshire','new jersey','new mexico','new york','north carolina',
    'north dakota','ohio','oklahoma','oregon','pennsylvania','rhode island',
    'south carolina','south dakota','tennessee','texas','utah','vermont',
    'virginia','washington','west virginia','wisconsin','wyoming',
    ' fl',' ca',' tx',' ny',' az',' ga',' il',' pa',' oh',' nc',
]

def _strip_location_keywords(kw_data: dict, location: str = "") -> dict:
    if not kw_data or not isinstance(kw_data, dict):
        return kw_data
    loc_words = []
    if location:
        loc_words = [w.lower() for w in re.split(r"[,\\s]+", location) if len(w) > 2]
    def _is_location_kw(kw: str) -> bool:
        low = kw.lower()
        for pattern in _LOCATION_PATTERNS:
            if re.search(pattern, low):
                return True
        for geo in _GENERIC_GEO:
            if geo in low:
                return True
        for w in loc_words:
            if w in low:
                return True
        return False
    def _clean_list(kws):
        if not isinstance(kws, list):
            return kws
        cleaned = []
        for k in kws:
            if isinstance(k, str):
                if not _is_location_kw(k):
                    cleaned.append(k)
            elif isinstance(k, dict):
                kw_text = k.get("keyword", k.get("term", k.get("text", "")))
                if not _is_location_kw(kw_text):
                    cleaned.append(k)
        return cleaned
    for key in ("keywords_by_service", "keywords_by_theme"):
        if key in kw_data and isinstance(kw_data[key], dict):
            kw_data[key] = {svc: _clean_list(kws) for svc, kws in kw_data[key].items()}
    for key in ("keywords", "brand_keywords", "non_brand_keywords",
                "competitor_keywords", "brand_protection_keywords"):
        if key in kw_data and isinstance(kw_data[key], list):
            kw_data[key] = _clean_list(kw_data[key])
    if "clusters" in kw_data and isinstance(kw_data["clusters"], list):
        for cluster in kw_data["clusters"]:
            if isinstance(cluster, dict) and "keywords" in cluster:
                cluster["keywords"] = _clean_list(cluster["keywords"])
    return kw_data

'''

if '_strip_location_keywords' not in content:
    content = content.replace(
        'async def run_all_agents(d: RunCrewRequest',
        filter_fn + 'async def run_all_agents(d: RunCrewRequest'
    )
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done! _strip_location_keywords added.')
else:
    print('Already exists')