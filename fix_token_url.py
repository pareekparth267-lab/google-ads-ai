content = open('app_v13.py', encoding='utf-8').read()

# Add missing constants after GOOGLE_MCC_ID line
old = 'GOOGLE_MCC_ID       = os.getenv("GOOGLE_ADS_MCC_ID", "").strip()'

new = '''GOOGLE_MCC_ID       = os.getenv("GOOGLE_ADS_MCC_ID", "").strip()

# Google API URLs
GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
GOOGLE_ADS_BASE     = "https://googleads.googleapis.com/v17"'''

if old in content:
    content = content.replace(old, new)
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done! GOOGLE_TOKEN_URL added.')
else:
    print('ERROR - line not found')