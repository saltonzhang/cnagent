#!/usr/bin/env python3
"""JP-local model-group management; no CN login credentials, no service restart."""
import argparse,datetime,hashlib,json,os,pathlib,subprocess,sys,urllib.request
GROUP='cn-default'
def main():
 p=argparse.ArgumentParser();p.add_argument('--model');p.add_argument('--apply',action='store_true');a=p.parse_args()
 home=pathlib.Path.home();d=json.loads((home/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json').read_text());binary=pathlib.Path(d['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==d['binarySHA256'],'core_pin_changed'
 config=pathlib.Path(d['configDir']);providers=config/'providers.json';state=json.loads(providers.read_text());group=next((g for g in state.get('groups',[]) if g.get('id')==GROUP),None)
 print(json.dumps({'group':'group/'+GROUP,'members':group.get('members',[]) if group else [],'requestedModel':a.model,'apply':a.apply}))
 if not a.model:return
 with urllib.request.urlopen('http://127.0.0.1:3425/v1/models',timeout=10) as r:ids={x['id'] for x in json.load(r)['data']}
 if a.model not in ids or a.model.startswith('group/'):raise ValueError('select_an_actual_available_provider_model')
 if not a.apply:return
 backup=home/'ai/cn-agent-egress-pilot/wg-private/central-model-backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup.mkdir(parents=True,mode=0o700);f=backup/'providers.before.json';f.write_bytes(providers.read_bytes());f.chmod(0o600)
 env=dict(os.environ,XDG_CONFIG_HOME=str(config.parent));args=[str(binary),'group','set',GROUP,'models='+a.model,'routing=order'] if group else [str(binary),'group','add',GROUP,'models='+a.model,'routing=order']
 r=subprocess.run(args,env=env,capture_output=True,timeout=20)
 if r.returncode:raise ValueError('group_update_failed_review_backup')
 updated=json.loads(providers.read_text());assert [{k:v for k,v in g.items()} for g in updated.get('groups',[]) if g.get('id')!=GROUP]==[g for g in state.get('groups',[]) if g.get('id')!=GROUP]
 assert {k:v for k,v in updated.items() if k!='groups'}=={k:v for k,v in state.items() if k!='groups'},'unrelated_provider_change'
 print(json.dumps({'updated':True,'group':'group/'+GROUP,'actualModel':a.model,'backup':str(backup),'restartRequired':False}))
if __name__=='__main__':
 try:main()
 except Exception as e:print('Central model change stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)
