content = open('app_v13.py', encoding='utf-8').read()

job_code = '''
# Background Job Store
import uuid as _uuid2
_jobs = {}

@app.post("/start-job")
async def start_job(body: RunCrewRequest, background_tasks: BackgroundTasks, _=Depends(verify_key)):
    job_id = str(_uuid2.uuid4())[:12]
    _jobs[job_id] = {"status": "running", "result": None, "error": None}
    async def run_job():
        try:
            result = await run_all_agents(body)
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = result
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
    background_tasks.add_task(run_job)
    return {"job_id": job_id, "status": "running"}

@app.get("/job-status/{job_id}")
async def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return {"status": job["status"], "error": job.get("error")}

@app.get("/job-result/{job_id}")
async def job_result(job_id: str):
    job = _jobs.get(job_id)
    if not job or job["status"] != "done":
        return {"error": "Not ready"}
    return job["result"]
'''

content = content.replace(
    'if __name__ == "__main__":',
    job_code + '\nif __name__ == "__main__":'
)
open('app_v13.py', 'w', encoding='utf-8').write(content)
print('Done! Backend job system added.')