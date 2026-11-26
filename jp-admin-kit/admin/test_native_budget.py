"""Run on JP with --binary existing core. Temporary HOME, keys and HTTP upstream only."""
import argparse,pathlib,tempfile,subprocess,os,json,http.server,threading,time,urllib.request,urllib.error,socket,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent));import device_budget,manage_budget
p=argparse.ArgumentParser();p.add_argument('--binary',required=True);a=p.parse_args();calls=[]
class API(http.server.BaseHTTPRequestHandler):
 def log_message(self,*_):pass
 def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[{"id":"m1"}]}')
 def do_POST(self):
  calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))));raw=json.dumps({'id':'resp_public','object':'response','status':'completed','model':'m1','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'OK'}]}],'usage':{'input_tokens':20,'output_tokens':1500,'total_tokens':1520}}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),API);threading.Thread(target=server.serve_forever,daemon=True).start();op=urllib.request.build_opener(urllib.request.ProxyHandler({}));proc=None
try:
 with tempfile.TemporaryDirectory(prefix='cn-budget-native-') as td:
  h=pathlib.Path(td);config=h/'config/magpie';config.mkdir(parents=True);s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
  env=dict(os.environ,HOME=td,XDG_CONFIG_HOME=str(config.parent),XDG_CACHE_HOME=str(h/'cache'),XDG_STATE_HOME=str(h/'state'),XDG_DATA_HOME=str(h/'data'),MAGPIE_ADDR='127.0.0.1:'+str(port),MAGPIE_NO_ACCOUNTS='1',MAGPIE_PLUGIN_MARKET='off',MAGPIE_TRANSLATOR_POLICY='',MAGPIE_OUTPUT_TRANSLATION_POLICY='',MAGPIE_OUTBOUND_AUDIT_ADDR='',HTTP_PROXY='',HTTPS_PROXY='',ALL_PROXY='',NO_PROXY='*')
  def cli(*args):
   r=subprocess.run([a.binary]+list(args),env=env,capture_output=True,timeout=30)
   if r.returncode:raise RuntimeError('isolated_native_cli_failed')
   return r.stdout
  cli('provider','add','Public mock','id=fake','responses=http://127.0.0.1:'+str(server.server_port)+'/v1','key=synthetic','models=m1','catalog=off')
  ka=cli('gateway-key','add','public-CN-A').decode().strip();kb=cli('gateway-key','add','public-CN-B').decode().strip()
  keys=json.loads((config/'caller-keys.json').read_text());ida=next(x['id'] for x in keys if x['name']=='public-CN-A');idb=next(x['id'] for x in keys if x['name']=='public-CN-B')
  old=dict(os.environ);os.environ.update(env)
  try:
   pa=device_budget.policy('day',1000);pb=device_budget.policy('month',10000)
   device_budget.ensure(pathlib.Path(a.binary),config,ida,pa);device_budget.ensure(pathlib.Path(a.binary),config,idb,pb)
  finally:os.environ.clear();os.environ.update(old)
  def start():
   global proc
   proc=subprocess.Popen([a.binary,'serve'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   for _ in range(150):
    try:op.open('http://127.0.0.1:'+str(port)+'/',timeout=.3).close();return
    except Exception:time.sleep(.1)
   raise RuntimeError('isolated_server_not_ready')
  def stop():
   global proc
   if proc is not None:proc.terminate();proc.wait(timeout=10);proc=None
  def ask(key):
   req=urllib.request.Request('http://127.0.0.1:'+str(port)+'/v1/responses',data=json.dumps({'model':'fake/m1','input':'Reply OK.'}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
   try:
    with op.open(req,timeout=20) as r:r.read();return r.status
   except urllib.error.HTTPError as e:e.read();return e.code
  start();assert ask(ka)==200;time.sleep(.3);before=len(calls);assert ask(ka)==429;assert len(calls)==before;assert ask(kb)==200
  stop();start();assert ask(ka)==429;assert ask(kb)==200;stop()
  # Simulate prior calendar window in the isolated ledger; no production clock/files touched.
  ledgers=list(h.rglob('usage.jsonl'));assert len(ledgers)==1
  rows=[json.loads(x) for x in ledgers[0].read_text().splitlines() if x.strip()]
  assert any(x.get('callerKeyId')==ida for x in rows) and any(x.get('callerKeyId')==idb for x in rows)
  for r in rows:
   if r.get('callerKeyId')==ida:r['t']='2020-01-01T00:00:00Z'
  ledgers[0].write_text(''.join(json.dumps(r)+'\n' for r in rows));start();assert ask(ka)==200;stop()
  records=h/'delivery';records.mkdir();(records/'cn-a.json').write_text(json.dumps({'gateway_key_id':ida,'budget':pa,'gateway_key':'not-a-real-key'}))
  revised=device_budget.policy('month',20000)
  preview=manage_budget.update(pathlib.Path(a.binary),config,records,'cn-a',revised,False);assert not preview.get('changed');assert device_budget.matches(device_budget.read_key(config,ida)[1],pa)
  changed=manage_budget.update(pathlib.Path(a.binary),config,records,'cn-a',revised,True);assert changed['changed'];assert device_budget.matches(device_budget.read_key(config,idb)[1],pb);assert json.loads((records/'cn-a.json').read_text())['budget']==revised
  print(json.dumps({'passed':True,'isolated':True,'nativeCore':True,'upstream':'synthetic HTTP','productionChanged':False,'cases':['native_limit_written_and_verified','per_device_usage_attributed','over_limit_429_before_upstream','other_device_unaffected','restart_preserves_limit','previous_day_usage_does_not_spend_today','admin_preview_read_only','admin_change_one_device_and_registry_only'],'knownLimit':'inflight usage may overshoot; cost is estimate'}))
finally:
 if proc is not None:proc.terminate();proc.wait(timeout=10)
 server.shutdown();server.server_close()
