"""JP-local administrator helper. Returns secrets in memory; never prints them."""
import fcntl,hashlib,json,os,pathlib,subprocess,tempfile

def enroll(request,issuer_source):
 home=pathlib.Path.home();base=home/'ai/cn-agent-egress-pilot';ca=base/'wg-private'
 deployment=home/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json'
 # Reuse the existing deployment only; never initialize a CA or replace a gateway.
 d=json.loads(deployment.read_text());binary=pathlib.Path(d['binary']);config=pathlib.Path(d['configDir'])
 if hashlib.sha256(binary.read_bytes()).hexdigest()!=d['binarySHA256']:raise ValueError('JP_binary_pin_changed')
 for name in ['ca.pem','ca-key.pem','allowed-serial']:
  if not (ca/name).is_file():raise ValueError('JP_existing_CA_not_found')
 # Check the actual running transport settings before modifying registration.
 import plistlib
 for role,port in [('api',43425),('egress',43480)]:
  job=plistlib.loads((home/'Library/LaunchAgents'/('local.cn-agent-wireguard.'+role+'.plist')).read_bytes());args=job['ProgramArguments']
  if str(ca/'allowed-serial') not in args or not any(str(port) in str(x) for x in args):raise ValueError('JP_transport_layout_changed')
 ns={'__name__':'fleet_issuer'};exec(compile(issuer_source,'issue_client.py','exec'),ns)
 device=request['device_id'];records=ca/'fleet-delivery';records.mkdir(mode=0o700,exist_ok=True)
 fd=os.open(records/'management.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(fd,fcntl.LOCK_EX)
 try:
  with tempfile.TemporaryDirectory(dir=str(records),prefix='enroll-') as td:
   td=pathlib.Path(td);csr=td/'client.csr';csr.write_text(request['csr']);csr.chmod(0o600)
   meta=ns['enroll'](ca,device,csr,td/'output')
   path=records/(device+'.json');name='cn-'+device
   keylist=config/'caller-keys.json';keys=json.loads(keylist.read_text());matches=[x for x in keys if x.get('name')==name]
   if len(matches)>1:raise ValueError('duplicate_device_gateway_key')
   if path.exists():
    previous=json.loads(path.read_text())
    if previous.get('serial')!=meta['serial'] or not matches or matches[0].get('id')!=previous.get('gateway_key_id') or matches[0].get('off'):raise ValueError('device_key_state_changed')
    key=previous['gateway_key'];keyid=previous['gateway_key_id']
   elif matches:
    # Never silently adopt a manually-created key with this name.
    raise ValueError('existing_key_without_delivery_record_review_required')
   else:
    env=dict(os.environ);env['XDG_CONFIG_HOME']=str(config.parent)
    r=subprocess.run([str(binary),'gateway-key','add',name],env=env,capture_output=True)
    if r.returncode:raise ValueError('gateway_key_creation_failed')
    key=r.stdout.decode().strip()
    if not key or '\n' in key:raise ValueError('gateway_key_output_invalid')
    matches=[x for x in json.loads(keylist.read_text()) if x.get('name')==name]
    if len(matches)!=1:raise ValueError('gateway_key_record_missing')
    keyid=matches[0]['id'];ns['atomic'](path,json.dumps({'serial':meta['serial'],'gateway_key_id':keyid,'gateway_key':key}).encode())
   return {'device_id':device,'serial':meta['serial'],'gateway_key':key,'gateway_key_id':keyid,'client.pem':(td/'output/client.pem').read_text(),'ca.pem':(td/'output/ca.pem').read_text()}
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
