content = open('app_v13.py', encoding='utf-8').read()

# Reduce orchestrator max_tokens significantly
content = content.replace(
    'max_tokens=1200,\n        agent_num=86',
    'max_tokens=400,\n        agent_num=86'
)
content = content.replace(
    'max_tokens=1200,\n        agent_num=87',
    'max_tokens=400,\n        agent_num=87'
)
content = content.replace(
    'max_tokens=1200,\n        agent_num=88',
    'max_tokens=400,\n        agent_num=88'
)

open('app_v13.py', 'w', encoding='utf-8').write(content)
print('Done!')