content = open('app_v13.py', encoding='utf-8').read()

# Increase ALL 600-token agents to 900
content = content.replace('max_tokens=600,', 'max_tokens=900,')

# Increase ALL 700-token agents to 1000  
content = content.replace('max_tokens=700,', 'max_tokens=1000,')

# Increase ALL 900-token agents to 1200
content = content.replace('max_tokens=900,', 'max_tokens=1200,')

# Also apply location filter to agents 81 and 82 results
old = "    winner_scale, mkt_expand, kw_expand, comp_gap, profit_roas, cross_sync, funnel_orch = n_results"
new = """    winner_scale, mkt_expand, kw_expand, comp_gap, profit_roas, cross_sync, funnel_orch = n_results
    # Strip location from expansion keyword agents
    kw_expand = _strip_location_keywords(kw_expand, d.target_location)
    comp_gap  = _strip_location_keywords(comp_gap,  d.target_location)"""

if old in content:
    content = content.replace(old, new)
    print('Fixed location filter for A81 and A82')
else:
    print('A81/A82 filter - not found, skipping')

open('app_v13.py', 'w', encoding='utf-8').write(content)
print('Done! All max_tokens increased.')