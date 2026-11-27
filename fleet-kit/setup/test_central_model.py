import importlib.util,json,pathlib,tempfile,types,sys,os,contextlib,io,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import enrollment,render
s=importlib.util.spec_from_file_location('migration',ROOT/'setup/use_central_model.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CentralModelTests(unittest.TestCase):
 def test_new_install_uses_group_in_both_configs(self):
  c=dict(render.DEFAULT,operator_user='operator',operator_home='/Users/operator')
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'render';render.render(c,p);provider=json.loads((p/'providers.template.json').read_text())['providers'][0];claude=json.loads((p/'claude-settings.json').read_text())
   self.assertNotIn('preset',provider);self.assertNotIn('chat',provider);self.assertEqual(provider['responses'],'http://127.0.0.1:44337/v1');self.assertEqual(provider['models'],['group/cn-default']);self.assertEqual(claude['model'],'sonnet');self.assertTrue(all(claude['env'][k]=='remote-magpie/group/cn-default' for k in m.ALIASES));self.assertNotIn('effortLevel',claude);self.assertNotIn('CLAUDE_CODE_EFFORT_LEVEL',claude['env'])
 def _exercise_migration(self,initial_route):
  with tempfile.TemporaryDirectory() as td:
   b=pathlib.Path(td);h=b/'agent';(h/'.config/magpie').mkdir(parents=True);(h/'.claude').mkdir();(b/'private').mkdir();config=b/'private/config.json'
   c=dict(render.DEFAULT,install_base=str(b),agent_user='fixture',jp_model_id=initial_route)
   files=[h/'.config/magpie/providers.json',h/'.claude/settings.json',config,b/'private/enrollment-request.json']
   values=[{'providers':[{'id':'remote-magpie','key':'PUBLIC_TEST_KEY','models':[initial_route],'chat':'http://127.0.0.1:44337/v1'},{'id':'other','models':['unchanged']}]},{'model':'remote-magpie/'+initial_route,'effortLevel':'high','env':{'UNCHANGED':'yes','CLAUDE_CODE_EFFORT_LEVEL':'medium'},'permissions':{'allow':['Bash(printf *)']}},c,enrollment.request_for(c,'PUBLIC_CSR','a'*64,1,ROOT/'trust/jp-ca.pem')]
   for p,v in zip(files,values):p.write_text(json.dumps(v))
   (b/'private/installer-state.json').write_text('{"configured":true}')
   before=[p.read_bytes() for p in files];stat=pathlib.Path.stat
   def rootstat(p,*a,**kw):
    x=stat(p,*a,**kw)
    if p==config:t=list(x);t[4]=0;return os.stat_result(t)
    return x
   def write(p,data,*a,**kw):
    p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.encode() if isinstance(data,str) else data)
   patches=[mock.patch.object(m.os,'getuid',return_value=0),mock.patch.object(pathlib.Path,'stat',rootstat),mock.patch.object(m.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_dir=str(h),pw_uid=501,pw_gid=20)),mock.patch.object(m,'write',side_effect=write)]
   with contextlib.ExitStack() as stack:
    for patch in patches:stack.enter_context(patch)
    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
    with mock.patch.object(sys,'argv',['migration','--config',str(config)]):m.main()
    self.assertEqual([p.read_bytes() for p in files],before)
    with mock.patch.object(sys,'argv',['migration','--config',str(config),'--apply']):m.main()
    after=json.loads(files[0].read_text());self.assertEqual(after['providers'][0]['key'],'PUBLIC_TEST_KEY');self.assertEqual(after['providers'][1],values[0]['providers'][1]);self.assertEqual(json.loads(files[1].read_text())['permissions'],values[1]['permissions']);self.assertEqual(json.loads(config.read_text())['jp_model_id'],'group/cn-default');new_settings=json.loads(files[1].read_text());self.assertEqual(new_settings['model'],'sonnet');self.assertTrue(all(new_settings['env'][k]=='remote-magpie/group/cn-default' for k in m.ALIASES));self.assertEqual(new_settings['effortLevel'],'high');self.assertEqual(new_settings['env']['CLAUDE_CODE_EFFORT_LEVEL'],'medium')
    if initial_route=='group/cn-default':self.assertEqual(files[3].read_bytes(),before[3])
    backup=next((b/'private/central-model-backups').iterdir())
    with mock.patch.object(sys,'argv',['migration','--config',str(config),'--rollback',str(backup)]):m.main()
    self.assertEqual([p.read_bytes() for p in files],before)
 def test_migration_preserves_key_other_settings_and_rolls_back_exactly(self):self._exercise_migration('codex/gpt-6.1-sol')
 def test_same_group_alias_update_preserves_signed_request_and_effort(self):self._exercise_migration('group/cn-default')
if __name__=='__main__':unittest.main()
