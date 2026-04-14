content = open('app_v13.py', encoding='utf-8').read()

old = '''        if r.is_success:
            customers = r.json().get("resourceNames", [])
            diag["step_3_accessible_customers"] = {
                "success":         True,
                "accessible_count": len(customers),
                "customer_ids":    [c.split("/")[-1] for c in customers],
                "raw":             customers[:10],
            }
        else:
            err = r.json().get("error", {})'''

new = '''        if r.is_success:
            try:
                customers = r.json().get("resourceNames", [])
            except Exception:
                customers = []
            diag["step_3_accessible_customers"] = {
                "success":         True,
                "accessible_count": len(customers),
                "customer_ids":    [c.split("/")[-1] for c in customers],
                "raw":             customers[:10],
                "raw_text":        r.text[:300],
            }
        else:
            diag["step_3_raw_response"] = r.text[:500]
            diag["step_3_status_code"] = r.status_code
            try:
                err = r.json().get("error", {})
            except Exception:
                err = {"message": r.text[:200]}'''

if old in content:
    content = content.replace(old, new)
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done!')
else:
    print('ERROR - not found')
    