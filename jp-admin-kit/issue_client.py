#!/usr/bin/env python3
"""JP administrator only: enroll/revoke one CN identity; never generates or exports a private key."""
import argparse,datetime,fcntl,hashlib,json,os,pathlib,re,secrets,subprocess,tempfile

def atomic(path,data):
 path=pathlib.Path(path);fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=str(path.parent))
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def openssl(args):
 r=subprocess.run(['/usr/bin/openssl']+args,stdin=subprocess.DEVNULL,capture_output=True)
 if r.returncode:raise RuntimeError('openssl_step_failed:'+args[0])
 return r.stdout

def state(ca):
 ca=pathlib.Path(ca).resolve()
 for name in ['ca.pem','ca-key.pem','allowed-serial']:
  p=ca/name
  if p.is_symlink() or not p.is_file():raise ValueError('existing regular CA/allow-list files required')
 if ca.stat().st_mode&0o022:raise ValueError('CA directory is writable by another identity')
 registry=ca/'fleet-registry.json'
 if registry.is_symlink():raise ValueError('unsafe registry')
 data=json.loads(registry.read_text()) if registry.exists() else {'schema':1,'devices':{}}
 if data.get('schema')!=1 or not isinstance(data.get('devices'),dict):raise ValueError('invalid registry; never replace it with an empty one')
 for device,item in data['devices'].items():
  if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}',device) or not isinstance(item,dict):raise ValueError('invalid device record')
  serial=item.get('serial','')
  if not re.fullmatch(r'[0-9a-f]+',serial) or item.get('status') not in ['pending','active','revoked']:raise ValueError('invalid registry identity')
  if item.get('cert_relative')!=str(pathlib.Path('fleet-certificates')/device/(serial+'.pem')):raise ValueError('unsafe certificate path in registry')
 allowed=set()
 for x in (ca/'allowed-serial').read_text().split():
  if not re.fullmatch(r'[0-9a-fA-F]+',x):raise ValueError('invalid existing allow-list; review before mutation')
  allowed.add(format(int(x,16),'x'))
 return ca,registry,data,allowed

def locked(ca):
 ca=pathlib.Path(ca).resolve();fd=os.open(ca/'fleet-issuance.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.fchmod(fd,0o600);fcntl.flock(fd,fcntl.LOCK_EX);return fd

def write_allowed(ca,allowed):atomic(ca/'allowed-serial',(''.join(x+'\n' for x in sorted(allowed))).encode())
def enroll(ca_dir,device,csr,output,days=90):
 if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}',device):raise ValueError('invalid device_id')
 if not 1<=days<=90:raise ValueError('leaf lifetime must be 1..90 days')
 csr=pathlib.Path(csr).resolve();digest=hashlib.sha256(csr.read_bytes()).hexdigest();fd=locked(ca_dir)
 try:
  ca,registry,data,allowed=state(ca_dir);openssl(['req','-in',str(csr),'-verify','-noout'])
  subject=openssl(['req','-in',str(csr),'-noout','-subject','-nameopt','RFC2253']).decode().strip()
  if subject.partition('subject=')[2].strip()!='CN=cn-agent-'+device:raise ValueError('CSR subject does not match device_id')
  item=data['devices'].get(device)
  if item:
   if item['status']=='revoked':raise ValueError('revoked device requires explicit rotation approval')
   if item['days']!=days:raise ValueError('existing certificate lifetime differs; explicit rotation required')
   if item['csr_sha256']!=digest:raise ValueError('different CSR for existing device; explicit rotation required')
   cert=ca/item['cert_relative'];assert hashlib.sha256(cert.read_bytes()).hexdigest()==item['cert_sha256'],'certificate_changed'
   if item['status']=='active' and item['serial'] not in allowed:raise ValueError('identity was removed externally; refuse to silently readmit')
  else:
   openssl(['x509','-in',str(ca/'ca.pem'),'-noout','-checkend',str(days*86400)])
   serial=format(secrets.randbits(127)+1,'x')
   while serial in allowed:serial=format(secrets.randbits(127)+1,'x')
   relative=pathlib.Path('fleet-certificates')/device/(serial+'.pem');cert=ca/relative;cert.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
   ext=ca/'fleet-client-extensions.cnf';atomic(ext,b'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=clientAuth\n')
   # CSR extensions are not copied; issuer controls CA:false and clientAuth.
   openssl(['x509','-req','-in',str(csr),'-CA',str(ca/'ca.pem'),'-CAkey',str(ca/'ca-key.pem'),'-set_serial','0x'+serial,'-days',str(days),'-sha256','-extfile',str(ext),'-out',str(cert)])
   cert.chmod(0o600);openssl(['verify','-CAfile',str(ca/'ca.pem'),str(cert)])
   item={'status':'pending','serial':serial,'csr_sha256':digest,'cert_sha256':hashlib.sha256(cert.read_bytes()).hexdigest(),'cert_relative':str(relative),'issued_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'days':days}
   data['devices'][device]=item;atomic(registry,json.dumps(data,indent=2).encode())
  if item['status']=='pending':
   allowed.add(item['serial']);write_allowed(ca,allowed);item['status']='active';atomic(registry,json.dumps(data,indent=2).encode())
  if cert.is_symlink():raise ValueError('unsafe stored certificate')
  openssl(['verify','-purpose','sslclient','-CAfile',str(ca/'ca.pem'),str(cert)])
  output=pathlib.Path(output)
  if output.is_symlink():raise ValueError('unsafe output directory')
  output.mkdir(parents=True,mode=0o700,exist_ok=True)
  for name,src in [('client.pem',cert),('ca.pem',ca/'ca.pem')]:
   dst=output/name
   if dst.is_symlink():raise ValueError('unsafe output file')
   atomic(dst,src.read_bytes())
  metadata={'device_id':device,'serial':item['serial'],'certificate_sha256':item['cert_sha256'],'private_key_included':False}
  atomic(output/'metadata.json',json.dumps(metadata,indent=2).encode());return metadata
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

def revoke(ca_dir,device):
 fd=locked(ca_dir)
 try:
  ca,registry,data,allowed=state(ca_dir);item=data['devices'].get(device)
  if not item:raise ValueError('unknown device; never remove an unmanaged serial')
  allowed.discard(item['serial']);write_allowed(ca,allowed);item['status']='revoked';atomic(registry,json.dumps(data,indent=2).encode())
  return {'device_id':device,'revoked':True,'existing_streams_may_require_disconnect':True}
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['enroll','revoke','list']);p.add_argument('--ca-dir',required=True);p.add_argument('--device-id');p.add_argument('--csr');p.add_argument('--out');p.add_argument('--days',type=int,default=90);a=p.parse_args()
 if a.action=='enroll':
  if not all([a.device_id,a.csr,a.out]):p.error('enroll requires --device-id --csr --out')
  result=enroll(a.ca_dir,a.device_id,a.csr,a.out,a.days)
 elif a.action=='revoke':
  if not a.device_id:p.error('revoke requires --device-id')
  result=revoke(a.ca_dir,a.device_id)
 else:
  fd=locked(a.ca_dir)
  try:ca,f,data,allowed=state(a.ca_dir);result={'devices':{k:{x:v.get(x) for x in ['status','serial','issued_utc','days']} for k,v in data['devices'].items()},'unmanaged_serials_preserved':len(allowed-{v['serial'] for v in data['devices'].values()})}
  finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
 print(json.dumps(result))
