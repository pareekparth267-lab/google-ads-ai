content = open('app_v13.py', encoding='utf-8').read()

old = '@app.post("/api/google/publish-v13")'

new = '''@app.post("/api/google/publish-v13")'''

# Check if GoogleAdsPublisher exists
if 'class GoogleAdsPublisher' in content:
    print('GoogleAdsPublisher found in code')
else:
    print('ERROR - GoogleAdsPublisher NOT found - need to add it')

if 'GOOGLE_ADS_AVAILABLE' in content:
    print('GOOGLE_ADS_AVAILABLE found')
else:
    print('ERROR - GOOGLE_ADS_AVAILABLE not found')

print('Done checking')