content = open('index.html', encoding='utf-8').read()

old = "    try { renderResults(data); } catch(renderErr) {"

new = """    // Defer rendering to avoid call stack overflow
    setTimeout(() => {
    try { renderResults(data); } catch(renderErr) {"""

old2 = "      try { showPublishSection(data); } catch(e) {}\n      // Still populate sidebar pages in background\n      try { _autoPopulateAllPages(data); } catch(e) {}\n    }"

new2 = """      try { showPublishSection(data); } catch(e) {}
      try { _autoPopulateAllPages(data); } catch(e) {}
    }
    }, 100);"""

if old in content:
    content = content.replace(old, new)
    print('Fixed render defer')
else:
    print('render line not found')

open('index.html', 'w', encoding='utf-8').write(content)
print('Done!')
