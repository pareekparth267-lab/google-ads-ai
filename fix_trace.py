import traceback as _tb

content = open('app_v13.py', encoding='utf-8').read()

content = content.replace(
    'import uuid as _uuid2',
    'import uuid as _uuid2\nimport traceback as _tb'
)

content = content.replace(
    '_jobs[job_id]["status"] = "error"\n            _jobs[job_id]["error"] = str(e)',
    '_jobs[job_id]["status"] = "error"\n            _jobs[job_id]["error"] = str(e) + " TRACE: " + _tb.format_exc()'
)

open('app_v13.py', 'w', encoding='utf-8').write(content)
print('Done!')