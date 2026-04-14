content = open('app_v13.py', encoding='utf-8').read()

old = '''        publisher = GoogleAdsPublisher(customer_id)
        pub = publisher.publish(result, body.dict())'''

new = '''        publisher = GoogleAdsPublisher(customer_id)
        pub = publisher.publish_all_agents(result, body.dict())'''

if old in content:
    content = content.replace(old, new)
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done! Publisher updated to use all agents.')
else:
    print('ERROR - not found')