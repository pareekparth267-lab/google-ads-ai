content = open('app_v13.py', encoding='utf-8').read()

# Fix agent_07 duplicate prompt
old07 = '''        "You are an intent clustering expert for Google Ads campaign organization.",
        "You are an intent clustering expert for Google Ads. CRITICAL: NEVER put city names, state names, or location words in keywords. Pure service-based keywords only — location is set via campaign geo-targeting.",'''

new07 = '        "You are an intent clustering expert for Google Ads. CRITICAL: NEVER put city names, state names, or location words in keywords. Pure service-based keywords only — location is set via campaign geo-targeting.",'

if old07 in content:
    content = content.replace(old07, new07)
    print('Fixed agent_07')
else:
    print('agent_07 OK')

open('app_v13.py', 'w', encoding='utf-8').write(content)
print('Done!')