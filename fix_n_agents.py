content = open('app_v13.py', encoding='utf-8').read()

# Find where n_results are unpacked and add filter after
old = "    winner_scale, mkt_expand, kw_expand, comp_gap, profit_roas, cross_sync, funnel_orch = n_results"

new = """    winner_scale, mkt_expand, kw_expand, comp_gap, profit_roas, cross_sync, funnel_orch = n_results
    kw_expand = _strip_location_keywords(kw_expand, d.target_location)
    comp_gap  = _strip_location_keywords(comp_gap,  d.target_location)"""

if old in content:
    content = content.replace(old, new)
    print('Fixed A81 and A82 location filter')
else:
    # Try to find it differently
    idx = content.find('funnel_orch = n_results')
    if idx > 0:
        line_end = content.find('\n', idx)
        insert = "\n    kw_expand = _strip_location_keywords(kw_expand, d.target_location)\n    comp_gap  = _strip_location_keywords(comp_gap,  d.target_location)"
        content = content[:line_end] + insert + content[line_end:]
        print('Fixed A81 and A82 via fallback method')
    else:
        print('ERROR - could not find location to insert filter')

open('app_v13.py', 'w', encoding='utf-8').write(content)
print('Done!')