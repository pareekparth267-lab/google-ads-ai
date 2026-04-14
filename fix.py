lines = open('index.html', encoding='utf-8').readlines()
end_line = 1929
for i in range(1929, 1970):
    if 'clearInterval(interval)' in lines[i]:
        end_line = i
        break
print('Replacing lines 1929 to', end_line)
new_line = "    const data = await apiPost('/run-crew-v13', body);\n"
lines = lines[:1929] + [new_line] + lines[end_line:]
open('index.html', 'w', encoding='utf-8').write(''.join(lines))
print('Done! Lines now:', len(lines))
