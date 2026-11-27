#!/usr/bin/env python3
"""CN-local orchestrator: no JP SSH login, JP user, password, shell or management call."""
import argparse,getpass,hashlib,json,os,pathlib,platform,pwd,re,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import render,enrollment

def run(args,secret=None):
 r=subprocess.run([str(x) for x in args],input=secret,stdout=subprocess.PIPE)
 if r.returncode:raise RuntimeError('installation_step_failed:'+pathlib.Path(str(args[0])).name)
 return r.stdout

def save_public_request(path,request):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if path.is_symlink():raise ValueError('unsafe_request_output')
 if path.exists():
  previous=enrollment.read(path)
  if previous.get('device_id')!=request['device_id']:raise ValueError('request_output_belongs_to_another_device')
 fd,name=tempfile.mkstemp(dir=str(path.parent),prefix='.cn-request-')
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'wb') as f:f.write(enrollment.canonical(request));f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def bundle_import(path,request,ca_path,prompt=None):
 envelope=enrollment.read(path);verified=enrollment.verify_bundle(envelope,request,ca_path)
 imported={'access_bundle':envelope}
 if 'gateway_key' not in verified:
  if prompt is None:
   if not sys.stdin.isatty():raise ValueError('API_key_requires_private_interactive_terminal_no_key_in_chat_or_arguments')
   prompt=getpass.getpass
  key=prompt('输入管理员提供的本设备 Magpie Gateway Key（隐藏输入）：')
  if not isinstance(key,str) or not 20<=len(key)<=4096 or any(x in key for x in '\r\n\x00'):raise ValueError('invalid_API_key')
  imported['manual_gateway_key']=key
 return imported

def main():
 p=argparse.ArgumentParser();p.add_argument('--device-id');p.add_argument('--config');p.add_argument('--plan',action='store_true');p.add_argument('--no-public-check',action='store_true');p.add_argument('--access-bundle');p.add_argument('--request-out');p.add_argument('--share-repo',action='append',default=[]);p.add_argument('--git-name');p.add_argument('--git-email');p.add_argument('--allow-home-traverse',action='store_true');a=p.parse_args()
 if platform.system()!='Darwin' or os.getuid()==0:raise ValueError('run_on_CN_as_ordinary_administrator_not_root')
 user=pwd.getpwuid(os.getuid());c=dict(render.DEFAULT)
 if a.config:c.update(enrollment.read(a.config))
 else:
  serial=run(['/usr/sbin/ioreg','-rd1','-c','IOPlatformExpertDevice']);uuid=re.search(rb'"IOPlatformUUID"\s*=\s*"([^"]+)"',serial)
  if not uuid:raise ValueError('cannot_identify_device')
  c.update(device_id=a.device_id or 'cn-'+hashlib.sha256(uuid.group(1)).hexdigest()[:16],operator_user=user.pw_name,operator_home=user.pw_dir)
 c['python_binary']=sys.executable;c=render.validate(c)
 if (c['jp_host'],c['jp_api_port'],c['jp_egress_port'])!=('10.9.8.30',43425,43480):raise ValueError('unsupported_JP_route')
 if c['operator_user']!=user.pw_name or c['operator_home']!=user.pw_dir:raise ValueError('operator_does_not_match_login')
 print(json.dumps({'device_id':c['device_id'],'operator':user.pw_name,'software':'iTerm2 + managed Magpie + native Claude + root-managed Python','JP':c['jp_host'],'JP_login_required':False,'plan_only':a.plan}),flush=True)
 if a.plan:return
 run(['/usr/bin/sudo','-v']);stage=pathlib.Path('/Library/Application Support/CN-Agent-Installer-v3')
 if stage.exists():
  r=subprocess.run(['/usr/bin/sudo','/usr/bin/stat','-f','%u',str(stage)],capture_output=True,text=True)
  if r.returncode or r.stdout.strip()!='0':raise ValueError('unsafe_installer_stage')
 else:run(['/usr/bin/sudo','/bin/mkdir',str(stage)])
 if stage.is_symlink():raise ValueError('symlink_installer_stage')
 run(['/usr/bin/sudo','/usr/bin/ditto',str(ROOT),str(stage)]);run(['/usr/bin/sudo','/usr/sbin/chown','-R','root:wheel',str(stage)]);run(['/usr/bin/sudo','/bin/chmod','-R','go-w',str(stage)])
 with tempfile.TemporaryDirectory(prefix='cn-agent-install-') as td:
  conf=pathlib.Path(td)/'config.json';conf.write_text(json.dumps(c));conf.chmod(0o600);rootcmd=['/usr/bin/sudo',sys.executable,str(stage/'setup/root_install.py')]
  prepared=json.loads(run(rootcmd+['prepare','--config',str(conf)]))
  if not prepared.get('prepared'):raise ValueError('prepare_incomplete')
  if a.access_bundle:
   imported=bundle_import(a.access_bundle,prepared['request'],ROOT/'trust/jp-ca.pem')
   configured=json.loads(run(rootcmd+['configure','--config',str(conf)],enrollment.canonical(imported)));del imported;print(json.dumps(configured),flush=True)
  elif prepared.get('already_configured'):
   print(run(rootcmd+['start','--config',str(conf)]).decode().strip(),flush=True)
  else:
   dest=pathlib.Path(a.request_out) if a.request_out else pathlib.Path(user.pw_dir)/'Downloads/CN-Agent-Enrollment'/(c['device_id']+'.request.json')
   save_public_request(dest,prepared['request'])
   print(json.dumps({'status':'awaiting_admin_access_bundle','installation_complete':False,'request_file':str(dest.resolve()),'request_contains_private_key':False,'JP_login_required':False}),flush=True)
   print('把登记申请交给管理员。管理员在 JP 签发接入包后，用 --access-bundle /绝对路径/设备.access.json 继续；不要提供 JP 登录凭据。',flush=True);return
  check=run(['/usr/bin/sudo',sys.executable,str(stage/'setup/accept.py'),'--config',str(conf)]+(['--no-public-check'] if a.no_public_check else []));result=json.loads(check);print(json.dumps(result),flush=True)
  if not result.get('passed'):raise RuntimeError('acceptance_failed_do_not_claim_ready')
 for repo in a.share_repo:
  command=[str(pathlib.Path(c['install_base'])/'share-repo'),repo]
  if a.git_name:command+=['--git-name',a.git_name]
  if a.git_email:command+=['--git-email',a.git_email]
  if a.allow_home_traverse:command+=['--allow-home-traverse']
  if subprocess.run(command).returncode:raise RuntimeError('repository_sharing_incomplete_agent_install_preserved')
 print('Repository helper: '+str(pathlib.Path(c['install_base'])/'share-repo')+'; select each repo explicitly. No repo/Home shared automatically.',flush=True)
 print('Installed. In iTerm2 choose JP Agent (WireGuard), then run claude. GUI acceptance remains required.',flush=True)
if __name__=='__main__':
 try:main()
 except Exception as e:print('Installation stopped: '+(str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__)+'. Credentials were not printed.',file=sys.stderr);sys.exit(1)
