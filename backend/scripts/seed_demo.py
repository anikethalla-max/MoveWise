"""Add synthetic examples only to the current workspace ID supplied by the operator."""
import argparse
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import Workspace, Housing

parser = argparse.ArgumentParser()
parser.add_argument('workspace_id', help='Workspace cookie value from your local browser')
args = parser.parse_args()
with SessionLocal() as db:
    if not db.get(Workspace, args.workspace_id):
        parser.error('Workspace not found')
    if db.scalar(select(Housing).where(Housing.workspace_id == args.workspace_id, Housing.source == 'synthetic demo')):
        parser.error('Synthetic examples already present')
    for name, locality, rent, maintenance, deposit in [
        ('Sample apartment A', 'Indiranagar', '32000.00', '3000.00', '100000.00'),
        ('Sample apartment B', 'Whitefield', '27000.00', '2500.00', '80000.00'),
        ('Sample apartment C', 'Koramangala', '36000.00', '3500.00', '110000.00'),
    ]:
        db.add(Housing(workspace_id=args.workspace_id, name=name, locality=locality, rent=rent,
                       maintenance=maintenance, deposit=deposit, source='synthetic demo',
                       notes='Synthetic example for demonstration; not a real listing or price quote.'))
    db.commit()
print('Added three synthetic Bengaluru examples.')
