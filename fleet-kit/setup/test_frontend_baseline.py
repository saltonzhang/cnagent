"""Standalone opt-in runtime test; temporary HOME and synthetic loopback upstream only."""
import argparse,os,pathlib,tempfile,json,subprocess,http.server,threading,urllib.request,urllib.error,socket,time,copy

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--binary',required=True);parser.add_argument('--out');a=parser.parse_args();seen=[];server=None;proc=None;op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 class API(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[{"id":"group/cn-default"}]}')
  def do_POST(self):
   b=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append(b);message={'id':'msg_public','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':'OK','annotations':[]}]};reply={'id':'resp_public','object':'response','status':'completed','model':'group/cn-default','output':[message],'usage':{'input_tokens':20,'output_tokens':2,'total_tokens':22}}
   if b.get('stream'):
    events=[{'type':'response.created','response':dict(reply,status='in_progress',output=[])},{'type':'response.output_item.added','output_index':0,'item':dict(message,status='in_progress',content=[])},{'type':'response.content_part.added','item_id':'msg_public','output_index':0,'content_index':0,'part':{'type':'output_text','text':'','annotations':[]}},{'type':'response.output_text.delta','item_id':'msg_public','output_index':0,'content_index':0,'delta':'OK'},{'type':'response.output_text.done','item_id':'msg_public','output_index':0,'content_index':0,'text':'OK'},{'type':'response.output_item.done','output_index':0,'item':message},{'type':'response.completed','response':reply}];raw=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode();kind='text/event-stream'
   else:raw=json.dumps(reply).encode();kind='application/json'
   self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 try:
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),API);threading.Thread(target=server.serve_forever,daemon=True).start()
  with tempfile.TemporaryDirectory(prefix='cn4777-runtime-') as td:
   h=pathlib.Path(td);config=h/'config/magpie';config.mkdir(parents=True);s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
   (config/'providers.json').write_text(json.dumps({'providers':[{'id':'remote-magpie','name':'Public JP mock','responses':'http://127.0.0.1:'+str(server.server_port)+'/v1','key':'public-synthetic','models':['group/cn-default'],'catalog':'off','proxy':'direct'}]}));(config/'plugins.json').write_text('{"plugins":[]}');(config/'settings.json').write_text('{"allowIPs":["127.0.0.1/32"],"proxy":"direct"}')
   env=dict(os.environ,HOME=td,XDG_CONFIG_HOME=str(config.parent),XDG_CACHE_HOME=str(h/'cache'),XDG_DATA_HOME=str(h/'data'),XDG_STATE_HOME=str(h/'state'),MAGPIE_ADDR='127.0.0.1:'+str(port),MAGPIE_NO_ACCOUNTS='1',MAGPIE_PLUGIN_MARKET='off',MAGPIE_TRANSLATOR_POLICY='',MAGPIE_OUTPUT_TRANSLATION_POLICY='',MAGPIE_OUTBOUND_AUDIT_ADDR='',HTTP_PROXY='',HTTPS_PROXY='',ALL_PROXY='',NO_PROXY='*')
   proc=subprocess.Popen([a.binary,'serve'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   for _ in range(150):
    try:op.open('http://127.0.0.1:'+str(port)+'/v1/models',timeout=.3).close();break
    except Exception:time.sleep(.1)
   else:raise RuntimeError('isolated_frontend_not_ready')
   def ask(body):
    with op.open(urllib.request.Request('http://127.0.0.1:'+str(port)+'/v1/messages',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=25) as r:return r.status,r.read()
   body={'model':'remote-magpie/group/cn-default','max_tokens':128,'messages':[{'role':'user','content':'PUBLIC_FIXTURE. Reply OK.'}]};checks=[]
   status,raw=ask(body);assert status==200 and 'OK' in raw.decode();assert seen[-1]['model']=='group/cn-default';checks.append('public_message_responses_group_route')
   tools=copy.deepcopy(body);tools['tools']=[{'name':'Read','description':'Public mock only','input_schema':{'type':'object','properties':{'path':{'type':'string'}}}}];tools['messages']+=[{'role':'assistant','content':[{'type':'tool_use','id':'toolu_public','name':'Read','input':{'path':'/tmp/public-fixture.txt'}}]},{'role':'user','content':[{'type':'tool_result','tool_use_id':'toolu_public','content':'PUBLIC_TOOL_RESULT'}]}]
   status,raw=ask(tools);assert status==200;upstream=seen[-1];assert 'PUBLIC_TOOL_RESULT' in json.dumps(upstream);assert any(x.get('type')=='function_call' and x.get('call_id')=='toolu_public' for x in upstream['input']);assert any(x.get('type')=='function_call_output' and x.get('call_id')=='toolu_public' for x in upstream['input']);checks.append('tool_call_and_result_ids_preserved')
   status,raw=ask(dict(body,stream=True));assert status==200 and b'message_stop' in raw and b'OK' in raw;checks.append('stream_completed_through_messages_responses_bridge')
   proc.terminate();proc.wait(timeout=10);proc=None
   out={'passed':True,'isolated':True,'upstream':'synthetic loopback HTTP','version':'0.1.4777','checks':checks,'productionChanged':False,'userToolCommandsExecuted':False}
   if a.out:pathlib.Path(a.out).write_text(json.dumps(out,indent=2)+'\n')
   print(json.dumps(out))
 finally:
  if proc is not None:proc.terminate();proc.wait(timeout=10)
  if server is not None:server.shutdown();server.server_close()
if __name__=='__main__':main()
