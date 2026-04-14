content = open('app_v13.py', encoding='utf-8').read()

old = '''    headers = {
        "Authorization":  f"Bearer {access_token}",
        "developer-token": GOOGLE_ADS_DEV_TOK,
        "Content-Type":   "application/json",
    }

    # Step 3 — List accessible customers
    try:
        r = httpx.get(
            f"{GOOGLE_ADS_BASE}/customers:listAccessibleCustomers",
            headers=headers, timeout=30
        )'''

new = '''    headers = {
        "Authorization":  f"Bearer {access_token}",
        "developer-token": GOOGLE_ADS_DEV_TOK,
        "Content-Type":   "application/json",
    }
    if GOOGLE_MCC_ID:
        headers["login-customer-id"] = GOOGLE_MCC_ID.replace("-","")

    # Step 3 — List accessible customers
    try:
        r = httpx.get(
            f"{GOOGLE_ADS_BASE}/customers:listAccessibleCustomers",
            headers=headers, timeout=30
        )'''

if old in content:
    content = content.replace(old, new)
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done!')
else:
    print('ERROR - not found')