content = open('app_v13.py', encoding='utf-8').read()

# Fix the listAccessibleCustomers URL
old = 'f"{GOOGLE_ADS_BASE}/customers:listAccessibleCustomers"'
new = '"https://googleads.googleapis.com/v17/customers:listAccessibleCustomers"'

count = content.count(old)
print(f'Found {count} occurrences')

content = content.replace(old, new)
open('app_v13.py', 'w', encoding='utf-8').write(content)
print('Done!')