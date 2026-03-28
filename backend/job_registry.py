import threading
import uuid
import time
from datetime import datetime, timedelta

class JobRegistry:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()
        self.ttl = timedelta(hours=24)

    def create_job(self):
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {
                'id': job_id,
                'status': 'queued',
                'progress': 0,
                'result': None,
                'error': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        self._cleanup()
        return job_id

    def update_job(self, job_id, status=None, progress=None, result=None, error=None):
        with self.lock:
            if job_id in self.jobs:
                if status: self.jobs[job_id]['status'] = status
                if progress is not None: self.jobs[job_id]['progress'] = progress
                if result is not None: self.jobs[job_id]['result'] = result
                if error: self.jobs[job_id]['error'] = error
                self.jobs[job_id]['updated_at'] = datetime.now()

    def get_job(self, job_id):
        with self.lock:
            return self.jobs.get(job_id)

    def _cleanup(self):
        now = datetime.now()
        expired = [jid for jid, job in self.jobs.items() if now - job['created_at'] > self.ttl]
        for jid in expired:
            del self.jobs[jid]

job_registry = JobRegistry()
