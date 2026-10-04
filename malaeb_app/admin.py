#!/usr/bin/env python3
"""Local subscription review commands. Run only after independently verifying payment."""
import sys, time
from server import connect, init_db

def main():
 init_db()
 if len(sys.argv)<2 or sys.argv[1] not in ('pending','activate'):
  print('Usage: python3 admin.py pending | activate REFERENCE'); return 2
 with connect() as db:
  if sys.argv[1]=='pending':
   rows=db.execute("SELECT s.reference,o.name,o.email,o.phone,s.plan,s.amount,s.created_at FROM subscriptions s JOIN owners o ON o.id=s.owner_id WHERE s.status='pending' ORDER BY s.id").fetchall()
   if not rows: print('No pending subscription requests.'); return 0
   for r in rows: print(f"{r['reference']} | {r['plan']} | {r['amount']:,} IQD | {r['name']} | {r['email']} | {r['phone']}")
   return 0
  if len(sys.argv)!=3: print('Usage: python3 admin.py activate REFERENCE'); return 2
  row=db.execute("SELECT * FROM subscriptions WHERE reference=? AND status='pending'",(sys.argv[2],)).fetchone()
  if not row: print('Pending reference not found.'); return 1
  days=365 if row['plan']=='yearly' else 30; now=int(time.time())
  db.execute("UPDATE subscriptions SET status='active',paid_at=?,expires_at=? WHERE id=?",(now,now+days*86400,row['id']))
  print(f"Activated {row['reference']} for {days} days. Do this only after verifying the transfer/payment.")
 return 0
if __name__=='__main__': raise SystemExit(main())
