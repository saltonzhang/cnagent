import pathlib,pwd,os,tempfile,json,unittest
from unittest import mock
import install_repo_sharing as m
class HelperInstallTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.base=pathlib.Path(self.t.name)/'base';self.base.mkdir();(self.base/'private').mkdir();(self.base/'launch').write_text('public launcher');self.c={'install_base':str(self.base),'operator_user':'publichost','agent_user':'publicagent','python_binary':'/usr/bin/python3'}
  users={'publichost':type('User',(),{'pw_uid':501,'pw_name':'publichost','pw_dir':'/Users/publichost'})(),'publicagent':type('User',(),{'pw_uid':502,'pw_name':'publicagent','pw_dir':'/Users/publicagent'})()};patch=mock.patch.object(m.pwd,'getpwnam',side_effect=lambda n:users[n]);patch.start();self.addCleanup(patch.stop)
 def test_plan_does_not_install_or_change_repo(self):
  with mock.patch.object(m,'trusted'):result=m.install(self.c)
  self.assertFalse(result['projectPermissionsChanged']);self.assertFalse((self.base/'share-repo').exists())
 def test_install_resumes_with_identity_context_no_service_calls(self):
  with mock.patch.object(m,'trusted'):
   m.install(self.c,True);before=(self.base/'share-repo').read_bytes();result=m.install(self.c,True)
  self.assertEqual(result['changedFiles'],[]);self.assertEqual(before,(self.base/'share-repo').read_bytes());ctx=json.loads((self.base/'repo-sharing.json').read_text());self.assertEqual(ctx['operator_user'],'publichost');self.assertNotIn('key',ctx);self.assertFalse(result['servicesRestarted'])
 def test_customized_helper_not_overwritten(self):
  with mock.patch.object(m,'trusted'):
   m.install(self.c,True);(self.base/'share-repo').write_text('user modification')
   with self.assertRaisesRegex(ValueError,'customized'):m.install(self.c,True)
  self.assertEqual((self.base/'share-repo').read_text(),'user modification')
if __name__=='__main__':unittest.main()
