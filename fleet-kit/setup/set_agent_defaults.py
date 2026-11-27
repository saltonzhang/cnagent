#!/usr/bin/env python3
"""Managed CN only: match CN162's default aliases, preserve effort/auth and routing."""
import argparse,json,pathlib,pwd,os,tempfile,sys,fcntl
import set_agent_timezone as guard
ALIASES=['ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL']
GROUP='group/cn-default'
def migrate(config,apply=False,rollback=None,owner=0):
 config=pathlib.Path(config);guard.migrate(config,owner=owner)
 c=json.loads(config.read_text())
 if c.get('jp_model_id')!=GROUP:raise ValueError('central_group_migration_required_first')
 a=pwd.getpwnam(c['agent_user']);home=pathlib.Path(a.pw_dir);file=guard.safe(home/'.claude/settings.json',a.pw_uid)
 if (home/'.claude').is_symlink():raise ValueError('unsafe_settings_directory')
 provider=json.loads((home/'.config/magpie/providers.json').read_text());entries=[p for p in provider.get('providers',[]) if p.get('id')=='remote-magpie']
 if len(entries)!=1 or entries[0].get('responses')!='http://127.0.0.1:'+str(c['api_adapter_port'])+'/v1' or entries[0].get('preset') or GROUP not in entries[0].get('models',[]):raise ValueError('responses_group_route_required')
 raw=file.read_bytes();s=file.stat();parent=pathlib.Path(c['install_base'])/'private/agent-default-backups'
 if rollback:
  b=pathlib.Path(rollback)
  if b.is_symlink() or b.parent!=parent or b.stat().st_uid!=owner:raise ValueError('invalid_rollback_directory')
  m=json.loads(guard.safe(b/'change.json',owner).read_text());old=guard.safe(b/'settings.before',owner).read_bytes()
  if m['settings']!=str(file) or guard.sha(raw)!=m['afterSHA256'] or guard.sha(old)!=m['beforeSHA256']:raise ValueError('rollback_conflict_preserve_current_settings')
  if not apply:return {'rollbackPreview':True,'apply':False}
  guard.atomic(file,old,s.st_uid,s.st_gid,s.st_mode&0o777);return {'rolledBack':True,'newClaudeSessionRequired':True}
 d=json.loads(raw);desired={k:'remote-magpie/'+GROUP for k in ALIASES};needed=d.get('model')!='sonnet' or any(d.get('env',{}).get(k)!=v for k,v in desired.items())
 out={'defaultModel':'sonnet','aliasTarget':'remote-magpie/'+GROUP,'changeNeeded':needed,'apply':apply,'effortPolicyChanged':False,'certificateKeyQuotaRequestUnchanged':True,'serverModelLockAdded':False,'servicesRestarted':False}
 if not apply or not needed:return out
 d['model']='sonnet';d.setdefault('env',{}).update(desired);after=(json.dumps(d,indent=2)+'\n').encode()
 if parent.exists() and (parent.is_symlink() or parent.stat().st_uid!=owner):raise ValueError('unsafe_backup_directory')
 parent.mkdir(mode=0o700,exist_ok=True);b=pathlib.Path(tempfile.mkdtemp(prefix='aliases-',dir=str(parent)));b.chmod(0o700)
 guard.atomic(b/'settings.before',raw,owner,s.st_gid,0o600);guard.atomic(b/'change.json',(json.dumps({'settings':str(file),'beforeSHA256':guard.sha(raw),'afterSHA256':guard.sha(after)})+'\n').encode(),owner,s.st_gid,0o600)
 if file.is_symlink() or file.read_bytes()!=raw:raise ValueError('settings_changed_during_update')
 guard.atomic(file,after,s.st_uid,s.st_gid,s.st_mode&0o777);out.update(changed=True,backup=str(b),newClaudeSessionRequired=True);return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default='/Library/Application Support/CN-Agent-Egress/private/config.json');p.add_argument('--apply',action='store_true');p.add_argument('--rollback');a=p.parse_args()
 if os.geteuid()!=0:raise ValueError('local_root_required')
 if not a.apply:print(json.dumps(migrate(a.config,False,a.rollback)));return
 migrate(a.config,False,a.rollback)
 c=json.loads(pathlib.Path(a.config).read_text());lock=pathlib.Path(c['install_base'])/'private/install.lock'
 if lock.exists():guard.safe(lock,0)
 fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX);print(json.dumps(migrate(a.config,True,a.rollback)))
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
if __name__=='__main__':
 try:main()
 except Exception as e:print('Agent defaults update stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__)+'. No secrets printed.',file=sys.stderr);sys.exit(1)
