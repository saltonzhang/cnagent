#!/usr/bin/env python3
"""JP administrator only. Per-device status and explicit budget changes, no key output."""
import argparse,datetime,fcntl,hashlib,json,os,pathlib,re,subprocess,sys,tempfile
import device_budget

def atomic(p,value):
 fd,tmp=tempfile.mkstemp(prefix='.budget-',dir=str(p.parent))
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o600);os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def update(binary,config,records,device,chosen=None,apply=False):
 if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}',device):raise ValueError('invalid_device_id')
 file=records/(device+'.json')
 if file.is_symlink():raise ValueError('unsafe_device_record')
 record=json.loads(file.read_text());keyid=record['gateway_key_id'];before,key=device_budget.read_key(config,keyid)
 out={'device_id':device,'gateway_key_id':keyid,'recorded_budget':record.get('budget'),'current_limit':key.get('limit'),'additional_limits':key.get('moreLimits',[]),'apply':apply}
 env=dict(os.environ,XDG_CONFIG_HOME=str(config.parent))
 if chosen is None:
  if apply:raise ValueError('explicit_budget_required')
  r=subprocess.run([str(binary),'gateway-key','limit',keyid],env=env,capture_output=True,text=True,timeout=30)
  if r.returncode:raise ValueError('budget_status_failed')
  out['usage']=r.stdout;return out
 chosen=device_budget.validate(chosen);out['requested_budget']=chosen
 if not apply:return out
 if device_budget.matches(key,chosen):
  record['budget']=chosen;atomic(file,record);out['changed']=False;return out
 if key.get('moreLimits') or (key.get('limit') or {}).get('models'):raise ValueError('complex_existing_limits_require_manual_review')
 backup=records/'budget-backups';backup.mkdir(mode=0o700,exist_ok=True)
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 snapshot=backup/(device+'-'+stamp+'.json');atomic(snapshot,{'device_id':device,'gateway_key_id':keyid,'limit':key.get('limit'),'recorded_budget':record.get('budget'),'requested_budget':chosen})
 args=[str(binary),'gateway-key','limit',keyid]
 if chosen['mode']=='unlimited':args+=['off']
 else:
  args+=[chosen['period']]
  if chosen['tokens']:args+=['--tokens',str(chosen['tokens'])]
  if chosen['cost']:args+=['--cost',str(chosen['cost'])]
  if chosen['cache_reads']:args+=['--cache-reads']
 r=subprocess.run(args,env=env,capture_output=True,timeout=30)
 if r.returncode:raise ValueError('budget_update_failed_review_private_backup')
 after,updated=device_budget.read_key(config,keyid)
 if not device_budget.matches(updated,chosen):raise ValueError('budget_update_not_verified')
 if [x for x in before if x.get('id')!=keyid]!=[x for x in after if x.get('id')!=keyid]:raise ValueError('unrelated_key_changed_review_required')
 if {k:v for k,v in key.items() if k not in ['limit','moreLimits']}!={k:v for k,v in updated.items() if k not in ['limit','moreLimits']}:raise ValueError('unrelated_device_key_property_changed')
 record['budget']=chosen;atomic(file,record);out.update(changed=True,backup=str(snapshot),current_limit=updated.get('limit'),recorded_budget=chosen);return out

def main():
 os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--device-id',required=True);p.add_argument('--period',choices=['day','week','month','5h']);p.add_argument('--tokens',type=int);p.add_argument('--cost',type=float);p.add_argument('--cache-reads',action='store_true');p.add_argument('--unlimited',action='store_true');p.add_argument('--apply',action='store_true');a=p.parse_args()
 chosen=device_budget.policy(a.period,a.tokens,a.cost,a.cache_reads,a.unlimited) if any(x is not None for x in [a.period,a.tokens,a.cost]) or a.cache_reads or a.unlimited else None
 h=pathlib.Path.home();d=json.loads((h/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json').read_text());binary=pathlib.Path(d['binary']);config=pathlib.Path(d['configDir'])
 if hashlib.sha256(binary.read_bytes()).hexdigest()!=d['binarySHA256']:raise ValueError('JP_binary_pin_changed')
 records=h/'ai/cn-agent-egress-pilot/wg-private/fleet-delivery';fd=os.open(records/'management.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX);print(json.dumps(update(binary,config,records,a.device_id,chosen,a.apply)))
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
if __name__=='__main__':
 try:main()
 except Exception as e:print('Budget management stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__)+'. No secret printed.',file=sys.stderr);sys.exit(1)
