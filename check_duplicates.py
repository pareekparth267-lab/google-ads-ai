content = open('app_v13.py', encoding='utf-8').read()
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'NEVER include city' in line or 'NEVER put city' in line:
        print(i+1, ':', line.strip()[:80])
        