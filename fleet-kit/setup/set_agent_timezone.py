#!/usr/bin/env python3
"""Incremental, managed-CN-only launcher update. No keys, services or system TZ changes."""
import argparse,datetime,fcntl,hashlib,json,os,pathlib,pwd,stat,subprocess,tempfile,sys
sha=lambda b:hashlib.sha256(b).hexdigest()
RULE='(deny file-read* (regex #"^(/private)?/etc/localtime$"))'
BLOCK='\n# Read the current network sandbox, then add Agent-only host timezone restrictions.\nagent_profile=$(/bin/cat "$base/controlled.sb")\nagent_profile+=$\'\\n(deny file-read* (regex #"^(/private)?/etc/localtime$"))\\n\'\n'
def safe(p,owner):
 p=pathlib.Path(p)
 if p.is_symlink() or not p.is_file():raise ValueError('unsafe_or_missing_file')
 s=p.stat()
 if s.st_uid!=owner or s.st_mode&0o022:raise ValueError('untrusted_file_owner_or_mode')
 return p

def atomic(p,data,uid,gid,mode):
 fd,tmp=tempfile.mkstemp(prefix='.timezone-',dir=str(p.parent))
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.chown(tmp,uid,gid);os.chmod(tmp,mode);os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def transform(raw,home,user):
 s=raw.decode();prefix='/usr/bin/env -i ';old=prefix+'HOME='+home+' USER='+user+' LOGNAME='+user;new=prefix+'TZ=Asia/Tokyo HOME='+home+' USER='+user+' LOGNAME='+user
 if s.count(prefix)!=1:raise ValueError('ambiguous_launcher_environment')
 if s.count(new)!=1:
  if s.count(old)!=1 or 'TZ=' in s:raise ValueError('custom_launcher_requires_review')
  s=s.replace(old,new)
 old_profile='-f "$base/controlled.sb"';new_profile='-p "$agent_profile"'
 if s.count(new_profile)==1 and BLOCK in s:return s.encode()
 if s.count(old_profile)!=1 or 'agent_profile=' in s or 'agent_profile+=' in s:raise ValueError('custom_launcher_requires_review')
 marker='exec /usr/bin/sudo -u '
 if s.count(marker)!=1:raise ValueError('launcher_identity_ambiguous')
 return s.replace(marker,BLOCK+'\n'+marker).replace(old_profile,new_profile).encode()

def migrate(config,apply=False,rollback=None,owner=0):
 config=safe(config,owner);c=json.loads(config.read_text());base=pathlib.Path(c['install_base']);private=base/'private'
 for d in [base,private]:
  if d.is_symlink() or not d.is_dir() or d.stat().st_uid!=owner or d.stat().st_mode&0o022:raise ValueError('unsafe_install_directory')
 state=safe(private/'installer-state.json',owner);j=json.loads(state.read_text())
 if j.get('schema')!=3 or not j.get('configured') or not j.get('accepted_bundle_sha256') or j.get('device_id')!=c.get('device_id'):raise ValueError('managed_v3_install_required_do_not_adopt_pilot')
 account=pwd.getpwnam(c['agent_user']);record=j.get('accounts',{}).get(c['agent_user'],{})
 if not record.get('complete') or record.get('uid')!=account.pw_uid or record.get('home')!=account.pw_dir or c['agent_home']!=account.pw_dir:raise ValueError('managed_account_identity_changed')
 live=safe(base/'launch',owner);s=live.stat();before=live.read_bytes();parent=private/'timezone-backups'
 if rollback:
  b=pathlib.Path(rollback)
  if b.is_symlink() or b.parent!=parent or b.stat().st_uid!=owner:raise ValueError('invalid_rollback_directory')
  m=json.loads(safe(b/'change.json',owner).read_text());old=safe(b/'launch.before',owner).read_bytes()
  if m['launch']!=str(live) or sha(before)!=m['afterSHA256'] or sha(old)!=m['beforeSHA256']:raise ValueError('rollback_conflict_preserve_current_launcher')
  if not apply:return {'rollbackPreview':True,'willChangeOnly':str(live),'apply':False}
  atomic(live,old,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode));return {'rolledBack':True,'newShellRequired':True,'servicesRestarted':False}
 after=transform(before,c['agent_home'],c['agent_user'])
 out={'device_id':c['device_id'],'defaultTZ':'Asia/Tokyo','hostTimezoneFileGuard':True,'changeNeeded':after!=before,'apply':apply,'newShellRequired':True,'systemTimezoneChanged':False,'servicesRestarted':False}
 if not apply or before==after:return out
 # Syntax check only; never execute a copied root launcher while validating it.
 with tempfile.NamedTemporaryFile() as f:
  f.write(after);f.flush();r=subprocess.run(['/bin/bash','-n',f.name],capture_output=True)
  if r.returncode:raise ValueError('candidate_shell_syntax_invalid')
 if parent.exists() and (parent.is_symlink() or parent.stat().st_uid!=owner):raise ValueError('unsafe_backup_directory')
 parent.mkdir(mode=0o700,exist_ok=True);b=pathlib.Path(tempfile.mkdtemp(prefix=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=str(parent)));b.chmod(0o700)
 m={'launch':str(live),'beforeSHA256':sha(before),'afterSHA256':sha(after),'uid':s.st_uid,'gid':s.st_gid,'mode':stat.S_IMODE(s.st_mode)}
 atomic(b/'launch.before',before,owner,s.st_gid,0o600);atomic(b/'change.json',(json.dumps(m,indent=2)+'\n').encode(),owner,s.st_gid,0o600)
 if live.is_symlink() or live.read_bytes()!=before:raise ValueError('launcher_changed_during_update')
 atomic(live,after,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode));out.update(changed=True,backup=str(b));return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--rollback');p.add_argument('--config',default='/Library/Application Support/CN-Agent-Egress/private/config.json');a=p.parse_args()
 if os.geteuid()!=0:raise ValueError('local_root_required')
 # Serialize with the existing installer. Read-only preview creates no lock or state.
 if not a.apply:print(json.dumps(migrate(pathlib.Path(a.config),False,a.rollback)));return
 migrate(pathlib.Path(a.config),False,a.rollback)
 c=json.loads(safe(a.config,0).read_text());lock=pathlib.Path(c['install_base'])/'private/install.lock'
 if lock.exists():safe(lock,0)
 fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX);print(json.dumps(migrate(pathlib.Path(a.config),True,a.rollback)))
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
if __name__=='__main__':
 try:main()
 except Exception as e:print('Timezone update stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__)+'. No secrets printed.',file=sys.stderr);sys.exit(1)
