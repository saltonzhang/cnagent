import importlib.util,pathlib,tempfile,os,json,unittest,sys
from unittest import mock
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'setup'))
import set_agent_defaults as m
class AgentDefaultsTests(unittest.TestCase):
 def fixture(self,td):
  b=pathlib.Path(td)/'install';p=b/'private';p.mkdir(parents=True);h=pathlib.Path(td)/'agent';(h/'.claude').mkdir(parents=True);(h/'.config/magpie').mkdir(parents=True)
  c={'install_base':str(b),'agent_home':str(h),'device_id':'cn-fixture','agent_user':'fixture','api_adapter_port':44337,'jp_model_id':'group/cn-default'};state={'schema':3,'configured':True,'accepted_bundle_sha256':'public-test','device_id':'cn-fixture','accounts':{'fixture':{'complete':True,'uid':os.getuid(),'home':str(h)}}}
  for n,x in [('config.json',c),('installer-state.json',state)]:f=p/n;f.write_text(json.dumps(x));f.chmod(0o600)
  (b/'launch').write_text('#!/bin/bash\nexec /usr/bin/sudo -u fixture /usr/bin/env -i HOME='+str(h)+' USER=fixture LOGNAME=fixture /usr/bin/sandbox-exec -f "$base/controlled.sb" /bin/zsh\n')
  (h/'.config/magpie/providers.json').write_text(json.dumps({'providers':[{'id':'remote-magpie','models':['group/cn-default'],'responses':'http://127.0.0.1:44337/v1','key':'public-not-real'}]}))
  f=h/'.claude/settings.json';f.write_text(json.dumps({'model':'remote-magpie/group/cn-default','env':{'ANTHROPIC_AUTH_TOKEN':'public-local','CLAUDE_CODE_EFFORT_LEVEL':'high'},'effortLevel':'medium','permissions':{'deny':['Bash(example-denied *)']}}));f.chmod(0o600)
  (p/'enrollment-request.json').write_text('public signed-request sentinel');return b,p/'config.json',h,f,SimpleNamespace(pw_uid=os.getuid(),pw_dir=str(h))
 def test_preview_apply_idempotence_and_exact_rollback(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,h,f,a=self.fixture(td);raw=f.read_bytes();protected={p:p.read_bytes() for p in [c,b/'launch',b/'private/enrollment-request.json',h/'.config/magpie/providers.json']}
   with mock.patch.object(m.pwd,'getpwnam',return_value=a):
    self.assertTrue(m.migrate(c,owner=os.getuid())['changeNeeded']);self.assertEqual(f.read_bytes(),raw)
    r=m.migrate(c,True,owner=os.getuid());new=json.loads(f.read_text());self.assertEqual(new['model'],'sonnet');self.assertTrue(all(new['env'][k]=='remote-magpie/group/cn-default' for k in m.ALIASES));self.assertEqual(new['env']['CLAUDE_CODE_EFFORT_LEVEL'],'high');self.assertEqual(new['effortLevel'],'medium');self.assertEqual(new['permissions'],json.loads(raw)['permissions']);self.assertEqual(new['env']['ANTHROPIC_AUTH_TOKEN'],'public-local')
    self.assertFalse(m.migrate(c,True,owner=os.getuid())['changeNeeded']);m.migrate(c,True,r['backup'],owner=os.getuid());self.assertEqual(f.read_bytes(),raw)
   for p,v in protected.items():self.assertEqual(p.read_bytes(),v)
 def test_rollback_preserves_later_effort_change(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,h,f,a=self.fixture(td)
   with mock.patch.object(m.pwd,'getpwnam',return_value=a):
    r=m.migrate(c,True,owner=os.getuid());d=json.loads(f.read_text());d['effortLevel']='high';f.write_text(json.dumps(d))
    with self.assertRaisesRegex(ValueError,'rollback_conflict'):m.migrate(c,True,r['backup'],owner=os.getuid())
 def test_non_group_route_is_not_silently_migrated(self):
  with tempfile.TemporaryDirectory() as td:
   b,c,h,f,a=self.fixture(td);d=json.loads(c.read_text());d['jp_model_id']='codex/public';c.write_text(json.dumps(d));raw=f.read_bytes()
   with mock.patch.object(m.pwd,'getpwnam',return_value=a),self.assertRaisesRegex(ValueError,'migration_required'):m.migrate(c,True,owner=os.getuid())
   self.assertEqual(f.read_bytes(),raw)
if __name__=='__main__':unittest.main()
