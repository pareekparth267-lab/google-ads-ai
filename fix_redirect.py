content = open('app_v13.py', encoding='utf-8').read()

old = '"http://https://google-ads-ai-zaok.onrender.com/auth/callback"'
new = '"https://google-ads-ai-zaok.onrender.com/auth/callback"'

if old in content:
    content = content.replace(old, new)
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done!')
else:
    print('Not found - searching...')
    idx = content.find('auth/callback')
    if idx > 0:
        print(content[idx-50:idx+50])