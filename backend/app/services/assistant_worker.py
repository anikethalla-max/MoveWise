"""Durable queue worker for Coordinator runs; safe alongside API background execution."""
import time
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import AgentRun
from app.services.assistant_runs import execute_run, recover_interrupted_runs


def main():
    print('MoveWise assistant worker running',flush=True)
    while True:
        with SessionLocal() as db:
            recover_interrupted_runs(db)
            run_id=db.scalar(select(AgentRun.id).where(AgentRun.parent_run_id.is_(None),
                AgentRun.status=='queued').order_by(AgentRun.created_at).limit(1))
        if run_id:execute_run(run_id)
        else:time.sleep(2)


if __name__=='__main__':main()
