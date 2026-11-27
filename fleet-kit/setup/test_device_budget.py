"""Temporary key files and scripted native CLI, never production keys."""
import pathlib,sys,tempfile,json,unittest,copy,subprocess
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'admin'));sys.path.insert(0,str(ROOT))
import device_budget as b,issue_access
class BudgetTests(unittest.TestCase):
 def test_missing_policy_stops_before_registration(self):
  with mock.patch.object(issue_access,'enroll',side_effect=AssertionError('must not register')):
   with self.assertRaisesRegex(ValueError,'explicit_budget_required'):issue_access.issue({},'unused')
 def test_policy_rejects_zero_negative_nan_and_implicit_unlimited(self):
  for args in [(),('day',),('day',0),('day',-1),('day',True),('year',10),('day',None,float('nan')),('day',None,float('inf')),('day',None,-1)]:
   with self.subTest(args=args),self.assertRaises(ValueError):b.policy(*args)
  with self.assertRaises(ValueError):b.policy('day',100,unlimited=True)
 def test_five_hour_policy_uses_native_hours_and_preserves_other_periods(self):
  chosen=b.policy('5h',1000000,cache_reads=True)
  self.assertTrue(b.matches({'limit':{'period':'hours','hours':5,'tokens':1000000,'cacheReads':True}},chosen))
  self.assertFalse(b.matches({'limit':{'period':'hours','hours':4,'tokens':1000000,'cacheReads':True}},chosen))
  self.assertFalse(b.matches({'limit':{'period':'day','tokens':1000000,'cacheReads':True}},chosen))
 def test_explicit_unlimited(self):self.assertEqual(b.policy(unlimited=True),{'mode':'unlimited'})
 def fixture(self,p):
  config=p/'magpie';config.mkdir();keys=[{'id':'a','name':'CN A','secret':'public-fake-A','models':['group/cn-default']},{'id':'b','name':'CN B','secret':'public-fake-B','limit':{'period':'day','tokens':42}}];(config/'caller-keys.json').write_text(json.dumps(keys));return config,keys
 def test_set_and_resume_preserves_other_device_and_no_usage_reset(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);c,original=self.fixture(p);chosen=b.policy('month',1000000,cache_reads=True)
   def native(args,**kwargs):
    self.assertNotIn('reset',args);self.assertNotIn('off',args);keys=json.loads((c/'caller-keys.json').read_text());keys[0]['limit']={'period':'month','tokens':1000000,'cacheReads':True,'since':'public-timestamp'};(c/'caller-keys.json').write_text(json.dumps(keys));return subprocess.CompletedProcess(args,0,b'',b'')
   with mock.patch.object(b.subprocess,'run',side_effect=native) as r:
    b.ensure(p/'native',c,'a',chosen);b.ensure(p/'native',c,'a',chosen,recorded=chosen);self.assertEqual(r.call_count,1)
   self.assertEqual(json.loads((c/'caller-keys.json').read_text())[1],original[1])
 def test_update_failed_or_silently_ignored_is_rejected(self):
  for code in [0,1]:
   with tempfile.TemporaryDirectory() as td:
    p=pathlib.Path(td);c,_=self.fixture(p)
    with mock.patch.object(b.subprocess,'run',return_value=subprocess.CompletedProcess([],code,b'',b'')),self.assertRaisesRegex(ValueError,'budget_(update|verification)_failed'):b.ensure(p/'native',c,'a',b.policy('day',100))
 def test_existing_budget_cannot_be_changed_by_reissuing(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);c,_=self.fixture(p)
   with mock.patch.object(b.subprocess,'run') as r,self.assertRaisesRegex(ValueError,'budget_differs'):b.ensure(p/'native',c,'a',b.policy('day',200),recorded=b.policy('day',100))
   r.assert_not_called()
 def test_record_drift_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);c,_=self.fixture(p)
   with self.assertRaisesRegex(ValueError,'budget_drift'):b.ensure(p/'native',c,'a',b.policy('day',100),recorded=b.policy('day',100))
 def test_legacy_limit_cannot_be_silently_removed(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);c,_=self.fixture(p)
   with self.assertRaisesRegex(ValueError,'existing_key_limits'):b.ensure(p/'native',c,'b',b.policy(unlimited=True))
 def test_scoped_or_multiple_limits_not_misreported_as_whole_key_cap(self):
  chosen=b.policy('day',100)
  self.assertFalse(b.matches({'limit':{'period':'day','tokens':100,'models':['fake/*']}},chosen))
  self.assertFalse(b.matches({'limit':{'period':'day','tokens':100},'moreLimits':[{'period':'week','tokens':200}]},chosen))
if __name__=='__main__':unittest.main()
