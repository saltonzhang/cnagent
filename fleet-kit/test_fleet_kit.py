import importlib.util,json,pathlib,subprocess,tempfile,unittest,sys,concurrent.futures,shutil
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from render import render,validate
from issue_client import enroll,revoke

class RenderTests(unittest.TestCase):
 def config(self):return {'device_id':'cn-test-002','operator_user':'operator2','operator_home':'/Users/operator2','agent_user':'teamagent','network_user':'teamnet','agent_home':'/Users/teamagent','network_home':'/var/db/team-net','jp_host':'10.20.30.40','cn_api_port':3535,'api_adapter_port':45337,'web_proxy_port':19190}
 def test_parameterization_and_syntax(self):
  with tempfile.TemporaryDirectory() as t:
   out=pathlib.Path(t)/'stage';render(self.config(),out)
   for p in out.iterdir():
    text=p.read_text(errors='replace') if p.suffix!='.plist' else ''
    self.assertNotIn('@@',text);self.assertNotIn('salton-',text);self.assertNotIn('10.9.8.30',text)
   launch=(out/'launch').read_text();self.assertIn('TERM="$terminal_type"',launch);self.assertNotIn('claude|codex|shell',launch)
   subprocess.run(['/bin/bash','-n',str(out/'launch')],check=True)
   compile((out/'supervisor.py').read_text(),str(out/'supervisor.py'),'exec');compile((out/'probe.py').read_text(),str(out/'probe.py'),'exec')
   pf=(out/'pilot.pf').read_text();self.assertIn('user teamnet flags any',pf);self.assertIn('to 10.20.30.40',pf)
   self.assertIn('__READ_FROM_PROTECTED_DEVICE_KEY_FILE__',(out/'providers.template.json').read_text())
   self.assertIn('--public-check',(out/'probe.py').read_text());self.assertNotIn("('directInternet'",(out/'probe.py').read_text())
 def test_reject_unsafe_config(self):
  for patch in [{'operator_user':'x; id'},{'agent_home':'/Users/x/../operator2'},{'jp_host':'127.0.0.1'},{'python_binary':'/Users/operator2/bin/python3'},{'install_base':'/Users/teamagent/code'},{'enable_codex':True},{'web_proxy_port':3535},{'gateway_key':'secret'}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):validate(dict(self.config(),**patch))
 def test_existing_staging_refused(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):render(self.config(),t)

class IssuerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.tmp.name);self.ca=self.p/'ca';self.ca.mkdir(mode=0o700)
  self.openssl(['req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=Fleet-Isolated-Test-CA','-days','365','-keyout',str(self.ca/'ca-key.pem'),'-out',str(self.ca/'ca.pem')]);(self.ca/'allowed-serial').write_text('000abc\n')
 def tearDown(self):self.tmp.cleanup()
 def openssl(self,args):subprocess.run(['/usr/bin/openssl']+args,check=True,stdin=subprocess.DEVNULL,capture_output=True)
 def csr(self,name):
  csr=self.p/(name+'.csr');self.openssl(['req','-new','-newkey','rsa:2048','-nodes','-subj','/CN=cn-agent-'+name,'-keyout',str(self.p/(name+'.key')),'-out',str(csr)]);return csr
 def test_enroll_idempotence_and_targeted_revoke(self):
  csr=self.csr('cn-a');one=enroll(self.ca,'cn-a',csr,self.p/'out-a');two=enroll(self.ca,'cn-a',csr,self.p/'out-a')
  self.assertEqual(one['serial'],two['serial']);self.assertFalse(one['private_key_included']);self.assertIn('abc',(self.ca/'allowed-serial').read_text().split())
  other=enroll(self.ca,'cn-b',self.csr('cn-b'),self.p/'out-b');revoke(self.ca,'cn-a');allowed=(self.ca/'allowed-serial').read_text().split();self.assertNotIn(one['serial'],allowed);self.assertIn(other['serial'],allowed);self.assertIn('abc',allowed)
  self.assertFalse(any('key' in f.name for f in (self.p/'out-a').iterdir()))
  with self.assertRaises(ValueError):enroll(self.ca,'cn-a',csr,self.p/'out-a')
 def test_wrong_identity_and_corrupt_registry_fail_closed(self):
  before=(self.ca/'allowed-serial').read_bytes()
  with self.assertRaises(ValueError):enroll(self.ca,'cn-a',self.csr('cn-b'),self.p/'wrong')
  self.assertEqual(before,(self.ca/'allowed-serial').read_bytes());(self.ca/'fleet-registry.json').write_text('{bad')
  with self.assertRaises(json.JSONDecodeError):enroll(self.ca,'cn-a',self.csr('cn-a'),self.p/'bad')
  self.assertEqual(before,(self.ca/'allowed-serial').read_bytes())
 def test_existing_device_cannot_be_silently_reissued(self):
  csr=self.csr('cn-a');enroll(self.ca,'cn-a',csr,self.p/'a');before=(self.ca/'allowed-serial').read_bytes()
  replacement=self.csr('cn-a')
  with self.assertRaises(ValueError):enroll(self.ca,'cn-a',replacement,self.p/'a')
  self.assertEqual(before,(self.ca/'allowed-serial').read_bytes())
 @unittest.skipUnless(shutil.which('go'),'management-host Go required only for PKI interoperability test')
 def test_go_generated_ca_interoperability(self):
  ca=self.p/'go-ca';subprocess.run(['go','run','.','-role','generate','-dir',str(ca)],cwd=ROOT/'transport-src',check=True,capture_output=True)
  before=set((ca/'allowed-serial').read_text().split());result=enroll(ca,'cn-go',self.csr('cn-go'),self.p/'go-out')
  after=set((ca/'allowed-serial').read_text().split());self.assertTrue(before.issubset(after));self.assertIn(result['serial'],after)
 def test_registry_cannot_export_arbitrary_file(self):
  csr=self.csr('cn-a');enroll(self.ca,'cn-a',csr,self.p/'a');f=self.ca/'fleet-registry.json';d=json.loads(f.read_text());d['devices']['cn-a']['cert_relative']='ca-key.pem';f.write_text(json.dumps(d));before=(self.ca/'allowed-serial').read_bytes()
  with self.assertRaises(ValueError):enroll(self.ca,'cn-a',csr,self.p/'export')
  self.assertFalse((self.p/'export').exists());self.assertEqual(before,(self.ca/'allowed-serial').read_bytes())
 def test_parallel_registration_preserves_all_devices(self):
  jobs=[]
  for name in ['cn-a','cn-b']:
   csr=self.csr(name);jobs.append(subprocess.Popen([sys.executable,str(ROOT/'issue_client.py'),'enroll','--ca-dir',str(self.ca),'--device-id',name,'--csr',str(csr),'--out',str(self.p/name)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
  results=[]
  try:
   for job in jobs:
    out,err=job.communicate(timeout=30);results.append((job.returncode,out,err))
  finally:
   for job in jobs:
    if job.poll() is None:job.kill();job.communicate()
  serials=[]
  for code,out,err in results:
   self.assertEqual(code,0,err);serials.append(json.loads(out)['serial'])
  allowed=(self.ca/'allowed-serial').read_text().split();self.assertTrue(set(serials).issubset(allowed));self.assertIn('abc',allowed)

if __name__=='__main__':unittest.main()
