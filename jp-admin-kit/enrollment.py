"""Offline enrollment wire format. CN contains only a pinned public CA, no JP login credential."""
import base64,hashlib,json,pathlib,re,subprocess,tempfile,time
DOMAIN=b'CN-AGENT-ACCESS-V1\n'
SIGNER_CN='CN Agent Enrollment Signing v1'
MAX_BYTES=128*1024

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def sha(data):return hashlib.sha256(data).hexdigest()
def _pairs(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise ValueError('duplicate_json_field')
  result[k]=v
 return result

def loads(data):
 if len(data)>MAX_BYTES:raise ValueError('enrollment_file_too_large')
 return json.loads(data,object_pairs_hook=_pairs)
def read(path):
 p=pathlib.Path(path)
 if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_BYTES:raise ValueError('invalid_enrollment_file')
 return loads(p.read_bytes())
def openssl(args):
 r=subprocess.run(['/usr/bin/openssl']+[str(x) for x in args],stdin=subprocess.DEVNULL,capture_output=True)
 if r.returncode:raise ValueError('enrollment_crypto_verification_failed')
 return r.stdout

def fingerprint(path):return sha(openssl(['x509','-in',path,'-outform','DER']))
def request_for(config,csr,nonce,created_at,ca_path):
 return {'schema':1,'device_id':config['device_id'],'csr':csr,'csr_sha256':sha(csr.encode()),'nonce':nonce,'created_at':created_at,'ca_sha256':fingerprint(ca_path),'route':{k:config[k] for k in ['jp_host','jp_api_port','jp_egress_port','jp_model_id']}}
def validate_request(r,ca_path):
 if not isinstance(r,dict) or set(r)!={'schema','device_id','csr','csr_sha256','nonce','created_at','ca_sha256','route'} or r['schema']!=1:raise ValueError('invalid_request_schema')
 if not isinstance(r['device_id'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}',r['device_id']):raise ValueError('invalid_device_id')
 if not isinstance(r['csr'],str) or len(r['csr'])>16384 or sha(r['csr'].encode())!=r['csr_sha256']:raise ValueError('request_CSR_digest_mismatch')
 if not isinstance(r['nonce'],str) or not re.fullmatch(r'[0-9a-f]{64}',r['nonce']):raise ValueError('invalid_request_nonce')
 if type(r['created_at']) is not int or r['created_at']>time.time()+300:raise ValueError('invalid_request_time')
 if r['ca_sha256']!=fingerprint(ca_path):raise ValueError('request_CA_mismatch')
 route=r['route']
 if not isinstance(route,dict) or set(route)!={'jp_host','jp_api_port','jp_egress_port','jp_model_id'}:raise ValueError('invalid_request_route')
 # This installer targets the existing, pinned JP deployment, not arbitrary hosts.
 if route['jp_host']!='10.9.8.30' or route['jp_api_port']!=43425 or route['jp_egress_port']!=43480:raise ValueError('unsupported_JP_route')
 if not isinstance(route['jp_model_id'],str) or not re.fullmatch(r'[A-Za-z0-9_./:@-]+',route['jp_model_id']):raise ValueError('invalid_request_model')
 return r

def create_bundle(delivery,request,signer_cert,signer_key,hours=48,omit_key=False):
 if not 1<=hours<=168:raise ValueError('bundle_validity_must_be_1_to_168_hours')
 now=int(time.time());payload={'schema':1,'device_id':request['device_id'],'request_sha256':sha(canonical(request)),'csr_sha256':request['csr_sha256'],'ca_sha256':request['ca_sha256'],'route':request['route'],'issued_at':now,'expires_at':now+hours*3600,'serial':delivery['serial'],'gateway_key_id':delivery['gateway_key_id'],'client.pem':delivery['client.pem']}
 if not omit_key:payload['gateway_key']=delivery['gateway_key']
 data=DOMAIN+canonical(payload)
 with tempfile.TemporaryDirectory() as td:
  f=pathlib.Path(td)/'message';f.write_bytes(data);signature=openssl(['dgst','-sha256','-sign',signer_key,f])
 return {'schema':1,'payload_b64':base64.b64encode(data).decode(),'signature_b64':base64.b64encode(signature).decode(),'signer_cert_pem':pathlib.Path(signer_cert).read_text()}

def verify_bundle(envelope,request,ca_path,now=None):
 validate_request(request,ca_path)
 if not isinstance(envelope,dict) or set(envelope)!={'schema','payload_b64','signature_b64','signer_cert_pem'} or envelope['schema']!=1:raise ValueError('invalid_access_bundle_schema')
 if len(canonical(envelope))>MAX_BYTES:raise ValueError('enrollment_file_too_large')
 try:data=base64.b64decode(envelope['payload_b64'],validate=True);sig=base64.b64decode(envelope['signature_b64'],validate=True)
 except Exception:raise ValueError('invalid_access_bundle_encoding')
 if not data.startswith(DOMAIN):raise ValueError('invalid_access_bundle_domain')
 with tempfile.TemporaryDirectory() as td:
  td=pathlib.Path(td);cert=td/'signer.pem';message=td/'message';signature=td/'signature';pub=td/'public.pem'
  cert.write_text(envelope['signer_cert_pem']);message.write_bytes(data);signature.write_bytes(sig)
  openssl(['verify','-purpose','any','-CAfile',ca_path,cert])
  subject=openssl(['x509','-in',cert,'-noout','-subject','-nameopt','RFC2253']).decode().partition('subject=')[2].strip()
  text=openssl(['x509','-in',cert,'-text','-noout']).decode()
  if subject!='CN='+SIGNER_CN or 'Code Signing' not in text or 'CA:FALSE' not in text or 'TLS Web Client Authentication' in text:raise ValueError('invalid_enrollment_signer_purpose')
  pub.write_bytes(openssl(['x509','-in',cert,'-pubkey','-noout']))
  openssl(['dgst','-sha256','-verify',pub,'-signature',signature,message])
 payload=loads(data[len(DOMAIN):]);fields={'schema','device_id','request_sha256','csr_sha256','ca_sha256','route','issued_at','expires_at','serial','gateway_key_id','client.pem'}
 if not isinstance(payload,dict) or set(payload) not in [fields,fields|{'gateway_key'}] or payload.get('schema')!=1:raise ValueError('invalid_access_payload_schema')
 for field,value in [('device_id',request['device_id']),('request_sha256',sha(canonical(request))),('csr_sha256',request['csr_sha256']),('ca_sha256',request['ca_sha256']),('route',request['route'])]:
  if payload.get(field)!=value:raise ValueError('access_bundle_not_for_this_request')
 now=int(time.time()) if now is None else now
 if type(payload['issued_at']) is not int or type(payload['expires_at']) is not int or payload['issued_at']>now+300 or payload['expires_at']<=now or not 0<payload['expires_at']-payload['issued_at']<=168*3600:raise ValueError('access_bundle_expired_or_invalid_time')
 if not isinstance(payload['serial'],str) or not re.fullmatch(r'[0-9a-f]+',payload['serial']):raise ValueError('invalid_access_serial')
 if 'gateway_key' in payload and (not isinstance(payload['gateway_key'],str) or not 20<=len(payload['gateway_key'])<=4096 or any(x in payload['gateway_key'] for x in '\r\n\x00')):raise ValueError('invalid_gateway_key')
 with tempfile.TemporaryDirectory() as td:
  td=pathlib.Path(td);client=td/'client.pem';csr=td/'client.csr'
  client.write_text(payload['client.pem']);csr.write_text(request['csr'])
  openssl(['verify','-purpose','sslclient','-CAfile',ca_path,client])
  if openssl(['x509','-in',client,'-pubkey','-noout'])!=openssl(['req','-in',csr,'-pubkey','-noout']):raise ValueError('access_certificate_not_for_this_CSR')
  subject=openssl(['x509','-in',client,'-noout','-subject','-nameopt','RFC2253']).decode().partition('subject=')[2].strip()
  serial=openssl(['x509','-in',client,'-noout','-serial']).decode().strip().partition('=')[2]
  if subject!='CN=cn-agent-'+request['device_id'] or format(int(serial,16),'x')!=payload['serial']:raise ValueError('access_certificate_identity_mismatch')
 payload['ca.pem']=pathlib.Path(ca_path).read_text()
 return payload
