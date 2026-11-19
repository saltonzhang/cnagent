#!/usr/bin/env python3
"""One-time, local-administrator migration for v3-managed CNs. No JP login or restart."""
import argparse,datetime,json,os,pathlib,pwd,secrets,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import enrollment
from root_install import write
MODEL='group/cn-default'
def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--rollback');p.add_argument('--config',default='/Library/Application Support/CN-Agent-Egress/private/config.json');a=p.parse_args()
 if os.getuid()!=0:raise ValueError('local_root_required')
 config=pathlib.Path(a.config)
 if config.is_symlink() or config.stat().st_uid!=0:raise ValueError('untrusted_local_install_record')
 c=json.loads(config.read_text());base=pathlib.Path(c['install_base']);state=base/'private/installer-state.json'
 if not state.is_file() or not json.loads(state.read_text()).get('configured'):raise ValueError('v3_managed_install_required_do_not_adopt_historical_pilot')
 agent=pwd.getpwnam(c['agent_user']);home=pathlib.Path(agent.pw_dir)
 paths=[home/'.config/magpie/providers.json',home/'.claude/settings.json',config,base/'private/enrollment-request.json']
 if any(x.is_symlink() or not x.is_file() for x in paths):raise ValueError('unsafe_or_missing_configuration')
 if a.rollback:
  backup=pathlib.Path(a.rollback).resolve();parent=(base/'private/central-model-backups').resolve()
  if backup.parent!=parent or json.loads((backup/'paths.json').read_text())!=[str(x) for x in paths]:raise ValueError('invalid_rollback_directory')
  for i,path in enumerate(paths):
   st=path.stat();write(path,(backup/(str(i)+'.before')).read_bytes(),uid=st.st_uid,gid=st.st_gid)
  print(json.dumps({'rolledBack':True,'newClaudeSessionRequired':True}));return

 providers=json.loads(paths[0].read_text());matches=[x for x in providers['providers'] if x.get('id')=='remote-magpie'];assert len(matches)==1,'remote_provider_ambiguous'
 claude=json.loads(paths[1].read_text());request=enrollment.read(paths[3]);enrollment.validate_request(request,ROOT/'trust/jp-ca.pem')
 print(json.dumps({'before':c['jp_model_id'],'after':MODEL,'apply':a.apply,'restartRequired':False}))
 if not a.apply:return
 if c['jp_model_id']==MODEL and claude.get('model')=='remote-magpie/'+MODEL and MODEL in matches[0].get('models',[]):return
 backup=base/'private/central-model-backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup.mkdir(parents=True,mode=0o700)
 for i,path in enumerate(paths):write(backup/(str(i)+'.before'),path.read_bytes())
 write(backup/'paths.json',json.dumps([str(x) for x in paths]))
 matches[0]['models']=list(dict.fromkeys(matches[0].get('models',[])+[MODEL]));claude['model']='remote-magpie/'+MODEL;c['jp_model_id']=MODEL
 request=enrollment.request_for(c,request['csr'],secrets.token_hex(32),int(__import__('time').time()),ROOT/'trust/jp-ca.pem')
 write(paths[0],json.dumps(providers,indent=2),uid=agent.pw_uid,gid=agent.pw_gid);write(paths[1],json.dumps(claude,indent=2),uid=agent.pw_uid,gid=agent.pw_gid);write(config,json.dumps(c,indent=2));write(paths[3],enrollment.canonical(request))
 print(json.dumps({'migrated':True,'backup':str(backup),'keysAndCertificatesUnchanged':True,'newClaudeSessionRequired':True,'oldAccessBundleMustNotBeReimported':True}))
if __name__=='__main__':
 try:main()
 except Exception as e:print('Migration stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)
