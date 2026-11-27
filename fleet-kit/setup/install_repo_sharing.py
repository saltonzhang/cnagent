#!/usr/bin/env python3
"""Add repo sharing helpers only. No service, credentials, network or project ACL changes."""
import argparse,hashlib,json,os,pathlib,pwd,shutil,sys,tempfile,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def trusted(p):
 s=p.stat()
 if p.is_symlink() or s.st_uid!=0 or s.st_mode&0o022:raise ValueError("root_managed_runtime_required")

def install(c,apply=False):
 b=pathlib.Path(c['install_base']);op=pwd.getpwnam(c['operator_user']);agent=pwd.getpwnam(c['agent_user']);py=pathlib.Path(c['python_binary'])
 if op.pw_uid==0 or agent.pw_uid==0 or op.pw_uid==agent.pw_uid:raise ValueError('distinct_nonroot_accounts_required')
 for p in [b,b/'launch',py.resolve()]:
  trusted(p)
 context={'schema':1,'operator_user':op.pw_name,'operator_home':op.pw_dir,'agent_user':agent.pw_name,'agent_home':agent.pw_dir,'python_binary':str(py),'install_base':str(b)}
 source=(ROOT/'repo-sharing/share_git_repo.py').read_bytes();wrapper=('#!/bin/bash\nexec '+__import__('shlex').quote(str(py))+' '+__import__('shlex').quote(str(b/'repo-sharing/share_git_repo.py'))+' "$@"\n').encode()
 files={b/'repo-sharing/share_git_repo.py':(source,0o644),b/'repo-sharing.json':((json.dumps(context,indent=2)+'\n').encode(),0o644),b/'share-repo':(wrapper,0o755)}
 state=b/'private/repo-sharing-install.json';previous=json.loads(state.read_text()) if state.exists() else {};changed=[]
 for p,(data,mode) in files.items():
  if p.is_symlink():raise ValueError('symlink_helper_destination')
  if p.exists() and p.read_bytes()!=data and previous.get('files',{}).get(str(p))!=sha(p):raise ValueError('unmanaged_or_customized_repo_helper_preserved')
  if not p.exists() or p.read_bytes()!=data:changed.append(str(p))
 result={'component':'repository-sharing','apply':apply,'changedFiles':changed,'servicesRestarted':False,'projectPermissionsChanged':False,'operator':op.pw_name,'agent':agent.pw_name,'command':str(b/'share-repo')}
 if not apply:return result
 backup=pathlib.Path(tempfile.mkdtemp(prefix='repo-tools-',dir=str(b/'private')));backup.chmod(0o700)
 for p in files:
  if p.exists():shutil.copyfile(p,backup/p.name);(backup/p.name).chmod(0o600)
 target=b/'repo-sharing'
 if target.exists():trusted(target)
 target.mkdir(mode=0o755,exist_ok=True);target.chmod(0o755)
 for p,(data,mode) in files.items():
  fd,name=tempfile.mkstemp(dir=p.parent)
  try:
   os.fchmod(fd,mode)
   with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
   os.replace(name,p)
  finally:
   if os.path.exists(name):os.unlink(name)
 manifest={'files':{str(p):sha(p) for p in files},'backup':str(backup)};state.write_text(json.dumps(manifest,indent=2));state.chmod(0o600);result['backup']=str(backup);return result

def main():
 os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--operator-user',default=os.environ.get('SUDO_USER'));p.add_argument('--agent-user',default='cnagent');p.add_argument('--install-base',default='/Library/Application Support/CN-Agent-Egress');p.add_argument('--apply',action='store_true');a=p.parse_args()
 if os.getuid()!=0 or sys.platform!='darwin':raise ValueError('macOS_local_root_required')
 c={'operator_user':a.operator_user,'agent_user':a.agent_user,'install_base':a.install_base,'python_binary':sys.executable};print(json.dumps(install(c,a.apply)))
if __name__=='__main__':
 try:main()
 except Exception as e:print('Repo helper installation stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__)+'. No secrets printed.',file=sys.stderr);sys.exit(1)
