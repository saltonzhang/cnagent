#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14
"""在当前 Git 工作树中，为宿主账号和受控 Agent 设置共享权限与每仓库独立的 Git 身份。"""
import argparse
import base64
import datetime
import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

GIT = "/usr/bin/git"
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
LAUNCH = "/Library/Application Support/CN-Agent-Egress/launch"
OPERATOR_USER = None
AGENT_USER = "cnagent"
CONTEXT_PATH = "/Library/Application Support/CN-Agent-Egress/repo-sharing.json"
JOURNAL = None
COMMON = "read,write,append,readattr,writeattr,readextattr,writeextattr,readsecurity"
WEB_HOSTS = {"github.com": "github.com", "ssh.github.com": "github.com",
             "gitlab.com": "gitlab.com", "altssh.gitlab.com": "gitlab.com",
             "bitbucket.org": "bitbucket.org"}


class Stop(Exception):
    pass


def context(path):
    global OPERATOR_USER, AGENT_USER, PYTHON, LAUNCH, CONTEXT_PATH
    path=Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.stat().st_uid!=0 or path.stat().st_mode & 0o022:
        raise Stop("缺少可信的 root 管理共享上下文，请先安装仓库共享组件。")
    c=json.loads(path.read_text())
    for k in ("operator_user","agent_user"):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,62}",c[k]):raise Stop("账户配置无效。")
        pwd.getpwnam(c[k])
    if c["operator_user"] in (c["agent_user"],"root"):raise Stop("宿主与受控账户必须独立。")
    OPERATOR_USER,AGENT_USER=c["operator_user"],c["agent_user"]
    PYTHON=c["python_binary"];LAUNCH=str(Path(c["install_base"])/"launch");CONTEXT_PATH=str(path)
    for file in [Path(PYTHON),Path(LAUNCH)]:
        if file.is_symlink(): file=file.resolve(strict=True)
        if not file.is_absolute() or not file.is_file() or file.stat().st_uid!=0 or file.stat().st_mode & 0o022:raise Stop("运行时或受控启动器不可信。")

def acl_entries(path):
    r=subprocess.run(["/bin/ls","-dle",str(path)],capture_output=True,text=True)
    if r.returncode:raise Stop("无法读取 ACL；未将未知权限当成空权限。")
    return [m.group(1) for line in r.stdout.splitlines() if (m:=re.match(r"^\s+\d+: (.+)$",line))]

class Journal:
    def __init__(self,op,request=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",op):raise Stop("操作编号无效。")
        parent=Path.home()/".local/state/cnagent-repo-sharing"
        parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if parent.resolve()!=parent:raise Stop("操作记录目录不允许符号链接。")
        parent.chmod(0o700);self.path=parent/(op+".jsonl")
        if self.path.exists():raise Stop("操作记录已存在，请勿覆盖。")
        self.data={"schema":1,"owner":os.getuid(),"request":request,"paths":{},"configs":{}};self.save("init")
    @classmethod
    def open(cls,op):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",op):raise Stop("操作编号无效。")
        obj=object.__new__(cls);obj.path=Path.home()/".local/state/cnagent-repo-sharing"/(op+".jsonl")
        if obj.path.is_symlink() or obj.path.stat().st_uid!=os.getuid() or obj.path.stat().st_mode & 0o077:raise Stop("操作记录权限无效。")
        obj.data=None
        for line in obj.path.read_text().splitlines():
            event=json.loads(line)
            if event["section"]=="init":obj.data=event["value"]
            elif event["section"] in ("paths","configs"):obj.data[event["section"]][event["key"]]=event["value"]
            elif event["section"]=="done":obj.data["rolled_back"]=True
        if not obj.data or obj.data["owner"]!=os.getuid():raise Stop("操作记录归属不匹配。")
        return obj
    def save(self,section,key=None):
        value=self.data if section=="init" else self.data.get(section,{}).get(key) if key else True
        event={"section":section,"key":key,"value":value}
        fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w") as f:json.dump(event,f);f.write("\n");f.flush();os.fsync(f.fileno())
    def before(self,path):
        p=Path(path);s=p.lstat()
        if s.st_uid!=os.getuid():raise Stop("不能修改其他账户拥有文件的 ACL。")
        key=str(p)
        if key not in self.data["paths"]:self.data["paths"][key]={"inode":s.st_ino,"device":s.st_dev,"before":acl_entries(p),"after":None};self.save("paths",key)
    def after(self,path):self.data["paths"][str(path)]["after"]=acl_entries(path);self.save("paths",str(path))
    def config(self,path):
        p=Path(path)
        if p.is_symlink() or (p.exists() and (not p.is_file() or p.stat().st_uid!=os.getuid())):raise Stop("Git 配置归属或类型异常。")
        data=p.read_bytes() if p.exists() else None
        if data is not None and len(data)>1048576:raise Stop("Git 配置过大，停止。")
        self.data["configs"][str(p)]={"before":base64.b64encode(data).decode() if data is not None else None,"mode":p.stat().st_mode & 0o777 if p.exists() else 0o600,"after":None};self.save("configs",str(p))
    def finish_configs(self):
        for name,item in self.data["configs"].items():
            item["after"]=hashlib.sha256(Path(name).read_bytes()).hexdigest();self.save("configs",name)
    def rollback(self):
        # Preflight every item before undoing anything. Replaced files or later
        # changes require review instead of wiping somebody else's work.
        for name,item in self.data["paths"].items():
            p=Path(name);st=p.lstat()
            if st.st_uid!=os.getuid() or (st.st_dev,st.st_ino)!=(item["device"],item["inode"]) or acl_entries(p)!=item["after"]:raise Stop("文件或 ACL 已变化，停止自动回滚以保留后续修改。")
        for name,item in self.data["configs"].items():
            p=Path(name)
            if p.is_symlink() or item["after"] is None or hashlib.sha256(p.read_bytes()).hexdigest()!=item["after"]:raise Stop("Git 配置已变化，须人工对照私密备份。")
        for name,item in self.data["configs"].items():
            p=Path(name)
            if item["before"] is None:p.unlink()
            else:
                fd,tmp=tempfile.mkstemp(dir=p.parent)
                with os.fdopen(fd,"wb") as f:f.write(base64.b64decode(item["before"]))
                os.chmod(tmp,item["mode"]);os.replace(tmp,p)
        for name,item in reversed(list(self.data["paths"].items())):
            if item["before"]:r=subprocess.run(["/bin/chmod","-E",name],input=("\n".join(item["before"])+"\n").encode(),capture_output=True)
            else:r=subprocess.run(["/bin/chmod","-h","-N",name],capture_output=True)
            if r.returncode:raise Stop("ACL 回滚未完成，请核对私密操作记录。")
        self.data["rolled_back"]=True;self.save("done");print("本账户的共享配置已回滚；未改动仓库内容或提交。")

def grant_parents(root,common):
    paths=set(root.parent.parents)|{root.parent}
    if not common.is_relative_to(root):paths|=set(common.parent.parents)|{common.parent}
    home=Path(pwd.getpwnam(OPERATOR_USER).pw_dir)
    if home in paths and not (JOURNAL and JOURNAL.data["request"].get("allow_home_traverse")):
        raise Stop("仓库位于宿主 Home 内。建议放到 /Users/Shared 的专用项目目录；若明确接受父目录遍历权限影响，可加 --allow-home-traverse。")
    for p in sorted(paths,key=lambda p:len(p.parts)):
        if p.lstat().st_uid==os.getuid():add_acl([p],"user:"+AGENT_USER,"search")


def git(cwd, *args, optional=False):
    p = subprocess.run([GIT, "--no-optional-locks", "-c", "core.fsmonitor=false",
                        "-C", cwd, *args], capture_output=True)
    if p.returncode and not (optional and p.returncode == 1):
        raise Stop("Git 读取或写入失败，请检查仓库、账户目录和 Git 配置。")
    return p.stdout


def value(data):
    return os.fsdecode(data.removesuffix(b"\n"))


def nul(data):
    return list(map(os.fsdecode, filter(None, data.split(b"\0"))))


def layout(start):
    start = Path(start).resolve(strict=True)
    if not start.is_dir() or ".git" in start.parts:
        raise Stop("请在工作目录或它的子目录运行。")
    root = next((p for p in (start, *start.parents) if os.path.lexists(p / ".git")), None)
    if not root:
        raise Stop("这里没有 Git 工作树；裸仓库没有可共同编辑的工作目录。")
    if (root / ".git").is_symlink() or root.name == "*":
        raise Stop("仓库标记为符号链接或路径会扩大 Git 信任范围；已停止。")
    paths = []
    for flag in ("--show-toplevel", "--absolute-git-dir", "--git-common-dir"):
        out = git(root, "-c", "safe.directory=" + str(root),
                  "rev-parse", "--path-format=absolute", flag)
        p = Path(value(out))
        if p.resolve(strict=True) != p or "\n" in str(p):
            raise Stop("Git 路径包含间接跳转或换行；已停止。")
        paths.append(p)
    if paths[0] != root:
        raise Stop("工作树路径和 Git 登记不匹配。")
    _, admin, common = paths
    if admin != common:
        if admin.parent != common / "worktrees" or not (admin / "gitdir").is_file():
            raise Stop("独立工作树的管理目录无法核实。")
        back = Path(value((admin / "gitdir").read_bytes()))
        if not back.is_absolute():
            back = admin / back
        if back.resolve() != root / ".git":
            raise Stop("关联工作树的双向路径不匹配。")
    if (common == root or root.is_relative_to(common) or common in (Path("/"), Path.home())
            or any(part in {".ssh", ".gnupg", ".state", "backups"} for part in common.parts)):
        raise Stop("Git 公共目录与工作目录边界异常。")
    if (common/"objects/info/alternates").exists() and (common/"objects/info/alternates").stat().st_size:
        raise Stop("存在仓库外的 alternates 对象库，须单独审核，未自动扩大共享。")
    if not (common / "objects").is_dir() or not (admin / "HEAD").is_file():
        raise Stop("缺少标准 Git 对象库或 HEAD。")
    return root, admin, common


def scoped(root, *args, **opts):
    return git(root, "-c", "safe.directory=" + str(root), *args, **opts)


def remote_urls(root):
    remotes = {}
    for name in value(scoped(root, "remote")).splitlines():
        if name.startswith("-") or any(c.isspace() for c in name):
            raise Stop("远端名不适合命令行操作。")
        def urls(key):
            return nul(scoped(root, "config", "--null", "--get-all",
                              "remote." + name + "." + key, optional=True))
        fetch = urls("url")
        if not fetch:
            raise Stop("远端缺少可识别的 URL。")
        remotes[name] = (fetch, urls("pushurl") or fetch)
    return remotes


def validate_https(url):
    u = urlsplit(url)
    if (u.scheme != "https" or not u.hostname or u.username is not None or
            u.password is not None or u.query or u.fragment or not u.path.strip("/") or
            any(c.isspace() or ord(c) < 32 for c in url)):
        raise Stop("请使用托管平台提供的不含用户名、令牌或查询串的 HTTPS 克隆地址。")
    return url


def ssh_hostname(repo, host, user):
    """只让 OpenSSH 展开普通账户的配置，支持 Host、Include 和通配符。"""
    if not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", host):
        return None
    if user and not re.fullmatch(r"[a-zA-Z0-9_.-]+", user):
        return None
    if (os.environ.get("GIT_SSH_COMMAND") or os.environ.get("GIT_SSH") or
            scoped(repo, "config", "--get", "core.sshCommand", optional=True)):
        return None
    # ssh -G 只打印有效配置。阻止联网、写普通文件和派生子进程（包括 Match exec）。
    policy = ('(version 1)(allow default)(deny network*)(deny file-write*)'
              '(allow file-write-data (literal "/dev/null"))(deny process-fork)')
    try:
        p = subprocess.run(["/usr/bin/sandbox-exec", "-p", policy, "/usr/bin/ssh",
                            "-G", "-o", "CanonicalizeHostname=no", "--",
                            f"{user}@{host}" if user else host],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode == 0:
        for line in p.stdout.splitlines():
            if line.startswith(b"hostname "):
                return os.fsdecode(line[9:]).strip().lower()
    return None


def destination(raw, *, ssh_repo=None):
    """把托管平台的 SSH 地址转换为 HTTPS。路径无法可靠推导时由操作者填写。"""
    if not raw or any(ord(c) < 32 for c in raw) or re.match(r"^[\w+.-]+::", raw):
        raise Stop("远端含不受支持的自定义传输或控制字符。")
    if "://" in raw:
        u = urlsplit(raw)
        if u.scheme == "https":
            return validate_https(raw)
        if u.password is not None or u.query or u.fragment or (u.username and u.scheme != "ssh"):
            raise Stop("远端地址可能带有凭据，先将凭据移出共享 Git 配置。")
        if u.scheme == "file":
            return raw
        if u.scheme not in ("ssh", "git", "http"):
            raise Stop("请先核实此远端使用的传输方式。")
        is_ssh, user = u.scheme == "ssh", u.username
        host, path = u.hostname, u.path.lstrip("/")
        if u.port is not None and not (is_ssh and u.port == 22):
            return None
    else:
        match = re.match(r"^(?:([^/@:]+)@)?([^/:]+):(.+)$", raw)
        if not match:
            return raw  # 本地路径不自动扩展授权
        is_ssh = True
        user, host, path = match.groups()
    host = (host or "").lower()
    if is_ssh and ssh_repo is not None:
        host = ssh_hostname(ssh_repo, host, user)
    host = WEB_HOSTS.get(host)
    if host and re.fullmatch(r"[\w.-]+(?:/[\w.-]+)+", path):
        return validate_https("https://" + host + "/" + path)
    return None


def routes(remotes, check=False, *, repo=None):
    mapping = {}
    for name, pair in remotes.items():
        for direction, urls in zip(("拉取", "推送"), pair):
            for i, raw in enumerate(urls, 1):
                if raw in mapping:
                    continue
                url = destination(raw, ssh_repo=repo)
                label = f"远端 {name} 的{direction}地址 {i}"
                if url is None:
                    if check:
                        print(label + " 需在首次配置时填入对应的 HTTPS 克隆地址。")
                    else:
                        url = validate_https(input(label + " 对应的 HTTPS 克隆地址：").strip())
                elif url != raw:
                    print(label + " 已自动识别为 " + url)
                mapping[raw] = url
    return mapping


def protected(rel):
    return (any(x in {".ssh", ".gnupg", ".state", "backups"} for x in rel.parts)
            or rel.name in {"id_rsa", "id_ed25519", ".env"}
            or rel.as_posix() in {"proxy/subscriptions.env", "proxy/iproyal-proxies.yaml"}
            or (rel.parts[:2] in (("config", "hosts"), ("config", "deployments")) and rel.name.endswith(".env"))
            or (rel.name.startswith(".env.") and not rel.name.endswith((".example", ".sample", ".template"))))


def check_protected_path(path, rel):
    if protected(rel) and path.exists() and not path.is_symlink() and path.stat().st_mode & 0o044:
        raise Stop("排除的敏感文件或目录本身对组/其他用户可读。请先核实并收紧权限或移到仓库外；工具不会修改它。")


def inventory(root, admin, common):
    groups = {k: set() for k in ("dirs", "removable", "meta", "files", "links", "readonly", "traverse", "old_temps")}
    def add(p, key):
        info = p.lstat()
        if stat.S_ISLNK(info.st_mode):
            if key == "links":
                groups[key].add(p)
            return
        if key in ("dirs", "meta") and not stat.S_ISDIR(info.st_mode):
            raise Stop("目录类型在预检期间发生变化。")
        if key in ("files", "readonly"):
            if not stat.S_ISREG(info.st_mode):
                raise Stop("发现非常规文件，已停止。")
            if info.st_nlink > 1:
                if p.is_relative_to(common / "objects"):
                    groups["readonly"].add(p)
                    return
                raise Stop("存在多重硬链接；为避免改变另一条路径的权限，已停止。")
        groups[key].add(p)
    add(root, "dirs")
    ignored = set(nul(scoped(root, "ls-files", "-z", "--cached", "--ignored", "--exclude-standard")))
    # 含未跟踪内容或被排除条目的目录不加“删除目录本身”的 ACL。
    keep = {root}
    temp_candidates = []
    for flags in ([], ["--ignored"]):
        for entry in nul(scoped(root, "ls-files", "-z", "--others", "--directory", "--exclude-standard", *flags)):
            p = root / entry.rstrip("/")
            check_protected_path(p,Path(entry.rstrip("/")))
            keep.update(p.parents)
            if not flags and not entry.endswith("/"):
                match = re.fullmatch(r"(.+)\.tmp\.[0-9]+\.[0-9a-fA-F]{6,64}", p.name)
                if match:
                    temp_candidates.append((p, p.with_name(match[1])))
    for entry in nul(scoped(root, "ls-files", "-z", "--cached")):
        rel = Path(entry)
        if rel.is_absolute() or ".." in rel.parts:
            raise Stop("Git 索引含异常路径。")
        p = root / rel
        if entry in ignored or protected(rel):
            check_protected_path(p,rel)
            keep.update(p.parents)
            continue
        if p.parent.resolve() != p.parent or not os.path.lexists(p):
            continue
        if p.is_dir() and not p.is_symlink():
            keep.update(p.parents)
            continue  # gitlink 对应的子模块需从子模块自身运行
        if p.lstat().st_dev != root.stat().st_dev:
            raise Stop("发现跨卷跟踪文件，请分别核实。")
        add(p, "links" if p.is_symlink() else "files")
        for parent in p.parents:
            if parent == root:
                break
            add(parent, "dirs")
    groups["removable"] = groups["dirs"] - keep
    for p, target in temp_candidates:
        if target in groups["files"] and p.parent.resolve() == p.parent:
            try:
                info = p.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                groups["old_temps"].add(p)
    if admin != root / ".git":
        add(root / ".git", "readonly")
    def fail(e):
        raise e
    if admin != common:
        groups["traverse"].add(admin.parent)
    for top in dict.fromkeys((common, admin)):
        device = top.stat().st_dev
        for folder, subdirs, names in os.walk(top, followlinks=False, onerror=fail):
            p = Path(folder)
            add(p, "meta")
            subdirs[:] = [d for d in subdirs if not (p / d).is_symlink()
                          and (p / d).stat().st_dev == device
                          and not (p == common and d in ("modules", "worktrees"))]
            for n in names:
                add(p / n, "files")
    return groups


def add_acl(paths, principal, rights):
    ace = f"{principal} allow {rights}"
    for p in paths:
        def normalized(entry):
            left, sep, right=entry.partition(" allow ");return (left,frozenset(right.split(","))) if sep else (entry,frozenset())
        if any(normalized(entry)==normalized(ace) for entry in acl_entries(p)): continue
        if JOURNAL: JOURNAL.before(p)
        result=subprocess.run(["/bin/chmod","-h","+a",ace,str(p)],stderr=subprocess.DEVNULL)
        if JOURNAL: JOURNAL.after(p)
        if result.returncode: raise Stop("ACL 写入失败；已记录完成的项，可核对后回滚或重跑。")


def allow_owner_cleanup(groups, owner):
    # macOS 的 group:owner 随文件的实际所有者匹配。仅授予删除，不向对方开放新文件。
    directories = [p for p in groups["dirs"] if p.lstat().st_uid == owner]
    add_acl(directories, "group:owner", "delete,file_inherit,directory_inherit,limit_inherit,only_inherit")
    remnants = []
    for p in groups["old_temps"]:
        try:
            info = p.lstat()
        except FileNotFoundError:
            continue
        if info.st_uid == owner and stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            remnants.append(p)
    add_acl(remnants, "group:owner", "delete")


def grant(groups, owner, peer):
    def owned(key):
        return [p for p in groups[key] if p.lstat().st_uid == owner]
    def acl(paths, user, rights):
        add_acl(paths, "user:" + user, rights)
    files = owned("files")
    acl(files, peer, COMMON + ",delete")
    acl([p for p in files if p.lstat().st_mode & stat.S_IXUSR], peer, "execute")
    acl(owned("links"), peer, "delete")
    acl([p for p in owned("readonly") if p.lstat().st_nlink == 1], peer, "read,readattr")
    acl(owned("dirs"), peer, "list,search,add_file,add_subdirectory,readattr,readextattr,readsecurity")
    acl(owned("removable"), peer, "delete")
    acl(owned("traverse"), peer, "search")
    allow_owner_cleanup(groups, owner)
    for account in (OPERATOR_USER, AGENT_USER):
        acl(owned("meta"), account, COMMON + ",file_inherit,directory_inherit")
        acl(owned("meta"), account, "search,delete_child,directory_inherit")


def config_location(admin):
    suffix = hashlib.sha256(os.fsencode(admin)).hexdigest()
    return Path.home() / ".config/git/cnagent-shares" / (suffix + ".inc")


def configured_routes(conf):
    data = git(Path.home(), "config", "--null", "--file", str(conf),
               "--get-regexp", r"^url\..*\.insteadof$", optional=True)
    result = {}
    for row in nul(data):
        key, _, raw = row.partition("\n")
        result[raw] = key.removeprefix("url.").removesuffix(".insteadof")
    return result


def check_destinations(remotes, rewrites):
    for pair in remotes.values():
        for urls in pair:
            for raw in urls:
                if raw in rewrites:
                    validate_https(rewrites[raw])
                elif destination(raw) != raw:
                    raise Stop("远端已变更，请用普通模式重新设置 HTTPS 地址。")


def agent_preflight(request):
    root, admin, common = map(Path, request["layout"])
    ancestors = [root.parent]
    if not common.is_relative_to(root):
        ancestors.append(common.parent)
    if any(not os.access(p, os.X_OK) for p in ancestors):
        raise Stop("cnagent 无法穿过仓库父目录或工作树登记目录。请先核实该目录的遍历权限。")
    conf = config_location(admin)
    if conf.parent.resolve() != conf.parent or conf.is_symlink():
        raise Stop("个人配置路径是符号链接。")
    if request["refresh"]:
        if not conf.is_file():
            raise Stop("该工作树尚未用通用版配置，请先运行一次不带 --refresh 的命令。")
        check_destinations(request["remotes"], configured_routes(conf))


def as_agent(source, phase, request):
    cmd = ["/usr/bin/sudo", LAUNCH, "shell", "-fc", 'exec "$@"', "zsh",
           PYTHON, "-I", "-B", "-c", source, phase]
    if subprocess.run(cmd, input=json.dumps(request).encode()).returncode:
        raise Stop("受控账户步骤未完成；请查看上方提示。")


def verify_worktree_save(root):
    # 实测编辑器的原子保存顺序。仅操作本次排他创建的临时文件。
    paths = []
    try:
        for _ in range(2):
            with tempfile.NamedTemporaryFile(dir=root, prefix=".cnagent-save-", delete=False) as f:
                paths.append(Path(f.name))
                f.write(b"save-check")
        os.replace(paths[1], paths[0])
        paths[0].unlink()
    except OSError as exc:
        raise Stop(f"工作目录中的创建、替换或删除失败（errno={exc.errno}）。") from exc
    finally:
        for p in paths:
            try:
                p.unlink(missing_ok=True)
            except PermissionError:
                info = p.lstat()
                if info.st_uid == os.getuid() and info.st_nlink == 1 and stat.S_ISREG(info.st_mode):
                    add_acl([p], "group:owner", "delete")
                    p.unlink()


def configure_agent(request):
    root, admin, common = layout(request["root"])
    if list(map(str, (root, admin, common))) != request["layout"]:
        raise Stop("账户切换前后 Git 管理路径不一致。")
    home = Path.home()
    conf = config_location(admin)
    # Git 的 includeIf.gitdir 使用通配符匹配；对真实路径中的特殊字符转义。
    condition = re.sub(r"([\\*?\[])", r"\\\1", str(admin))
    include_key = "includeIf.gitdir:" + condition + ".path"
    remotes = remote_urls(root)
    if remotes != {n: tuple(v) for n, v in request["remotes"].items()}:
        raise Stop("配置期间远端发生变化，请重新预检。")
    if request["refresh"]:
        if not conf.is_file():
            raise Stop("此工作树尚未配置，请先运行一次不带 --refresh 的命令。")
    else:
        conf.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if conf.parent.resolve() != conf.parent or conf.is_symlink():
            raise Stop("个人配置路径是符号链接。")
        JOURNAL.config(home/".gitconfig")
        JOURNAL.config(conf)
        with tempfile.NamedTemporaryFile(dir=conf.parent, delete=False) as holder:
            tmp = Path(holder.name)
        try:
            for role in ("author", "committer"):
                for field in ("name", "email"):
                    git(home, "config", "--file", str(tmp), role+"."+field, request[field])
            for raw, url in request["routes"].items():
                if raw != url:
                    git(home, "config", "--file", str(tmp), "--add", "url."+validate_https(url)+".insteadOf", raw)
            git(home, "config", "--file", str(tmp), "credential.useHttpPath", "true")
            os.replace(tmp, conf)
        finally:
            tmp.unlink(missing_ok=True)
        for key, val in (("safe.directory", str(root)), (include_key, str(conf))):
            git(home, "config", "--global", "--fixed-value", "--replace-all", key, val, val)
    if JOURNAL: JOURNAL.finish_configs()
    for role, label in (("author", "AUTHOR"), ("committer", "COMMITTER")):
        name = value(git(home, "config", "--file", str(conf), "--get", role+".name"))
        email = value(git(home, "config", "--file", str(conf), "--get", role+".email"))
        if not value(git(root, "var", "GIT_"+label+"_IDENT")).startswith(f"{name} <{email}> "):
            raise Stop("当前仓库的实际 Git 身份与专用配置不匹配。")
    rewrites = configured_routes(conf)
    check_destinations(remotes, rewrites)
    for name, pair in remotes.items():
        for flags, urls in zip(([], ["--push"]), pair):
            effective = value(git(root, "remote", "get-url", "--all", *flags, name)).splitlines()
            expected = [rewrites.get(raw, raw) for raw in urls]
            if effective != expected:
                raise Stop("实际远端与已配置地址不匹配，请重新配置该仓库。")
    groups = inventory(root, admin, common)
    grant(groups, os.getuid(), OPERATOR_USER)
    if any(not os.access(p, os.R_OK) for p in groups["readonly"]):
        raise Stop("共享对象或 Git 标记文件不可读；请先检查文件及其父目录。")
    if any(not os.access(p, os.R_OK|os.W_OK) for p in groups["files"]):
        raise Stop("仍有需要协作的文件缺少读写权限。")
    verify_worktree_save(root)
    with tempfile.TemporaryFile(dir=admin) as f:
        f.write(b"cnagent-permission-check"); f.flush()
    print("本机校验通过：工作目录创建、替换和删除成功，Git 写权限、提交身份及远端设置已核对。")


def main():
    global OPERATOR_USER, AGENT_USER, PYTHON, LAUNCH, CONTEXT_PATH, JOURNAL
    os.umask(0o077)
    if sys.platform != "darwin": raise Stop("仅支持 macOS ACL。")
    if sys.version_info < (3,9): raise Stop("需要 root 管理的 Python 3.9 或更高版本。")
    for key in ("GIT_DIR","GIT_WORK_TREE","GIT_COMMON_DIR","GIT_INDEX_FILE","GIT_OBJECT_DIRECTORY"):
        os.environ.pop(key, None)
    if sys.argv[1:] in (["--agent"], ["--verify-access"], ["--rollback-agent"]):
        request = json.load(sys.stdin)
        context(request["context_path"])
        if pwd.getpwuid(os.getuid()).pw_name != AGENT_USER:
            raise Stop("此步骤须通过受控启动器进入 cnagent。")
        if sys.argv[1] == "--rollback-agent":
            try: Journal.open(request["operation_id"]).rollback()
            except FileNotFoundError: print("没有可用的受控账户修改记录；仅继续核对宿主记录。")
            return
        if sys.argv[1] == "--agent": JOURNAL = Journal(request["operation_id"], request)
        if sys.argv[1] == "--verify-access":
            agent_preflight(request)
        else:
            configure_agent(request)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="仓库目录或子目录，默认当前位置")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只读预检")
    mode.add_argument("--refresh", action="store_true", help="按最新索引补齐已配置仓库的权限")
    parser.add_argument("--context", default=CONTEXT_PATH, help="root-owned installed sharing context")
    parser.add_argument("--allow-home-traverse", action="store_true", help="明确允许给 Agent 添加宿主所拥有父目录的 search ACL，不授予目录列表权限")
    parser.add_argument("--git-name")
    parser.add_argument("--git-email")
    parser.add_argument("--rollback", metavar="OPERATION_ID")
    args = parser.parse_args()
    context(args.context)
    if pwd.getpwuid(os.getuid()).pw_name != OPERATOR_USER:
        raise Stop("请从配置中宿主账号的普通终端运行，勿用 sudo 启动整个脚本。")
    if args.rollback:
        journal=Journal.open(args.rollback)
        as_agent(Path(__file__).read_text(), "--rollback-agent", journal.data["request"])
        journal.rollback(); return
    root, admin, common = layout(args.path)
    print("当前工作目录：",root,flush=True)
    if common != root / ".git":
        print("该工作树使用的 Git 公共目录：",common,flush=True)
        print("同一仓库的关联工作树共享对象和引用。其他工作树的文件和索引不在本次范围。")
    groups = inventory(root, admin, common)
    uids = {os.getuid(), pwd.getpwnam(AGENT_USER).pw_uid}
    # 历史临时文件可能随时被编辑器移走，只在其所有者的修复步骤再次核实。
    if any(p.lstat().st_uid not in uids for key, paths in groups.items()
           if key != "old_temps" for p in paths):
        raise Stop("范围内存在其他账户拥有的文件，请先核实归属。")
    # 共享整个 Git 对象库意味着历史里的内容对两个账户均可见。
    headers = nul(scoped(root, "config", "--local", "--null", "--get-regexp", r"^http\.(.*\.)?extraheader$", optional=True))
    if any(re.match(r"(?i)\s*(?:authorization|proxy-authorization|cookie)\s*:", row.partition("\n")[2]) for row in headers):
        raise Stop("共享 Git 配置内含认证头。请先把凭据移到个人凭据管理器。")
    remotes = remote_urls(root)
    print(f"本次有 {len(groups['files'])} 个常规文件、{len(remotes)} 个远端。",flush=True)
    if args.check:
        routes(remotes, check=True, repo=root)
        print("只读预检完成。")
        return
    request = dict(root=str(root), layout=list(map(str, (root, admin, common))),
                   remotes=remotes, refresh=args.refresh, allow_home_traverse=args.allow_home_traverse, context_path=CONTEXT_PATH, operation_id=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+str(os.getpid()))
    if args.refresh:
        for pair in remotes.values():
            for urls in pair:
                for raw in urls:
                    destination(raw)
    else:
        request["routes"] = routes(remotes, repo=root)
        request["name"] = (args.git_name or input("受控 Agent 的 Git 提交姓名：")).strip()
        request["email"] = (args.git_email or input("受控 Agent 的 Git 提交邮箱：")).strip()
        if (not request["name"] or "@" not in request["email"]
                or any(c in request["name"] + request["email"] for c in "\r\n<>")):
            raise Stop("请输入有效的姓名和邮箱。")
    subprocess.run(["/usr/bin/sudo", "-v"], check=True)
    source = Path(__file__).read_text()
    JOURNAL = Journal(request["operation_id"], request)
    grant_parents(root, common)
    as_agent(source, "--verify-access", request)
    grant(groups, os.getuid(), AGENT_USER)
    as_agent(source, "--agent", request)
    print("共享操作记录：" + request["operation_id"] + "；新跟踪文件或原子保存后可用 --refresh 补齐。")


if __name__ == "__main__":
    try:
        main()
    except (Stop,OSError,ValueError,KeyError,EOFError,subprocess.CalledProcessError) as exc:
        sys.exit("配置停止："+(str(exc) if isinstance(exc,Stop) else type(exc).__name__))
