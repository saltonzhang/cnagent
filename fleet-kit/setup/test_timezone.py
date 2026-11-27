import pathlib,tempfile,unittest,importlib.util,os,json,pwd,shutil
from unittest import mock
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('timezone_update',ROOT/'setup/set_agent_timezone.py');tz=importlib.util.module_from_spec(spec);spec.loader.exec_module(tz)
class TimezoneTests(unittest.TestCase):
 def fixture(self,td):
  b=pathlib.Path(td)/'install';p=b/'private';p.mkdir(parents=True);h=pathlib.Path(td)/'agent';h.mkdir();c={'install_base':str(b),'device_id':'cn-public-test','agent_user':'public-test','agent_home':str(h)};state={'schema':3,'configured':True,'accepted_bundle_sha256':'public-test-hash','device_id':c['device_id'],'accounts':{'public-test':{'uid':os.getuid(),'home':str(h),'complete':True}}}
  for n,d in [('config.json',c),('installer-state.json',state)]:f=p/n;f.write_text(json.dumps(d));f.chmod(0o600)
  text='#!/bin/bash\nexec /usr/bin/sudo -u public-test /usr/bin/env -i HOME='+str(h)+' USER=public-test LOGNAME=public-test \\\n HTTP_PROXY=http://127.0.0.1:18190 \\\n /usr/bin/sandbox-exec -f "$base/controlled.sb" /bin/zsh "$@"\n';(b/'launch').write_text(text);(b/'launch').chmod(0o755)
  for n in ['certificate.pem','caller-key.json','providers.json','policy.json']:(p/n).write_text('public sentinel '+n)
  return b,p/'config.json',SimpleNamespace(pw_uid=os.getuid(),pw_dir=str(h))
 def test_preview_writes_nothing(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td);before={str(p):p.read_bytes() for p in b.rglob('*') if p.is_file()}
   with mock.patch.object(tz.pwd,'getpwnam',return_value=a):r=tz.migrate(c,owner=os.getuid())
   self.assertTrue(r['changeNeeded']);self.assertFalse((b/'private/timezone-backups').exists());self.assertEqual(before,{str(p):p.read_bytes() for p in b.rglob('*') if p.is_file()})
 def test_apply_idempotent_and_rollback_preserve_other_files(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td);before={str(p):p.read_bytes() for p in b.rglob('*') if p.is_file()};raw=(b/'launch').read_bytes()
   with mock.patch.object(tz.pwd,'getpwnam',return_value=a):
    r=tz.migrate(c,True,owner=os.getuid());self.assertTrue(r['changed']);current=(b/'launch').read_bytes();self.assertIn(b'TZ=Asia/Tokyo HOME=',current);self.assertIn(tz.RULE.encode(),current);self.assertIn(b'-p "$agent_profile"',current);restored=current.decode().replace(tz.BLOCK+'\n','').replace('-p "$agent_profile"','-f "$base/controlled.sb"').replace('/usr/bin/env -i TZ=Asia/Tokyo HOME=','/usr/bin/env -i HOME=');self.assertEqual(restored.encode(),raw);self.assertEqual((b/'launch').stat().st_mode&0o777,0o755)
    count=len(list((b/'private/timezone-backups').iterdir()));second=tz.migrate(c,True,owner=os.getuid());self.assertFalse(second['changeNeeded']);self.assertEqual(len(list((b/'private/timezone-backups').iterdir())),count)
    preview=tz.migrate(c,False,r['backup'],owner=os.getuid());self.assertTrue(preview['rollbackPreview']);self.assertIn(b'TZ=Asia/Tokyo',(b/'launch').read_bytes());tz.migrate(c,True,r['backup'],owner=os.getuid());self.assertEqual((b/'launch').read_bytes(),raw)
   for p,data in before.items():self.assertEqual(pathlib.Path(p).read_bytes(),data)
 def test_rollback_refuses_concurrent_launcher_edits(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td)
   with mock.patch.object(tz.pwd,'getpwnam',return_value=a):
    r=tz.migrate(c,True,owner=os.getuid());(b/'launch').write_text((b/'launch').read_text()+'# subsequent edit\n')
    with self.assertRaisesRegex(ValueError,'rollback_conflict'):tz.migrate(c,True,r['backup'],owner=os.getuid())
 def test_legacy_pilot_is_not_adopted(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td);(b/'private/installer-state.json').unlink();before=(b/'launch').read_bytes()
   with self.assertRaises(ValueError):tz.migrate(c,True,owner=os.getuid())
   self.assertEqual((b/'launch').read_bytes(),before);self.assertFalse((b/'private/timezone-backups').exists())
 def test_identity_drift_refused(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td);a.pw_uid+=1
   with mock.patch.object(tz.pwd,'getpwnam',return_value=a),self.assertRaisesRegex(ValueError,'identity_changed'):tz.migrate(c,True,owner=os.getuid())
 def test_symlink_launcher_and_world_writable_config_refused(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td);target=b/'saved';(b/'launch').rename(target);(b/'launch').symlink_to(target)
   with mock.patch.object(tz.pwd,'getpwnam',return_value=a),self.assertRaises(ValueError):tz.migrate(c,True,owner=os.getuid())
   c.chmod(0o666)
   with self.assertRaises(ValueError):tz.migrate(c,True,owner=os.getuid())
 def test_custom_or_ambiguous_environment_refused(self):
  for text in ['exec env HOME=/example','/usr/bin/env -i HOME=/other USER=a LOGNAME=a','/usr/bin/env -i HOME=/a USER=a LOGNAME=a\n/usr/bin/env -i HOME=/a USER=a LOGNAME=a','/usr/bin/env -i HOME=/a USER=a LOGNAME=a TZ=Asia/Shanghai']:
   with self.assertRaises(ValueError):tz.transform(text.encode(),'/a','a')
 def test_new_template_defaults_to_JST_without_system_or_locale_change(self):
  s=(ROOT/'templates/launch.tmpl').read_text();self.assertIn('/usr/bin/env -i TZ=Asia/Tokyo HOME=',s);self.assertIn('LANG="$terminal_locale"',s);self.assertNotIn('systemsetup',s)
 def test_existing_JST_only_launcher_gets_file_guard(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td);raw=(b/'launch').read_bytes().replace(b'/usr/bin/env -i HOME=',b'/usr/bin/env -i TZ=Asia/Tokyo HOME=');(b/'launch').write_bytes(raw)
   with mock.patch.object(tz.pwd,'getpwnam',return_value=a):r=tz.migrate(c,True,owner=os.getuid())
   self.assertTrue(r['changed']);self.assertIn(tz.RULE.encode(),(b/'launch').read_bytes());self.assertEqual((b/'launch').read_bytes().count(b'TZ=Asia/Tokyo'),1)
 def test_guard_uses_current_network_profile_without_modifying_service_profile(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,a=self.fixture(td);profile=b/'controlled.sb';profile.write_text('(version 1)\n(allow default)\n(deny network*)\n');before=profile.read_bytes()
   with mock.patch.object(tz.pwd,'getpwnam',return_value=a):tz.migrate(c,True,owner=os.getuid())
   self.assertEqual(profile.read_bytes(),before);self.assertIn(b'/bin/cat "$base/controlled.sb"',(b/'launch').read_bytes());self.assertIn(b'-p "$agent_profile"',(b/'launch').read_bytes())
if __name__=='__main__':unittest.main()
