content = open('app_v13.py', encoding='utf-8').read()

old = '''# ── Google Ads Library ───────────────────────────────────────
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    GOOGLE_ADS_AVAILABLE = True
except ImportError:
    GOOGLE_ADS_AVAILABLE = False
    print("⚠️ google-ads library not installed")'''

new = '''# ── Google Ads Library ───────────────────────────────────────
GOOGLE_ADS_AVAILABLE = False
GoogleAdsClient = None
GoogleAdsException = None
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    GOOGLE_ADS_AVAILABLE = True
except Exception as e:
    print(f"⚠️ google-ads library error: {e}")'''

if old in content:
    content = content.replace(old, new)
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done!')
else:
    print('Not found - already fixed or different text')