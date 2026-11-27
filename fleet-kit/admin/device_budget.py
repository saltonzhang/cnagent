"""Administrator-selected, server-side per-device budget. No secrets in output."""
import math,os,subprocess

def policy(period=None,tokens=None,cost=None,cache_reads=False,unlimited=False):
 if unlimited:
  if period is not None or tokens is not None or cost is not None or cache_reads:raise ValueError('unlimited_conflicts_with_budget')
  return {'mode':'unlimited'}
 if period not in ['day','week','month','5h']:raise ValueError('explicit_budget_required_choose_period_or_unlimited')
 if tokens is not None and (type(tokens) is not int or not 0<tokens<=9007199254740991):raise ValueError('tokens_must_be_positive_integer')
 if cost is not None and (type(cost) not in [int,float] or not math.isfinite(cost) or cost<=0):raise ValueError('cost_must_be_positive_finite_USD')
 if type(cache_reads) is not bool:raise ValueError('invalid_cache_reads')
 if tokens is None and cost is None:raise ValueError('tokens_or_cost_required')
 return {'mode':'limited','period':period,'tokens':tokens or 0,'cost':float(cost or 0),'cache_reads':cache_reads}

def validate(p):
 if not isinstance(p,dict):raise ValueError('explicit_budget_required')
 if p=={'mode':'unlimited'}:return policy(unlimited=True)
 if set(p)!={'mode','period','tokens','cost','cache_reads'} or p['mode']!='limited':raise ValueError('invalid_budget_policy')
 return policy(p['period'],p['tokens'] or None,p['cost'] or None,p['cache_reads'])

def matches(key,p):
 limits=([key['limit']] if key.get('limit') else [])+key.get('moreLimits',[])
 if p['mode']=='unlimited':return not limits
 if len(limits)!=1:return False
 l=limits[0]
 return (l.get('period')==p['period'] or (p['period']=='5h' and l.get('period')=='hours' and l.get('hours')==5)) and l.get('tokens',0)==p['tokens'] and l.get('cost',0)==p['cost'] and bool(l.get('cacheReads',False))==p['cache_reads'] and not l.get('models') and not l.get('days') and (not l.get('hours') or p['period']=='5h')

def read_key(config,keyid):
 import json
 keys=json.loads((config/'caller-keys.json').read_text());rows=[x for x in keys if x.get('id')==keyid]
 if len(rows)!=1 or rows[0].get('off'):raise ValueError('budget_key_missing_or_disabled')
 return keys,rows[0]

def ensure(binary,config,keyid,p,recorded=None):
 p=validate(p);before,key=read_key(config,keyid)
 if recorded is not None:
  if validate(recorded)!=p:raise ValueError('existing_device_budget_differs_use_admin_limit_management')
  if not matches(key,p):raise ValueError('device_budget_drift_review_required')
  return p
 if matches(key,p):return p
 # Never remove/replace existing limits when adopting an older delivery record.
 if key.get('limit') or key.get('moreLimits'):raise ValueError('existing_key_limits_review_required')
 if p['mode']=='unlimited':raise ValueError('unexpected_existing_budget')
 args=[str(binary),'gateway-key','limit',keyid,p['period']]
 if p['tokens']:args+=['--tokens',str(p['tokens'])]
 if p['cost']:args+=['--cost',str(p['cost'])]
 if p['cache_reads']:args+=['--cache-reads']
 r=subprocess.run(args,env=dict(os.environ,XDG_CONFIG_HOME=str(config.parent)),capture_output=True,timeout=30)
 if r.returncode:raise ValueError('gateway_budget_update_failed_no_bundle_delivered')
 after,updated=read_key(config,keyid)
 if not matches(updated,p):raise ValueError('gateway_budget_verification_failed_no_bundle_delivered')
 if [x for x in before if x.get('id')!=keyid]!=[x for x in after if x.get('id')!=keyid]:raise ValueError('unrelated_key_changed_review_required')
 # Native CLI may add timestamps; all other properties of this device must persist.
 if {k:v for k,v in key.items() if k not in ['limit','moreLimits']}!={k:v for k,v in updated.items() if k not in ['limit','moreLimits']}:raise ValueError('unrelated_device_key_property_changed')
 return p
