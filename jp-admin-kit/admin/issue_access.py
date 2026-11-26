#!/usr/bin/env python3
"""Run locally on JP by its administrator. No SSH login or remote administration in CN installer."""
import argparse,fcntl,json,os,pathlib,secrets,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import enrollment
from jp_enroll import enroll
import device_budget

def signer(ca,hours):
 ca=pathlib.Path(ca);fd=os.open(ca/'bundle-signing.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(fd,fcntl.LOCK_EX)
 try:
  key=ca/'bundle-signing-key.pem';cert=ca/'bundle-signing-cert.pem'
  if key.is_symlink() or cert.is_symlink():raise ValueError('unsafe_signing_identity')
  if key.exists()!=cert.exists():raise ValueError('incomplete_signing_identity_review_required')
  if not key.exists():
   # A dedicated CA:false/codeSigning identity signs access bundles. The CA key
   # only signs this X.509 certificate; it never signs arbitrary bundle bodies.
   enrollment.openssl(['x509','-in',ca/'ca.pem','-noout','-checkend',str(90*86400)])
   import tempfile
   with tempfile.TemporaryDirectory(dir=str(ca),prefix='signer-') as td:
    td=pathlib.Path(td);k=td/'key';csr=td/'csr';c=td/'cert';ext=td/'extensions'
    enrollment.openssl(['req','-new','-newkey','rsa:2048','-nodes','-keyout',k,'-out',csr,'-subj','/CN='+enrollment.SIGNER_CN]);k.chmod(0o600)
    ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=codeSigning\n')
    enrollment.openssl(['x509','-req','-in',csr,'-CA',ca/'ca.pem','-CAkey',ca/'ca-key.pem','-set_serial','0x'+format(secrets.randbits(127)+1,'x'),'-days','90','-sha256','-extfile',ext,'-out',c])
    c.chmod(0o600);os.replace(k,key);os.replace(c,cert)
  if key.stat().st_mode&0o077:raise ValueError('signing_private_key_permissions_invalid')
  enrollment.openssl(['verify','-purpose','any','-CAfile',ca/'ca.pem',cert]);enrollment.openssl(['x509','-in',cert,'-noout','-checkend',str(hours*3600)])
  if enrollment.openssl(['x509','-in',cert,'-pubkey','-noout'])!=enrollment.openssl(['pkey','-in',key,'-pubout']):raise ValueError('signing_identity_key_mismatch')
  return cert,key
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

def issue(request,out,hours=48,omit_key=False,budget_policy=None):
 budget_policy=device_budget.validate(budget_policy)
 import time
 if type(hours) is not int or not 1<=hours<=168:raise ValueError('bundle_validity_must_be_1_to_168_hours')
 pinned=ROOT/'trust/jp-ca.pem';enrollment.validate_request(request,pinned)
 if time.time()-request['created_at']>7*86400:raise ValueError('enrollment_request_expired_regenerate_on_CN')
 ca=pathlib.Path.home()/'ai/cn-agent-egress-pilot/wg-private'
 if enrollment.fingerprint(ca/'ca.pem')!=enrollment.fingerprint(pinned):raise ValueError('JP_CA_does_not_match_installer_trust')
 out=pathlib.Path(out)
 if out.is_symlink():raise ValueError('unsafe_output_file')
 if out.exists():
  payload=enrollment.verify_bundle(enrollment.read(out),request,pinned)
  if ('gateway_key' not in payload)!=omit_key:raise ValueError('existing_bundle_key_mode_differs')
  registry=json.loads((ca/'fleet-registry.json').read_text())['devices'].get(request['device_id'],{})
  allowed={format(int(x,16),'x') for x in (ca/'allowed-serial').read_text().split()}
  if registry.get('status')!='active' or registry.get('serial')!=payload['serial'] or payload['serial'] not in allowed:raise ValueError('existing_access_identity_no_longer_active')
  record=json.loads((ca/'fleet-delivery'/(request['device_id']+'.json')).read_text())
  d=json.loads((pathlib.Path.home()/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json').read_text())
  if enrollment.sha(pathlib.Path(d['binary']).read_bytes())!=d['binarySHA256']:raise ValueError('JP_binary_pin_changed')
  keys=json.loads((pathlib.Path(d['configDir'])/'caller-keys.json').read_text());matches=[x for x in keys if x.get('id')==payload['gateway_key_id']]
  if len(matches)!=1 or matches[0].get('off') or record.get('gateway_key_id')!=payload['gateway_key_id'] or record.get('serial')!=payload['serial']:raise ValueError('existing_access_gateway_key_changed')
  if not omit_key and payload['gateway_key']!=record.get('gateway_key'):raise ValueError('existing_access_gateway_key_changed')
  if record.get('budget') is None or device_budget.validate(record['budget'])!=budget_policy or not device_budget.matches(matches[0],budget_policy):raise ValueError('existing_access_budget_changed_or_unverified')
  return {'budget':budget_policy,'issued':True,'reused':True,'device_id':request['device_id'],'api_key_included':not omit_key,'out':str(out)}
 cert,key=signer(ca,hours)
 delivery=enroll(request,(ROOT/'issue_client.py').read_text(),budget_policy=budget_policy)
 bundle=enrollment.create_bundle(delivery,request,cert,key,hours,omit_key)
 # Recheck live server policy before writing a sensitive delivery file.
 d=enrollment.read(pathlib.Path.home()/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json')
 _,live_key=device_budget.read_key(pathlib.Path(d['configDir']),delivery['gateway_key_id'])
 if not device_budget.matches(live_key,budget_policy):raise ValueError('budget_changed_before_delivery')
 # Validate everything locally before writing a sensitive delivery file.
 enrollment.verify_bundle(bundle,request,pinned)
 out.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(enrollment.canonical(bundle));f.flush();os.fsync(f.fileno())
 return {'budget':budget_policy,'issued':True,'reused':False,'device_id':request['device_id'],'api_key_included':not omit_key,'valid_hours':hours,'out':str(out),'JP_restart_required':False}

def main():
 os.umask(0o077)
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--out',required=True);p.add_argument('--approve',action='store_true');p.add_argument('--omit-api-key',action='store_true');p.add_argument('--valid-hours',type=int,default=48);p.add_argument('--period',choices=['day','week','month']);p.add_argument('--tokens',type=int);p.add_argument('--cost',type=float);p.add_argument('--cache-reads',action='store_true');p.add_argument('--unlimited',action='store_true');a=p.parse_args()
 request=enrollment.read(a.request);enrollment.validate_request(request,ROOT/'trust/jp-ca.pem')
 print(json.dumps({'device_id':request['device_id'],'CSR_digest':request['csr_sha256'],'route':request['route'],'approval_given':a.approve}),flush=True)
 if a.approve or any(x is not None for x in [a.period,a.tokens,a.cost]) or a.unlimited or a.cache_reads:
  chosen=device_budget.policy(a.period,a.tokens,a.cost,a.cache_reads,a.unlimited)
  print(json.dumps({'budget':chosen,'applied':False}),flush=True)
 if a.approve:print(json.dumps(issue(request,a.out,a.valid_hours,a.omit_api_key,budget_policy=chosen)))
 else:print('Review device and request through your trusted channel, then rerun with --approve. No registration changed.')
if __name__=='__main__':
 try:main()
 except Exception as e:print('JP issuance stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__)+'. No secret printed.',file=sys.stderr);sys.exit(1)
