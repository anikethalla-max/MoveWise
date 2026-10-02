import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import Depends, HTTPException
from app.api.routes.v1 import workspace
from app.core.config import settings


class WindowLimiter:
    def __init__(self):
        self.hits=defaultdict(deque)
        self.lock=Lock()

    def check(self,key:tuple,limit:int,window_seconds:int):
        now=time.monotonic()
        with self.lock:
            bucket=self.hits[key]
            while bucket and bucket[0]<=now-window_seconds:bucket.popleft()
            if len(bucket)>=limit:raise HTTPException(429,'Request limit reached. Please try again later.')
            bucket.append(now)


limiter=WindowLimiter()


def ai_rate_limit(workspace_id:str=Depends(workspace)):
    limiter.check(('ai',workspace_id),settings.ai_requests_per_minute,60)


def upload_rate_limit(workspace_id:str=Depends(workspace)):
    limiter.check(('upload',workspace_id),settings.uploads_per_hour,3600)
