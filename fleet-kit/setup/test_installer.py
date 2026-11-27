import importlib.util,json,os,pathlib,plistlib,subprocess,tempfile,unittest,sys
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'admin'))
def module(name,path):
 s=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
ri=module('root_install',ROOT/'setup/root_install.py');jp=module('jp_enroll',ROOT/'admin/jp_enroll.py')
ac=module('accept',ROOT/'setup/accept.py')
class InstallerTests(unittest.TestCase):
 def test_permissions_under_umask_and_resume(self):
  with tempfile.TemporaryDirectory() as td:
   h=pathlib.Path(td);old=os.umask(0o077)
   try:
    for _ in range(2):
     for name,mode in [('managed',0o755),('private',0o700)]:
      p=ri.directory(h/name,mode,os.getuid(),os.getgid());self.assertEqual(p.stat().st_mode&0o777,mode)
     ri.agent_directories(h,os.getuid(),os.getgid())
     for name in ['.local','.local/bin','.config','.config/magpie']:
      p=h/name;self.assertEqual(p.stat().st_uid,os.getuid());self.assertEqual(p.stat().st_mode&0o777,0o700)
     saved=h/'.config/magpie/existing'
     if saved.exists():self.assertEqual(saved.read_text(),'preserve')
     saved.write_text('preserve');(h/'managed').chmod(0o700)
   finally:os.umask(old)
 def test_agent_parent_ownership_uses_service_uid(self):
  with tempfile.TemporaryDirectory() as td,mock.patch.object(ri.os,'chown') as chown:
   ri.agent_directories(td,502,20)
   for name in ['.local','.local/bin','workspace','.config','.config/magpie','.claude']:
    chown.assert_any_call(pathlib.Path(td)/name,502,20)
 def test_directory_symlink_refused(self):
  with tempfile.TemporaryDirectory() as td:
   h=pathlib.Path(td);(h/'target').mkdir();(h/'link').symlink_to(h/'target');before=(h/'target').stat().st_mode
   with self.assertRaisesRegex(ValueError,'symlink_directory'):ri.directory(h/'link',0o755,os.getuid(),os.getgid())
   self.assertEqual((h/'target').stat().st_mode,before)

 def test_pf_counter_parser_requires_specific_block(self):
  text='@6 block return out quick on lo0 inet proto tcp from any to 127.0.0.1 port = 3435\n  [ Evaluations: 99 Packets: 7 Bytes: 200 ]\n@7 pass out quick on lo0 port = 44337\n [ Packets: 90 ]\n'
  self.assertEqual(ac.blocked_packets(text,3435),7);self.assertIsNone(ac.blocked_packets(text,44337))

 def test_existing_root_anchor_is_not_reloaded(self):
  with mock.patch.object(ri,'run',return_value=b'anchor "com.apple/*" all\n') as r:ri.ensure_anchor(pathlib.Path('/not-live'),{},lambda:None)
  self.assertEqual(r.call_count,1)
 def test_active_or_nonempty_root_policy_never_replaced(self):
  for rules,info in [(b'block all\n',b'Status: Disabled'),(b'',b'Status: Enabled')]:
   with mock.patch.object(ri,'run',side_effect=[rules,info]),self.assertRaisesRegex(ValueError,'review_active_policy'):ri.ensure_anchor(pathlib.Path('/not-live'),{},lambda:None)
 def test_fresh_disabled_filter_load_does_not_flush_nat(self):
  commands=[];state={}
  def command(args):
   commands.append(list(map(str,args)))
   if args==['/sbin/pfctl','-sr']:return b'' if len(commands)==1 else b'anchor "com.apple/*" all\n'
   if args==['/sbin/pfctl','-s','info']:return b'Status: Disabled'
   return b''
  with mock.patch.object(ri,'run',side_effect=command),mock.patch.object(ri,'write'),mock.patch.object(pathlib.Path,'read_text',return_value='anchor "com.apple/*"\n'):ri.ensure_anchor(pathlib.Path('/not-live'),state,lambda:None)
  self.assertTrue(state['factory_filter_anchor_added']);self.assertTrue(any('-R' in c for c in commands));self.assertFalse(any('-F' in c for c in commands))
 def test_asset_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'software').mkdir();(p/'software/LOCK.json').write_text(json.dumps({'files':{'test':{'sha256':'0'*64}}}));(p/'software/test').write_text('invalid')
   with mock.patch.object(ri,'ROOT',p),self.assertRaisesRegex(ValueError,'hash_mismatch'):ri.assets()
 def test_asset_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'software').mkdir();(p/'a').write_text('x');(p/'software/test').symlink_to(p/'a');(p/'software/LOCK.json').write_text(json.dumps({'files':{'test':{'sha256':ri.digest(p/'a')}}}))
   with mock.patch.object(ri,'ROOT',p),self.assertRaises(ValueError):ri.assets()
 def test_unmanaged_account_not_adopted(self):
  c={'agent_user':'existing'}
  with mock.patch.object(ri.pwd,'getpwnam',return_value=object()),self.assertRaisesRegex(ValueError,'unmanaged'):ri.account(c,{},lambda:None,'agent_user','/Users/existing','/bin/zsh')
 def test_managed_account_identity_drift_rejected(self):
  from types import SimpleNamespace
  c={'agent_user':'existing'};j={'accounts':{'existing':{'uid':600,'home':'/Users/existing','complete':True}}}
  with mock.patch.object(ri.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=601,pw_dir='/Users/existing')),self.assertRaisesRegex(ValueError,'identity_changed'):ri.account(c,j,lambda:None,'agent_user','/Users/existing','/bin/zsh')
 def test_unprepared_config_rejected(self):
  with self.assertRaisesRegex(ValueError,'prepare_first'):ri.configure({}, {},lambda:None,pathlib.Path('/not-live'),{})
 def test_atomic_no_symlink_write(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'target').write_text('unchanged');(p/'link').symlink_to(p/'target')
   with self.assertRaises(ValueError):ri.write(p/'link','replacement')
   self.assertEqual((p/'target').read_text(),'unchanged')
 def test_install_sources_no_embedded_private_material(self):
  for p in (ROOT/'setup').glob('*.py'):
   if p.name=='test_installer.py':continue
   self.assertNotIn('BEGIN PRIVATE KEY',p.read_text());self.assertNotIn('NOPASSWD:ALL',p.read_text()) if p.name!='test_installer.py' else None
 def test_jp_enroll_real_certificate_and_idempotent_key(self):
  # Real CSR/CA/issuer in temp; only gateway executable is a deterministic mock.
  with tempfile.TemporaryDirectory() as td:
   h=pathlib.Path(td);b=h/'ai/cn-agent-egress-pilot';ca=b/'wg-private';ca.mkdir(parents=True,mode=0o700);config=h/'.config/magpie';config.mkdir(parents=True);(config/'caller-keys.json').write_text('[]')
   def ssl(*a):subprocess.run(['/usr/bin/openssl',*map(str,a)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   ssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout',ca/'ca-key.pem','-out',ca/'ca.pem','-days','100','-subj','/CN=test-ca');(ca/'allowed-serial').write_text('abcdef\n')
   ssl('req','-new','-newkey','rsa:2048','-nodes','-keyout',h/'local-key.pem','-out',h/'client.csr','-subj','/CN=cn-agent-cn-test')
   native=h/'magpie';native.write_text('#!/usr/bin/env python3\nimport json,os,pathlib\np=pathlib.Path(os.environ["XDG_CONFIG_HOME"])/"magpie/caller-keys.json"\np.write_text(json.dumps([{"id":"device-key-1","name":"cn-cn-test","secret":"public-test-secret-not-a-real-key"}]))\nprint("public-test-secret-not-a-real-key")\n');native.chmod(0o755)
   d=h/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json';d.parent.mkdir(parents=True);d.write_text(json.dumps({'binary':str(native),'binarySHA256':ri.digest(native),'configDir':str(config)}))
   jobs=h/'Library/LaunchAgents';jobs.mkdir(parents=True)
   for r,p in [('api',43425),('egress',43480)]:
    (jobs/('local.cn-agent-wireguard.'+r+'.plist')).write_bytes(plistlib.dumps({'ProgramArguments':['test','-allowed',str(ca/'allowed-serial'),'-listen','10.9.8.30:'+str(p)]}))
   request={'device_id':'cn-test','csr':(h/'client.csr').read_text()};source=(ROOT/'issue_client.py').read_text()
   with mock.patch.object(pathlib.Path,'home',return_value=h):
    one=jp.enroll(request,source,budget_policy={'mode':'unlimited'});two=jp.enroll(request,source,budget_policy={'mode':'unlimited'})
   self.assertEqual(one,two);self.assertNotIn('client-key.pem',one);self.assertIn('abcdef',(ca/'allowed-serial').read_text());self.assertEqual(len(json.loads((config/'caller-keys.json').read_text())),1)
   self.assertEqual((ca/'fleet-delivery/cn-test.json').stat().st_mode&0o777,0o600)
 def test_jp_changed_pin_stops_before_enrollment(self):
  with tempfile.TemporaryDirectory() as td:
   h=pathlib.Path(td);f=h/'binary';f.write_text('changed');d=h/'ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json';d.parent.mkdir(parents=True);d.write_text(json.dumps({'binary':str(f),'binarySHA256':'0'*64,'configDir':str(h)}))
   with mock.patch.object(pathlib.Path,'home',return_value=h),self.assertRaisesRegex(ValueError,'pin_changed'):jp.enroll({},'',budget_policy={'mode':'unlimited'})
 def test_fresh_desktop_entry_owned_and_executable(self):
  with tempfile.TemporaryDirectory() as td:
   content=b'#!/bin/bash\nexit 0\n';self.assertTrue(ri.install_fresh_entry(td,content,os.getuid(),os.getgid()));p=pathlib.Path(td)/'Desktop/Start-JP-Agent-Fresh.command';self.assertEqual(p.read_bytes(),content);self.assertEqual(p.stat().st_mode&0o777,0o700)
 def test_fresh_desktop_entry_preserves_existing_unknown_file(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'Desktop';p.mkdir();file=p/'Start-JP-Agent-Fresh.command';file.write_bytes(b'keep my existing file');self.assertFalse(ri.install_fresh_entry(td,b'replacement',os.getuid(),os.getgid()));self.assertEqual(file.read_bytes(),b'keep my existing file')
if __name__=='__main__':unittest.main()
