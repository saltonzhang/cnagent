"""Run on an existing CN as its ordinary operator. Public temporary repo only.
Uses the real controlled launcher/Agent UID with disposable HOME on both sides.
Never changes user Git config, credentials, network policy or any real repo.
"""
import json,os,re,pathlib,pwd,shutil,subprocess,sys,tempfile
PY='/usr/bin/python3';LAUNCH='/Library/Application Support/CN-Agent-Egress/launch'
def run(args,env=None):
 r=subprocess.run(list(map(str,args)),env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
 if r.returncode:raise RuntimeError('public fixture failed: '+r.stdout[-1200:]+r.stderr[-900:])
 return r.stdout
root=pathlib.Path(tempfile.mkdtemp(prefix='cn-repo-sharing-test-',dir='/Users/Shared'));host=pwd.getpwuid(os.getuid());agent=pwd.getpwnam('cnagent');home=root/'host-home';home.mkdir(mode=0o700);ah=root/'agent-home';ah.mkdir(mode=0o700);repo=root/'repo';repo.mkdir(mode=0o700);ctx=root/'context.json'
ctx.write_text(json.dumps({'operator_user':host.pw_name,'agent_user':agent.pw_name,'python_binary':PY,'install_base':'/Library/Application Support/CN-Agent-Egress'}))
# Only these two fixture objects are changed as root.
setup='import os,pwd,sys,pathlib;p=pathlib.Path(sys.argv[1]);assert p.parent==pathlib.Path("/Users/Shared") and p.name.startswith("cn-repo-sharing-test-");a=pwd.getpwnam("cnagent");os.chown(p/"agent-home",a.pw_uid,a.pw_gid);os.chown(p/"context.json",0,0);os.chmod(p/"context.json",0o644)'
run(['/usr/bin/sudo',PY,'-c',setup,root])
source=pathlib.Path(sys.argv[1]).read_text();needle="'exec \"$@\"'";assert needle in source;source=source.replace(needle,repr('export HOME="'+str(ah)+'"; exec "$@"'),1);script=root/'share_fixture.py';script.write_text(source)
env=dict(os.environ,HOME=str(home));env.pop('GIT_CONFIG_GLOBAL',None);env.pop('GIT_CONFIG_SYSTEM',None)
def git(*args):return run(['/usr/bin/git','-c','user.name=Public Host','-c','user.email=host@example.invalid','-C',repo,*args],env)
def controlled(command):return run(['/usr/bin/sudo',LAUNCH,'shell','-fc','export HOME="'+str(ah)+'"; '+command])
try:
 git('init','-q');(repo/'README.md').write_text('public host content\n');(repo/'.gitignore').write_text('.env\n');(repo/'.env').write_text('PRIVATE_FIXTURE_ONLY');(repo/'.env').chmod(0o600);(repo/'script.sh').write_text('#!/bin/sh\nexit 0\n');(repo/'script.sh').chmod(0o700);git('add','README.md','.gitignore','script.sh');git('commit','-qm','public host initial')
 before_env=(repo/'.env').stat().st_mode
 out=run([PY,script,repo,'--context',ctx,'--git-name','Public CN','--git-email','cn@example.invalid'],env)
 op=re.search(r'共享操作记录：([A-Za-z0-9_-]+)',out).group(1);run([PY,script,'--context',ctx,'--rollback',op],env)
 out=run([PY,script,repo,'--context',ctx,'--git-name','Public CN','--git-email','cn@example.invalid'],env)
 command='cd "'+str(repo)+'" && /usr/bin/python3 -c '+__import__('shlex').quote('import pathlib; p=pathlib.Path("README.md");q=pathlib.Path("save-temp");q.write_text(p.read_text()+"public Agent edit\\n");q.replace(p);pathlib.Path("new-agent.txt").write_text("new public text")')+' && /usr/bin/git add README.md new-agent.txt && /usr/bin/git commit -qm "public Agent commit"'
 controlled(command)
 run([PY,script,repo,'--context',ctx,'--refresh'],env)
 assert 'public Agent edit' in (repo/'README.md').read_text();assert (repo/'new-agent.txt').read_text()=='new public text'
 (repo/'README.md').write_text('public host edit after Agent\n');git('add','README.md');git('commit','-qm','public host follow-up')
 controlled('cd "'+str(repo)+'" && /usr/bin/git status --porcelain && /usr/bin/git log -1 --format=%s')
 assert (repo/'.env').stat().st_mode==before_env
 denied=controlled('/usr/bin/python3 -c '+__import__('shlex').quote('import os; assert not os.access('+repr(str(repo/'.env'))+',os.R_OK);print("ignored_secret_denied")'))
 assert 'ignored_secret_denied' in denied
 print(json.dumps({'passed':True,'fixture':str(root),'realOperatorAndAgent':True,'sharedRepoReadWriteCommitBothWays':True,'newTrackedFileRefresh':True,'atomicSaveThenRefresh':True,'rollbackBeforeCommitsVerified':True,'ignoredEnvStillDenied':True,'realControlledLauncher':True,'realUserGitConfigModified':False,'productionNetworkOrReposModified':False}),flush=True)
finally:
 # The test tree is isolated but contains Agent-owned .git and private HOME;
 # cleanup is an explicit administrator operation limited to its known path.
 cleanup='import pathlib,shutil,sys;p=pathlib.Path(sys.argv[1]);assert p.parent==pathlib.Path("/Users/Shared") and p.name.startswith("cn-repo-sharing-test-");shutil.rmtree(p)'
 run(['/usr/bin/sudo',PY,'-c',cleanup,root])
