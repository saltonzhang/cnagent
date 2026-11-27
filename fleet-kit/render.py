#!/usr/bin/env python3
"""Render public, per-device staging files. Never installs, creates keys, or contacts JP."""
import argparse,ipaddress,json,pathlib,plistlib,re,uuid,os
ROOT=pathlib.Path(__file__).resolve().parent
DEFAULT=json.loads((ROOT/'deployment.example.json').read_text())
def validate(raw):
 c=dict(DEFAULT);unknown=set(raw)-set(c)
 if unknown:raise ValueError('unknown configuration fields: '+','.join(sorted(unknown)))
 c.update(raw)
 for k in ['device_id','operator_user','agent_user','network_user']:
  if not isinstance(c[k],str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,62}',c[k]) or 'REPLACE' in c[k]:raise ValueError('invalid/missing '+k)
 if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}',c['device_id']):raise ValueError('device_id must use lowercase letters/digits')
 if c['enable_codex']:raise ValueError('Codex tools require separate qualification; this fleet baseline supports Claude only')
 for key in ['agent_user','network_user']:
  if not re.fullmatch(r'[a-z_][a-z0-9_]{0,30}',c[key]):raise ValueError('service account must use a simple POSIX name: '+key)
 if c['agent_user']==c['network_user'] or c['operator_user'] in [c['agent_user'],c['network_user'],'root']:raise ValueError('three identities must be distinct')
 for k in ['operator_home','agent_home','network_home','install_base','python_binary','magpie_binary']:
  s=c[k]
  if not isinstance(s,str) or not s.startswith('/') or not re.fullmatch(r'[A-Za-z0-9_./ -]+',s) or '..' in pathlib.PurePosixPath(s).parts or 'REPLACE' in s:raise ValueError('unsafe/missing '+k)
 for k in ['agent_home','network_home','python_binary']:
  if ' ' in c[k]:raise ValueError('this template requires a no-space '+k)
 if c['agent_home']==c['operator_home'] or c['network_home'] in [c['agent_home'],c['operator_home']]:raise ValueError('homes must be distinct')
 if any(c[k] in ['/','/Users','/var','/var/db','/Library','/Applications'] for k in ['agent_home','network_home','install_base']):raise ValueError('dedicated directories required')
 for key,parent in [('agent_home','/Users'),('network_home','/var/db'),('install_base','/Library/Application Support')]:
  if str(pathlib.PurePosixPath(c[key]).parent)!=parent:raise ValueError('unsupported/untrusted parent for '+key)
 if c['python_binary'].startswith(('/Users/','/tmp/','/private/tmp/','/opt/homebrew/','/usr/local/')):raise ValueError('root supervisor requires a system/root-managed Python runtime')
 ip=ipaddress.IPv4Address(c['jp_host'])
 if ip.is_loopback or ip.is_unspecified or ip.is_multicast:raise ValueError('invalid JP address')
 ports=[c[k] for k in ['cn_api_port','api_adapter_port','web_proxy_port','jp_api_port','jp_egress_port']]
 if any(type(p) is not int or not 1024<=p<=65535 for p in ports) or len(set(ports))!=5:raise ValueError('ports must be distinct unprivileged integers')
 if not re.fullmatch(r'com\.apple/[A-Za-z0-9_.-]+',c['pf_anchor']):raise ValueError('dedicated child of existing com.apple anchor required')
 if type(c['enable_codex']) is not bool or not isinstance(c['jp_model_id'],str) or not re.fullmatch(r'[A-Za-z0-9_./:@-]+',c['jp_model_id']):raise ValueError('invalid model/codex flag')
 return c

def render(raw,out):
 c=validate(raw);out=pathlib.Path(out)
 if out.exists():raise ValueError('refusing existing staging directory')
 # Do not accidentally render directly into live installation paths.
 if str(out.resolve())==c['install_base'] or str(out.resolve()).startswith(('/Library/','/var/db/')):raise ValueError('render into a non-live staging directory')
 out.mkdir(parents=True,mode=0o700)
 mapping={k.upper():str(v) for k,v in c.items()};mapping['PYTHON_BIN_DIR']=str(pathlib.PurePosixPath(c['python_binary']).parent)
 for f in (ROOT/'templates').glob('*.tmpl'):
  s=f.read_text()
  for key,value in mapping.items():s=s.replace('@@'+key+'@@',value)
  if re.search(r'@@[A-Z_]+@@',s):raise ValueError('unresolved template token')
  if f.name=='launch.tmpl' and not c['enable_codex']:s=s.replace('claude|codex|shell','claude|shell')
  p=out/f.name[:-5];p.write_text(s);p.chmod(0o700 if p.name in ['launch','supervisor.py'] else 0o600)
 # The gateway secret is intentionally NOT rendered. Read its protected file
 # only when installing the dedicated providers.json on the target machine.
 provider={'providers':[{'id':'remote-magpie','name':'jp','key':'__READ_FROM_PROTECTED_DEVICE_KEY_FILE__','responses':'http://127.0.0.1:'+str(c['api_adapter_port'])+'/v1','proxy':'direct','models':[c['jp_model_id']]}]}
 (out/'providers.template.json').write_text(json.dumps(provider,indent=2));(out/'settings.json').write_text(json.dumps({'lan':False,'proxy':'direct'}))
 (out/'claude-settings.json').write_text(json.dumps({'env':{'ANTHROPIC_BASE_URL':'http://127.0.0.1:'+str(c['cn_api_port']),'ANTHROPIC_AUTH_TOKEN':'cnagent-local',**{k:'remote-magpie/'+c['jp_model_id'] for k in ['ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL']}},'model':'sonnet'},indent=2))
 label='local.cn-agent-wireguard.controlled'
 job={'Label':label,'ProgramArguments':[c['python_binary'],c['install_base']+'/supervisor.py'],'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':15,'StandardOutPath':c['install_base']+'/private/supervisor.log','StandardErrorPath':c['install_base']+'/private/supervisor-error.log'}
 (out/(label+'.plist')).write_bytes(plistlib.dumps(job))
 profile={'Profiles':[{'Guid':str(uuid.uuid5(uuid.NAMESPACE_URL,'cn-agent-wireguard:'+c['device_id'])),'Name':'JP Agent (WireGuard)','Custom Command':'Yes','Command':'/usr/bin/sudo "'+c['install_base']+'/launch" shell','Working Directory':c['operator_home'],'Terminal Type':'xterm-256color','Keyboard Map':{'0x7f-0x0':{'Action':11,'Text':'0x7f'},'0xf728-0x0':{'Action':10,'Text':'[3~'},'0xf728-0x800000':{'Action':10,'Text':'[3~'}}}]}
 (out/'CN-Agent-WireGuard.json').write_text(json.dumps(profile,indent=2));(out/'deployment.public.json').write_text(json.dumps(c,indent=2))
 (out/'cnagent-zshrc.fragment').write_text("if [[ -o interactive ]]; then\n bindkey '^?' backward-delete-char\n bindkey '^H' backward-delete-char\n bindkey '\\e[3~' delete-char\nfi\n")
 for f in out.iterdir():
  if f.is_file():f.chmod(0o700 if f.name in ['launch','supervisor.py'] else 0o600)
 return c
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();c=render(json.loads(pathlib.Path(a.config).read_text()),a.out);print(json.dumps({'rendered':True,'device_id':c['device_id'],'out':str(pathlib.Path(a.out).resolve()),'installed':False,'containsSecrets':False}))
