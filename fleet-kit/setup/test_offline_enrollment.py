"""Real cryptographic round trips; no live JP registration or privileged CN changes."""
import base64,copy,importlib.util,json,pathlib,subprocess,sys,tempfile,time,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'admin'))
import enrollment,issue_access
s=importlib.util.spec_from_file_location('cn_installer',ROOT/'setup/install.py');cn=importlib.util.module_from_spec(s);s.loader.exec_module(cn)

class OfflineEnrollmentTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.p=pathlib.Path(cls.temp.name);cls.ca=cls.p/'ca';cls.ca.mkdir(mode=0o700)
  def ssl(*a):return enrollment.openssl(list(a))
  cls.ssl=staticmethod(ssl)
  ssl('ecparam','-name','prime256v1','-genkey','-noout','-out',cls.ca/'ca-key.pem')
  ssl('req','-x509','-new','-key',cls.ca/'ca-key.pem','-out',cls.ca/'ca.pem','-days','100','-subj','/CN=test-CA')
  cls.cert,cls.key=issue_access.signer(cls.ca,48)
  cls.csr=cls.p/'client.csr';cls.ck=cls.p/'client-key';cls.client=cls.p/'client.pem'
  ssl('req','-new','-newkey','rsa:2048','-nodes','-keyout',cls.ck,'-out',cls.csr,'-subj','/CN=cn-agent-cn-test')
  ext=cls.p/'client.ext';ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=clientAuth\n')
  ssl('x509','-req','-in',cls.csr,'-CA',cls.ca/'ca.pem','-CAkey',cls.ca/'ca-key.pem','-set_serial','0x123abc','-days','90','-extfile',ext,'-out',cls.client)
  cls.request=enrollment.request_for({'device_id':'cn-test','jp_host':'10.9.8.30','jp_api_port':43425,'jp_egress_port':43480,'jp_model_id':'codex/gpt-6.1-sol'},cls.csr.read_text(),'a'*64,int(time.time()),cls.ca/'ca.pem')
  cls.delivery={'serial':'123abc','gateway_key_id':'public-key-id','gateway_key':'public-test-gateway-key-not-real','client.pem':cls.client.read_text()}
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def bundle(self,omit=False):return enrollment.create_bundle(self.delivery,self.request,self.cert,self.key,omit_key=omit)
 def test_root_rejects_forged_bundle_before_identity_or_file_access(self):
  s=importlib.util.spec_from_file_location('offline_root',ROOT/'setup/root_install.py');ri=importlib.util.module_from_spec(s);s.loader.exec_module(ri)
  b=self.bundle();b['signature_b64']=base64.b64encode(b'forged').decode()
  with tempfile.TemporaryDirectory() as td:
   t=pathlib.Path(td);(t/'trust').mkdir();(t/'trust/jp-ca.pem').write_bytes((self.ca/'ca.pem').read_bytes());(t/'private').mkdir();(t/'private/enrollment-request.json').write_bytes(enrollment.canonical(self.request))
   with mock.patch.object(ri,'ROOT',t),mock.patch.object(ri.pwd,'getpwnam',side_effect=AssertionError('must reject first')),mock.patch.object(ri,'write') as write:
    with self.assertRaises(ValueError):ri.configure(self.request['route'],{'prepared':True},lambda:None,t,{'access_bundle':b})
    write.assert_not_called()
 def test_root_checks_private_key_before_overwriting_active_certificate(self):
  from types import SimpleNamespace
  s=importlib.util.spec_from_file_location('offline_root',ROOT/'setup/root_install.py');ri=importlib.util.module_from_spec(s);s.loader.exec_module(ri)
  with tempfile.TemporaryDirectory() as td:
   t=pathlib.Path(td);(t/'trust').mkdir();(t/'trust/jp-ca.pem').write_bytes((self.ca/'ca.pem').read_bytes());(t/'private').mkdir();(t/'private/enrollment-request.json').write_bytes(enrollment.canonical(self.request))
   network=t/'network';network.mkdir();(network/'client.pem').write_text('unchanged');(network/'client-key.pem').write_bytes(self.key.read_bytes())
   c=dict(self.request['route'],device_id='cn-test',agent_user='testagent',network_user='testnet');u=SimpleNamespace(pw_dir=str(network),pw_uid=1,pw_gid=1)
   with mock.patch.object(ri,'ROOT',t),mock.patch.object(ri.pwd,'getpwnam',return_value=u),mock.patch.object(ri,'write') as write:
    with self.assertRaisesRegex(ValueError,'certificate_key_mismatch'):ri.configure(c,{'prepared':True},lambda:None,t,{'access_bundle':self.bundle()})
    write.assert_not_called();self.assertEqual((network/'client.pem').read_text(),'unchanged')
 def test_administrator_issue_roundtrip_and_resume_in_temporary_JP(self):
  import shutil,plistlib,contextlib,io
  with tempfile.TemporaryDirectory() as td:
   h=pathlib.Path(td);kit=h/'admin-kit';(kit/'trust').mkdir(parents=True);shutil.copy2(self.ca/'ca.pem',kit/'trust/jp-ca.pem');shutil.copy2(ROOT/'issue_client.py',kit/'issue_client.py')
   ca=h/'ai/cn-agent-egress-pilot/wg-private';ca.mkdir(parents=True,mode=0o700)
   for name in ['ca.pem','ca-key.pem']:shutil.copy2(self.ca/name,ca/name)
   (ca/'allowed-serial').write_text('abcdef\n')
   config=h/'.config/magpie';config.mkdir(parents=True);(config/'caller-keys.json').write_text('[]')
   native=h/'native';native.write_text('#!/usr/bin/env python3\nimport json,os,pathlib\np=pathlib.Path(os.environ["XDG_CONFIG_HOME"])/"magpie/caller-keys.json"\np.write_text(json.dumps([{"id":"new-id","name":"cn-cn-test","secret":"public-test-gateway-key-not-real"}]))\nprint("public-test-gateway-key-not-real")\n');native.chmod(0o755)
   d=h/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json';d.parent.mkdir(parents=True);d.write_text(json.dumps({'binary':str(native),'binarySHA256':enrollment.sha(native.read_bytes()),'configDir':str(config)}))
   jobs=h/'Library/LaunchAgents';jobs.mkdir(parents=True)
   for role,port in [('api',43425),('egress',43480)]:
    (jobs/('local.cn-agent-wireguard.'+role+'.plist')).write_bytes(plistlib.dumps({'ProgramArguments':['test',str(ca/'allowed-serial'),'10.9.8.30:'+str(port)]}))
   output=h/'device.access.json';captured=io.StringIO()
   with mock.patch.object(issue_access,'ROOT',kit),mock.patch.object(pathlib.Path,'home',return_value=h),contextlib.redirect_stdout(captured):
    first=issue_access.issue(self.request,output);second=issue_access.issue(self.request,output)
    omitted=h/'manual.access.json';manual=issue_access.issue(self.request,omitted,omit_key=True)
   self.assertNotIn(self.delivery['gateway_key'],captured.getvalue());self.assertFalse(first['reused']);self.assertTrue(second['reused']);self.assertFalse(manual['api_key_included'])
   self.assertEqual(output.stat().st_mode&0o777,0o600);self.assertEqual((ca/'bundle-signing-key.pem').stat().st_mode&0o777,0o600)
   verified=enrollment.verify_bundle(enrollment.read(output),self.request,kit/'trust/jp-ca.pem');self.assertEqual(verified['gateway_key'],self.delivery['gateway_key'])
   self.assertNotIn('gateway_key',enrollment.verify_bundle(enrollment.read(omitted),self.request,kit/'trust/jp-ca.pem'))
   self.assertIn('abcdef',(ca/'allowed-serial').read_text());self.assertEqual(len(json.loads((config/'caller-keys.json').read_text())),1)
   state=json.loads((ca/'fleet-registry.json').read_text());state['devices']['cn-test']['status']='revoked';(ca/'fleet-registry.json').write_text(json.dumps(state))
   with mock.patch.object(issue_access,'ROOT',kit),mock.patch.object(pathlib.Path,'home',return_value=h),self.assertRaisesRegex(ValueError,'no_longer_active'):issue_access.issue(self.request,output)
 def test_invalid_bundle_duration_fails_before_registration(self):
  with mock.patch.object(issue_access,'enroll',side_effect=AssertionError('must not register')):
   with self.assertRaisesRegex(ValueError,'validity'):issue_access.issue(self.request,'unused',hours=169)
 def test_real_signed_bundle_imports_key_without_prompt(self):
  with tempfile.TemporaryDirectory() as td:
   f=pathlib.Path(td)/'access';f.write_bytes(enrollment.canonical(self.bundle()));prompt=mock.Mock(side_effect=AssertionError('must not prompt'))
   result=cn.bundle_import(f,self.request,self.ca/'ca.pem',prompt)
   self.assertIn('access_bundle',result);self.assertNotIn('manual_gateway_key',result);prompt.assert_not_called()
 def test_omitted_key_uses_private_prompt(self):
  with tempfile.TemporaryDirectory() as td:
   f=pathlib.Path(td)/'access';f.write_bytes(enrollment.canonical(self.bundle(True)));prompt=mock.Mock(return_value=self.delivery['gateway_key'])
   result=cn.bundle_import(f,self.request,self.ca/'ca.pem',prompt)
   self.assertEqual(result['manual_gateway_key'],self.delivery['gateway_key']);prompt.assert_called_once()
 def test_missing_key_rejects_noninteractive_input(self):
  with tempfile.TemporaryDirectory() as td:
   f=pathlib.Path(td)/'access';f.write_bytes(enrollment.canonical(self.bundle(True)))
   with mock.patch.object(sys.stdin,'isatty',return_value=False),self.assertRaisesRegex(ValueError,'private_interactive'):cn.bundle_import(f,self.request,self.ca/'ca.pem')
 def test_tampered_payload_rejected_before_prompt(self):
  bundle=self.bundle(True);data=base64.b64decode(bundle['payload_b64']).replace(b'public-key-id',b'forged-key-id');bundle['payload_b64']=base64.b64encode(data).decode()
  with tempfile.TemporaryDirectory() as td:
   f=pathlib.Path(td)/'access';f.write_bytes(enrollment.canonical(bundle));prompt=mock.Mock()
   with self.assertRaises(ValueError):cn.bundle_import(f,self.request,self.ca/'ca.pem',prompt)
   prompt.assert_not_called()
 def test_signature_tampering_rejected(self):
  b=self.bundle();b['signature_b64']=base64.b64encode(b'wrong signature').decode()
  with self.assertRaises(ValueError):enrollment.verify_bundle(b,self.request,self.ca/'ca.pem')
 def test_other_request_nonce_and_device_rejected(self):
  for key,value in [('nonce','b'*64),('device_id','cn-other')]:
   r=copy.deepcopy(self.request);r[key]=value
   with self.assertRaisesRegex(ValueError,'not_for_this_request'):enrollment.verify_bundle(self.bundle(),r,self.ca/'ca.pem')
 def test_expired_bundle_rejected(self):
  with self.assertRaisesRegex(ValueError,'expired'):enrollment.verify_bundle(self.bundle(),self.request,self.ca/'ca.pem',now=int(time.time())+49*3600)
 def test_client_certificate_cannot_sign_access_bundles(self):
  b=enrollment.create_bundle(self.delivery,self.request,self.client,self.ck)
  with self.assertRaisesRegex(ValueError,'signer_purpose'):enrollment.verify_bundle(b,self.request,self.ca/'ca.pem')
 def test_wrong_client_certificate_rejected(self):
  d=dict(self.delivery);d['client.pem']=self.cert.read_text();b=enrollment.create_bundle(d,self.request,self.cert,self.key)
  with self.assertRaises(ValueError):enrollment.verify_bundle(b,self.request,self.ca/'ca.pem')
 def test_request_route_tampering_rejected(self):
  r=copy.deepcopy(self.request);r['route']['jp_host']='192.168.1.1'
  with self.assertRaisesRegex(ValueError,'unsupported_JP_route'):enrollment.validate_request(r,self.ca/'ca.pem')
 def test_untrusted_CA_rejected(self):
  r=copy.deepcopy(self.request);r['ca_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'CA_mismatch'):enrollment.verify_bundle(self.bundle(),r,self.ca/'ca.pem')
 def test_duplicate_JSON_fields_rejected(self):
  with self.assertRaisesRegex(ValueError,'duplicate_json'):enrollment.loads('{"schema":1,"schema":2}')
 def test_CN_code_has_no_JP_login_or_remote_command(self):
  for name in ['install.py','root_install.py']:
   source=(ROOT/'setup'/name).read_text()
   self.assertNotIn('/usr/bin/ssh',source);self.assertNotIn('--jp-user',source);self.assertNotIn('StrictHostKeyChecking',source);self.assertNotIn('ho@',source)
 def test_public_request_export_has_no_private_key(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'request';cn.save_public_request(p,self.request)
   self.assertEqual(enrollment.read(p),self.request);self.assertNotIn('PRIVATE KEY',p.read_text());self.assertEqual(p.stat().st_mode&0o777,0o600)
 def test_private_prompt_rejects_header_injection(self):
  with tempfile.TemporaryDirectory() as td:
   f=pathlib.Path(td)/'access';f.write_bytes(enrollment.canonical(self.bundle(True)))
   with self.assertRaisesRegex(ValueError,'invalid_API_key'):cn.bundle_import(f,self.request,self.ca/'ca.pem',lambda _: 'x'*30+'\nHeader: evil')
if __name__=='__main__':unittest.main()
