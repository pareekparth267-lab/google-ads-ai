content = open('app_v13.py', encoding='utf-8').read()

old = '''        "You are a brand keyword segmentation specialist for Google Ads.",
        "You are a brand keyword specialist. NEVER include city/location names in keywords. Service-based keywords only.",'''

new = '        "You are a brand keyword segmentation specialist for Google Ads. NEVER include city/location names in keywords. Service-based keywords only.",'

if old in content:
    content = content.replace(old, new)
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done! Fixed agent_05')
else:
    print('ERROR - text not found')