content = open('index.html', encoding='utf-8').read()

old = "    const data = await apiPost('/run-crew-v13', body);"

new = """    // Start background job - no timeout
    const jobResp = await apiPost('/start-job', body);
    const jobId = jobResp.job_id;
    clog('Job started: ' + jobId + ' - agents running in background...', 'info');

    // Poll every 5 seconds until done
    const data = await new Promise((resolve, reject) => {
      const poll = setInterval(async () => {
        try {
          const status = await apiGet('/job-status/' + jobId);
          clog('Status: ' + status.status, 'info');
          if (status.status === 'done') {
            clearInterval(poll);
            const result = await apiGet('/job-result/' + jobId);
            resolve(result);
          } else if (status.status === 'error') {
            clearInterval(poll);
            reject(new Error(status.error || 'Job failed'));
          }
        } catch(e) {
          clearInterval(poll);
          reject(e);
        }
      }, 5000);
    });"""

if old in content:
    content = content.replace(old, new)
    open('index.html', 'w', encoding='utf-8').write(content)
    print('Done! Frontend polling added.')
else:
    print('ERROR - line not found')
    