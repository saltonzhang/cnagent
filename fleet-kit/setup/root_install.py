#!/usr/bin/env python3
"""Privileged, journalled CN installer. Never execute against an unmanaged existing pilot."""
import argparse,fcntl,hashlib,json,os,pathlib,platform,plistlib,pwd,shutil,socket,secrets,subprocess,sys,tarfile,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));import render,enrollment
LABEL='local.cn-agent-wireguard.controlled'
def run(args,**kw):
 r=subprocess.run([str(x) for x in args],capture_output=True,**kw)
 if r.returncode:raise RuntimeError('command_failed:'+pathlib.Path(str(args[0])).name+':'+str(r.returncode))
 return r.stdout

def write(p,data,mode=0o600,uid=0,gid=0):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.is_symlink():raise ValueError('symlink_destination')
 fd,name=tempfile.mkstemp(dir=str(p.parent),prefix='.install-')
 try:
  os.fchmod(fd,mode);os.fchown(fd,uid,gid)
  with os.fdopen(fd,'wb') as f:f.write(data.encode() if isinstance(data,str) else data);f.flush();os.fsync(f.fileno())
  os.replace(name,p)
 finally:
  if os.path.exists(name):os.unlink(name)

def directory(path,mode,uid=0,gid=0):
 # Explicit modes survive umask 077; only call after managed-install checks.
 p=pathlib.Path(path)
 if p.is_symlink():raise ValueError('symlink_directory')
 p.mkdir(exist_ok=True)
 if not p.is_dir():raise ValueError('not_a_directory')
 os.chown(p,uid,gid);p.chmod(mode)
 return p

def agent_directories(home,uid,gid):
 # Own each parent; never recursively chmod/chown existing user data.
 for relative in ['.local','.local/bin','workspace','.config','.config/magpie','.claude']:
  directory(pathlib.Path(home)/relative,0o700,uid,gid)

def digest(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def assets():
 d=json.loads((ROOT/'software/LOCK.json').read_text())
 for name,v in d['files'].items():
  p=ROOT/'software'/name
  if p.is_symlink() or not p.is_file() or digest(p)!=v['sha256']:raise ValueError('software_hash_mismatch:'+name)
 return d

def account(c,j,save,key,home,shell):
 name=c[key]
 try:u=pwd.getpwnam(name)
 except KeyError:u=None
 record=j.setdefault('accounts',{}).get(name)
 if not record:
  if u or pathlib.Path(home).exists():raise ValueError('unmanaged_account_or_home:'+name)
  occupied={x.pw_uid for x in pwd.getpwall()};uid=502
  while uid in occupied:uid+=1
  record={'uid':uid,'home':home,'complete':False};j['accounts'][name]=record;save()
 if u and (u.pw_uid!=record['uid'] or u.pw_dir!=home):raise ValueError('account_identity_changed')
 if not record['complete']:
  if not u:
   for attr,v in [('UniqueID',record['uid']),('PrimaryGroupID',20),('NFSHomeDirectory',home),('UserShell',shell),('Password','*'),('IsHidden',1),('RealName','CN controlled service')]:run(['/usr/bin/dscl','.','-create','/Users/'+name,attr,str(v)])
  u=pwd.getpwnam(name)
  admins=run(['/usr/bin/id','-Gn',name]).decode().split()
  if 'admin' in admins:raise ValueError('service_account_is_admin')
  h=pathlib.Path(home);h.mkdir(mode=0o700,exist_ok=True);os.chown(h,u.pw_uid,u.pw_gid);h.chmod(0o700)
  record['complete']=True;save()
 u=pwd.getpwnam(name)
 if 'admin' in run(['/usr/bin/id','-Gn',name]).decode().split():raise ValueError('service_account_is_admin')
 return u

def ensure_anchor(b,j,save):
 rules=run(['/sbin/pfctl','-sr']).decode()
 if 'anchor "com.apple/*"' in rules:return
 # Fresh Macs can have the factory PF file but no loaded rules. Never replace
 # active/nonempty root policy; load FILTER ONLY, preserving NAT/options/states.
 info=run(['/sbin/pfctl','-s','info']).decode()
 if rules.strip() or 'Status: Disabled' not in info:raise ValueError('existing_pf_root_anchor_required_review_active_policy')
 if 'anchor "com.apple/*"' not in pathlib.Path('/etc/pf.conf').read_text():raise ValueError('factory_pf_anchor_not_found')
 f=b/'private/factory-filter-anchor.conf';write(f,'anchor "com.apple/*"\n')
 run(['/sbin/pfctl','-n','-R','-f',f]);j['factory_filter_anchor_added']=True;save();run(['/sbin/pfctl','-R','-f',f])
 if 'anchor "com.apple/*"' not in run(['/sbin/pfctl','-sr']).decode():raise ValueError('factory_pf_anchor_load_failed')

def prepare(c,j,save,b):
 lock=assets();arch={'arm64':'arm64','x86_64':'amd64'}.get(platform.machine())
 if not arch:raise ValueError('unsupported_architecture')
 ensure_anchor(b,j,save)
 # Refuse collisions before any kernel/network change.
 if not j.get('configured'):
  for k in ['cn_api_port','api_adapter_port','web_proxy_port']:
   s=socket.socket()
   try:s.bind(('127.0.0.1',c[k]))
   finally:s.close()
 software=directory(b/'software',0o755)
 # Existing personal apps are untouched. Managed Magpie is independent.
 if not (software/'magpie.app').exists():
  with tempfile.TemporaryDirectory() as td:
   run(['/usr/bin/ditto','-x','-k',ROOT/'software'/('magpie-darwin-'+arch+'.zip'),td]);src=pathlib.Path(td)/'magpie.app'
   run(['/usr/bin/codesign','--verify','--deep','--strict',src]);shutil.copytree(src,software/'magpie.app',symlinks=True)
 if not pathlib.Path('/Applications/iTerm.app').exists():
  with tempfile.TemporaryDirectory() as td:
   run(['/usr/bin/ditto','-x','-k',ROOT/'software/iterm.zip',td]);src=pathlib.Path(td)/'iTerm.app'
   run(['/usr/bin/codesign','--verify','--deep','--strict',src]);shutil.copytree(src,'/Applications/iTerm.app',symlinks=True);j['installed_iterm']=True;save()
 for app,team in [(software/'magpie.app','LY7MVTUDZG'),(pathlib.Path('/Applications/iTerm.app'),'H7V7XYVQ7D')]:
  info=subprocess.run(['/usr/bin/codesign','-dv',str(app)],capture_output=True).stderr.decode()
  if 'TeamIdentifier='+team not in info:raise ValueError('unexpected_software_signer')
 a=account(c,j,save,'agent_user',c['agent_home'],'/bin/zsh');n=account(c,j,save,'network_user',c['network_home'],'/usr/bin/false')
 ah=pathlib.Path(a.pw_dir);nh=pathlib.Path(n.pw_dir)
 agent_directories(ah,a.pw_uid,a.pw_gid)
 if not (ah/'.local/bin/claude').exists():
  with tarfile.open(ROOT/'software'/('claude-'+arch+'.tgz')) as t:
   member=t.getmember('package/claude')
   if not member.isfile() or member.size>400*1024*1024:raise ValueError('invalid_claude_archive')
   write(ah/'.local/bin/claude',t.extractfile(member).read(),0o755,a.pw_uid,a.pw_gid)
 run(['/usr/bin/codesign','--verify','--strict',ah/'.local/bin/claude'])
 info=subprocess.run(['/usr/bin/codesign','-dv',str(ah/'.local/bin/claude')],capture_output=True).stderr.decode()
 if 'TeamIdentifier=Q6L2SF6YDW' not in info:raise ValueError('unexpected_claude_signer')
 # Private key is born under the network identity and never crosses the machine.
 if not (nh/'client-key.pem').exists():
  run(['/usr/bin/sudo','-u',n.pw_name,'/usr/bin/openssl','req','-new','-newkey','rsa:2048','-nodes','-keyout',nh/'client-key.pem','-out',nh/'client.csr','-subj','/CN=cn-agent-'+c['device_id']]);(nh/'client-key.pem').chmod(0o600);(nh/'client.csr').chmod(0o600)
 c['magpie_binary']=str(software/'magpie.app/Contents/MacOS/magpie')
 write(b/'private/config.json',json.dumps(c,indent=2));j['prepared']=True
 request_file=b/'private/enrollment-request.json'
 request=enrollment.read(request_file) if request_file.exists() else None
 if request is None or (not j.get('configured') and time.time()-request['created_at']>7*86400):
  request=enrollment.request_for(c,(nh/'client.csr').read_text(),secrets.token_hex(32),int(time.time()),ROOT/'trust/jp-ca.pem')
  write(request_file,enrollment.canonical(request))
 enrollment.validate_request(request,ROOT/'trust/jp-ca.pem');save()
 return {'prepared':True,'device_id':c['device_id'],'request':request,'already_configured':bool(j.get('configured') and j.get('accepted_bundle_sha256'))}


def install_fresh_entry(home,content,uid,gid):
 desktop=pathlib.Path(home)/'Desktop'
 if desktop.is_symlink() or desktop.exists() and (not desktop.is_dir() or desktop.stat().st_uid!=uid):return False
 if not desktop.exists():desktop.mkdir(mode=0o700);os.chown(desktop,uid,gid)
 target=desktop/'Start-JP-Agent-Fresh.command'
 if target.is_symlink() or target.exists() and (not target.is_file() or target.stat().st_uid!=uid or target.read_bytes()!=content):return False
 write(target,content,0o700,uid,gid);return True

def configure(c,j,save,b,payload):
 if not j.get('prepared'):raise ValueError('prepare_first')
 request=enrollment.read(b/'private/enrollment-request.json')
 for k in ['jp_host','jp_api_port','jp_egress_port','jp_model_id']:
  if request['route'][k]!=c[k]:raise ValueError('request_route_changed')
 envelope=payload.get('access_bundle');verified=enrollment.verify_bundle(envelope,request,ROOT/'trust/jp-ca.pem')
 if 'gateway_key' not in verified:
  verified['gateway_key']=payload.get('manual_gateway_key')
 elif payload.get('manual_gateway_key') is not None:raise ValueError('bundle_already_contains_API_key')
 payload=verified
 a=pwd.getpwnam(c['agent_user']);n=pwd.getpwnam(c['network_user']);ah=pathlib.Path(a.pw_dir);nh=pathlib.Path(n.pw_dir)
 if payload.get('device_id')!=c['device_id'] or not isinstance(payload.get('gateway_key'),str) or not 20<=len(payload['gateway_key'])<=4096 or any(x in payload['gateway_key'] for x in '\r\n\x00'):raise ValueError('invalid_enrollment')
 # Verify against the on-host private key before changing any active certificate.
 with tempfile.TemporaryDirectory(prefix='cn-key-check-') as td:
  cert=pathlib.Path(td)/'client.pem';cert.write_text(payload['client.pem'])
  pub=run(['/usr/bin/openssl','x509','-in',cert,'-pubkey','-noout'])
  if pub!=run(['/usr/bin/openssl','pkey','-in',nh/'client-key.pem','-pubout']):raise ValueError('certificate_key_mismatch')
 for f in ['client.pem','ca.pem']:write(nh/f,payload[f],uid=n.pw_uid,gid=n.pw_gid)
 with tempfile.TemporaryDirectory(prefix='cn-render-') as td:
  stage=pathlib.Path(td)/'rendered';render.render(c,stage)
  for f in ['launch','supervisor.py','controlled.sb','pilot.pf','probe.py']:write(b/f,(stage/f).read_bytes(),0o755 if f in ['launch','supervisor.py'] else 0o644)
  arch={'arm64':'arm64','x86_64':'amd64'}[platform.machine()];write(b/'wg-transport',(ROOT/'bin'/('wg-transport-darwin-'+arch)).read_bytes(),0o755)
  provider=json.loads((stage/'providers.template.json').read_text());provider['providers'][0]['key']=payload['gateway_key']
  for f,v in [('providers.json',json.dumps(provider)),('settings.json',(stage/'settings.json').read_text())]:write(ah/'.config/magpie'/f,v,uid=a.pw_uid,gid=a.pw_gid)
  settings=json.loads((stage/'claude-settings.json').read_text());settings['env']['DISABLE_AUTOUPDATER']='1'
  write(ah/'.claude/settings.json',json.dumps(settings),uid=a.pw_uid,gid=a.pw_gid)
  write(ah/'.zshrc','export PATH="$HOME/.local/bin:'+str(pathlib.Path(c['python_binary']).parent)+':/usr/bin:/bin:/usr/sbin:/sbin"\n'+(stage/'cnagent-zshrc.fragment').read_text(),uid=a.pw_uid,gid=a.pw_gid)
  profile=pathlib.Path(c['operator_home'])/'Library/Application Support/iTerm2/DynamicProfiles/CN-Agent-WireGuard.json'
  # Back up only the exact file we own, never reset all iTerm settings.
  if profile.exists() and not j.get('configured'):write(b/'private/profile.before',profile.read_bytes())
  op=pwd.getpwnam(c['operator_user']);j['fresh_desktop_entry']=install_fresh_entry(op.pw_dir,(stage/'Start-JP-Agent-Fresh.command').read_bytes(),op.pw_uid,op.pw_gid);profile.parent.mkdir(parents=True,exist_ok=True)
  # New parent hierarchy must belong to the operator rather than root.
  for parent in [profile.parent,profile.parent.parent]:os.chown(parent,op.pw_uid,op.pw_gid)
  write(profile,(stage/'CN-Agent-WireGuard.json').read_bytes(),uid=op.pw_uid,gid=op.pw_gid)
  job=pathlib.Path('/Library/LaunchDaemons')/(LABEL+'.plist')
  if job.exists() and not j.get('configured'):raise ValueError('unmanaged_launchdaemon')
  write(job,(stage/(LABEL+'.plist')).read_bytes(),0o644)
 from install_repo_sharing import install as install_repo_tools
 j['repo_sharing_helper']=install_repo_tools(c,True);save()
 run(['/sbin/pfctl','-a',c['pf_anchor'],'-nf',b/'pilot.pf']);run(['/usr/bin/sandbox-exec','-f',b/'controlled.sb','/usr/bin/true']);run(['/usr/bin/plutil','-lint','/Library/LaunchDaemons/'+LABEL+'.plist'])
 j['configured']=True;j['accepted_bundle_sha256']=enrollment.sha(enrollment.canonical(envelope));j['accepted_request_sha256']=enrollment.sha(enrollment.canonical(request));save()
 # Only a newly provisioned CN job is started. No JP or other service restart.
 existing=subprocess.run(['/bin/launchctl','print','system/'+LABEL],capture_output=True)
 if existing.returncode:run(['/bin/launchctl','bootstrap','system','/Library/LaunchDaemons/'+LABEL+'.plist'])
 for _ in range(60):
  if (b/'private/expected-pf.txt').exists():break
  time.sleep(.25)
 return {'configured':True,'needs_live_acceptance':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','configure','status','stop','start']);p.add_argument('--config',required=True);args=p.parse_args()
 if os.getuid()!=0 or platform.system()!='Darwin':raise ValueError('macOS_root_required')
 raw=json.loads(pathlib.Path(args.config).read_text());c=render.validate(raw)
 if (c['jp_host'],c['jp_api_port'],c['jp_egress_port'])!=('10.9.8.30',43425,43480):raise ValueError('unsupported_JP_route')
 b=pathlib.Path(c['install_base']);private=b/'private'
 # An existing pilot is never adopted or overwritten by this installer.
 if b.exists() and not (private/'installer-state.json').exists():raise ValueError('existing_unmanaged_installation_stop')
 directory(b,0o755);directory(private,0o700)
 lockfd=os.open(private/'install.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(lockfd,fcntl.LOCK_EX)
 state=private/'installer-state.json';j=json.loads(state.read_text()) if state.exists() else {'schema':3,'device_id':c['device_id'],'accounts':{}}
 if j['device_id']!=c['device_id']:raise ValueError('different_device_installation')
 def save():write(state,json.dumps(j,indent=2))
 save()
 if (private/'config.json').exists():
  saved=json.loads((private/'config.json').read_text())
  if any(saved[k]!=c[k] for k in c if k!='magpie_binary'):raise ValueError('existing_parameters_changed')
  c=saved
 if args.action=='prepare':result=prepare(c,j,save,b)
 elif args.action=='configure':result=configure(c,j,save,b,json.load(sys.stdin))
 elif args.action=='start':
  if not j.get('configured') or not j.get('accepted_bundle_sha256'):raise ValueError('signed_access_bundle_required')
  existing=subprocess.run(['/bin/launchctl','print','system/'+LABEL],capture_output=True)
  if existing.returncode:run(['/bin/launchctl','bootstrap','system','/Library/LaunchDaemons/'+LABEL+'.plist'])
  result={'started':True,'credentials_unchanged':True}
 elif args.action=='stop':
  subprocess.run(['/bin/launchctl','bootout','system/'+LABEL],capture_output=True);result={'stopped':True,'accounts_and_PF_restrictions_retained':True,'JP_revocation_required':True}
 else:result={'device_id':j['device_id'],'prepared':j.get('prepared',False),'configured':j.get('configured',False),'job_loaded':subprocess.run(['/bin/launchctl','print','system/'+LABEL],capture_output=True).returncode==0}
 print(json.dumps(result))
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'error':str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__}),file=sys.stderr);sys.exit(1)
