import importlib.util,os,pathlib,pwd,subprocess,tempfile,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('repo_share',ROOT/'repo-sharing/share_git_repo.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class RepoSharingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name).resolve();self.home=self.root/'home';self.home.mkdir();self.repo=self.root/'repo';self.repo.mkdir();self.addCleanup(mock.patch.stopall);mock.patch.object(m.Path,'home',return_value=self.home).start();m.JOURNAL=None
  self.git('init','-q');(self.repo/'README').write_text('public');(self.repo/'.gitignore').write_text('.env\n');(self.repo/'.env').write_text('private fixture');(self.repo/'.env').chmod(0o600);self.git('add','README','.gitignore')
 def git(self,*args):return subprocess.run(['/usr/bin/git','-C',str(self.repo),*args],capture_output=True,check=True)
 def test_inventory_only_tracked_excludes_secrets_untracked(self):
  (self.repo/'untracked').write_text('not shared');root,admin,common=m.layout(self.repo);g=m.inventory(root,admin,common);self.assertIn(self.repo/'README',g['files']);self.assertNotIn(self.repo/'.env',g['files']);self.assertNotIn(self.repo/'untracked',g['files'])
 def test_public_readable_secret_blocks_sharing(self):
  (self.repo/'.env').chmod(0o644)
  with self.assertRaisesRegex(m.Stop,'敏感'):m.inventory(*m.layout(self.repo))
 def test_tracked_env_still_excluded(self):
  self.git('add','-f','.env');g=m.inventory(*m.layout(self.repo));self.assertNotIn(self.repo/'.env',g['files'])
 def test_symlink_target_is_not_enumerated_or_granted(self):
  outside=self.root/'outside';outside.write_text('private fixture');(self.repo/'link').symlink_to(outside);self.git('add','link');g=m.inventory(*m.layout(self.repo));self.assertIn(self.repo/'link',g['links']);self.assertNotIn(outside,g['files'])
 def test_external_alternates_refused(self):
  p=self.repo/'.git/objects/info/alternates';p.write_text('/outside/objects\n')
  with self.assertRaisesRegex(m.Stop,'alternates'):m.layout(self.repo)
 def test_hardlink_does_not_mutate_other_path(self):
  os.link(self.repo/'README',self.root/'hardlink')
  with self.assertRaisesRegex(m.Stop,'硬链接'):m.inventory(*m.layout(self.repo))
 def test_remote_rewrites_do_not_accept_credential_urls(self):
  self.assertEqual(m.destination('git@github.com:org/repo.git'),'https://github.com/org/repo.git')
  for url in ['https://user:secret@github.com/org/repo','https://github.com/org/repo?token=x']:
   with self.assertRaises(m.Stop):m.validate_https(url)
 def test_journal_acl_idempotence_and_restore(self):
  p=self.repo/'README';before=m.acl_entries(p);j=m.Journal('public-op',{});m.JOURNAL=j;principal='user:'+pwd.getpwuid(os.getuid()).pw_name
  m.add_acl([p],principal,'read,readattr');first=m.acl_entries(p);m.add_acl([p],principal,'readattr,read');self.assertEqual(first,m.acl_entries(p));m.Journal.open('public-op').rollback();self.assertEqual(before,m.acl_entries(p))
 def test_rollback_preserves_existing_acl(self):
  p=self.repo/'README';principal='user:'+pwd.getpwuid(os.getuid()).pw_name;m.add_acl([p],principal,'read');before=m.acl_entries(p);j=m.Journal('public-old',{});m.JOURNAL=j;m.add_acl([p],principal,'write');m.Journal.open('public-old').rollback();self.assertEqual(before,m.acl_entries(p))
 def test_changed_file_inode_refuses_rollback(self):
  p=self.repo/'README';j=m.Journal('public-changed',{});m.JOURNAL=j;m.add_acl([p],'user:'+pwd.getpwuid(os.getuid()).pw_name,'read');new=self.repo/'new';new.write_text('public replacement');new.replace(p)
  with self.assertRaisesRegex(m.Stop,'变化'):m.Journal.open('public-changed').rollback()
 def test_git_config_backup_is_private_and_guarded(self):
  p=self.home/'.gitconfig';p.write_text('[user]\nname = public-before\n');j=m.Journal('public-config',{});j.config(p);p.write_text('[user]\nname = public-after\n');j.finish_configs();self.assertEqual(j.path.stat().st_mode&0o777,0o600);m.Journal.open('public-config').rollback();self.assertIn('before',p.read_text())
if __name__=='__main__':unittest.main()
