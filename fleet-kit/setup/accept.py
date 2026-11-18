#!/usr/bin/env python3
"""On-host real acceptance. Emits only fixed status fields, never private model output."""
import argparse,hashlib,json,os,re,pathlib,pwd,subprocess,time,urllib.request,urllib.error

def execute(args,timeout=30):
 try:
  r=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=timeout);return r.returncode,r.stdout
 except subprocess.TimeoutExpired:return 124,''
def blocked_packets(text,port):
 total=0;found=False
 for block in re.split(r'(?m)^@\d+ ',text):
  line=block.splitlines()[0] if block else ''
  if line.startswith('block return out quick on lo0 ') and re.search(r'port = '+str(port)+r'(?:\s|$)',line) and 'user =' not in line:
   m=re.search(r'Packets:\s*(\d+)',block)
   if m:total+=int(m.group(1));found=True
 return total if found else None
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--no-public-check',action='store_true');a=p.parse_args()
 if os.getuid()!=0:raise ValueError('root_required')
 c=json.loads(pathlib.Path(a.config).read_text());b=pathlib.Path(c['install_base']);checks={}
 for _ in range(60):
  if (b/'private/expected-pf.txt').exists():break
  time.sleep(.5)
 code,info=execute(['/sbin/pfctl','-s','info']);checks['pfEnabled']=code==0 and 'Status: Enabled' in info
 code,rules=execute(['/sbin/pfctl','-a',c['pf_anchor'],'-sr']);checks['pfRulesMatch']=code==0 and rules==(b/'private/expected-pf.txt').read_text()
 for who in [c['operator_user'],c['agent_user']]:
  code,out=execute(['/usr/bin/sudo','-u',who,'/bin/cat',c['network_home']+'/client-key.pem']);checks[('ordinary' if who==c['operator_user'] else 'agent')+'CannotReadKey']=code!=0
 for port in [c['cn_api_port'],c['api_adapter_port'],c['web_proxy_port']]:
  # A refused/timeout socket alone is not proof: require per-port PF block counters AND a positive Agent-UID connection.
  script='import socket,json;s=socket.socket();s.settimeout(3)\ntry:s.connect(("127.0.0.1",'+str(port)+'));print("allowed")\nexcept OSError as e:print(e.errno)'
  _,before=execute(['/sbin/pfctl','-a',c['pf_anchor'],'-vvsr']);count_before=blocked_packets(before,port)
  code,out=execute(['/usr/bin/sudo','-u',c['operator_user'],c['python_binary'],'-c',script]);denied=code==0 and out.strip()!='allowed'
  _,after=execute(['/sbin/pfctl','-a',c['pf_anchor'],'-vvsr']);count_after=blocked_packets(after,port)
  allowed_code,allowed_out=execute(['/usr/bin/sudo','-u',c['agent_user'],c['python_binary'],'-c',script])
  checks['ordinaryPort'+str(port)+'Blocked']=denied and count_before is not None and count_after is not None and count_after>count_before and allowed_code==0 and allowed_out.strip()=='allowed'
 probe=[str(b/'launch'),'shell','-f','-c',c['python_binary']+' "'+str(b/'probe.py')+'"'+('' if a.no_public_check else ' --public-check')]
 code,out=execute(probe,45)
 try:
  data=json.loads(out);checks['controlledNegatives']=code==0 and all(data.get(k) is True for k in ['oldJPBlocked','otherLocalProxyBlocked','ipv6LoopbackBlocked','udpLoopbackBlocked','dnsIPCBlocked'])
  checks['JPProxy']=not a.no_public_check and data.get('proxySucceeded') is True and data.get('country')=='JP'
  proxy_digest=data.get('ipSHA256')
 except Exception:checks['controlledNegatives']=False;checks['JPProxy']=False;proxy_digest=None
 code,out=execute([b/'launch','claude','-p','Reply only OK. Do not use tools.','--output-format','json'],120)
 try:d=json.loads(out);checks['realClaudeReply']=code==0 and d.get('result','').strip()=='OK' and not d.get('is_error')
 except Exception:checks['realClaudeReply']=False
 # A public fixed Bash tool task verifies actual tool invocation, not model-only success.
 code,out=execute([b/'launch','claude','-p','Use the Bash tool to execute exactly: printf CN_AGENT_TOOL_OK. Then reply only DONE.','--allowedTools','Bash','--output-format','stream-json','--verbose'],120)
 try:
  events=[json.loads(line) for line in out.splitlines() if line.strip()];done=next((x for x in reversed(events) if x.get('type')=='result'),{});blocks=[v for x in events for v in x.get('message',{}).get('content',[]) if isinstance(v,dict)];checks['realToolTaskCompleted']=code==0 and not done.get('is_error') and done.get('result','').strip()=='DONE' and any(x.get('type')=='tool_use' and x.get('name')=='Bash' for x in blocks) and any(x.get('type')=='tool_result' and 'CN_AGENT_TOOL_OK' in json.dumps(x.get('content')) for x in blocks)
 except Exception:checks['realToolTaskCompleted']=False
 # Require both an actual Bash tool_use event and the exact public tool-result marker.
 code,status=execute(['/usr/bin/curl','--noproxy','*','-s','-o','/dev/null','-w','%{http_code}','--max-time','8','http://'+c['jp_host']+':3425/v1/models'])
 checks['oldJPDenied']=code==0 and status=='403'
 result={'passed':all(checks.values()),'checks':checks,'JPProxyIPDigest':proxy_digest,'interactiveAcceptanceRequired':True,'toolEventChecked':checks.get('realToolTaskCompleted',False)}
 report=b/'private/acceptance.json';report.write_text(json.dumps(result,indent=2));report.chmod(0o600);print(json.dumps(result))
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'passed':False,'error':type(e).__name__}));raise SystemExit(1)
