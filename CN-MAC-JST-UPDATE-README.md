# 已安装 CN：日本时区小更新包 v3.2.3

适用：已完成 v3.1.1 / v3.2.0 / v3.2.1 的 v3 受管理安装。给受控启动器设置 `TZ=Asia/Tokyo` 并阻止受控进程查询宿主 localtime 文件，不安装软件、不修改系统时区/语言、不重签证书、不改 Key、额度、模型、代理或门禁，不重启服务。

先校验下载的外层 ZIP SHA256，再解压到新目录；在本目录校验：

```bash
shasum -a 256 -c MANIFEST.sha256
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 set_agent_timezone.py
```

上面只预览，不改文件。确认设备与安装记录匹配后：

```bash
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 set_agent_timezone.py --apply
```

保存输出的 `backup` 路径。退出旧 Claude 与受控 shell，再打开：

```bash
sudo "/Library/Application Support/CN-Agent-Egress/launch" shell
date '+%Y-%m-%d %H:%M:%S %Z (UTC%z)'
```

预期 JST/+0900；普通终端应保持原时区。语言设置未改，星期仍可能为中文。已运行的进程不会热更新。

回滚先预览，确认后应用：

```bash
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 set_agent_timezone.py --rollback /完整备份目录
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 set_agent_timezone.py --rollback /完整备份目录 --apply
```

自定义安装路径用 `--config /原安装/private/config.json`；需要绝对路径。异常权限、符号链接、未知安装或身份变化会停止；不得重置账户、伪造状态或删除目录绕过。后续启动器有其他改动时回滚会拒绝覆盖。

162 历史试点已经单独设置，无需重复运行；没有 v3 安装记录时通用工具会拒绝接管。旧安装器源码不会被本小包修改；以后需要完整 configure 时使用 v3.2.1，避免旧模板恢复中国默认时区。

这是默认显示设置，不是阻止读取本机信息。命令仍在 CN 执行，可覆盖 TZ 或读取系统元数据。全量安装和管理员额度规则见同版仓库手册；额度工具 v3.2.0 继续兼容，无需修改 JP。

本版也适用于已装 v3.2.1：该版仅设置 TZ，没有拦截系统时区文件。应用后，受控 readlink/stat/ls/读取 localtime 应失败；date 仍 JST。退出旧进程并新开会话，旧历史不会被清除。此拦截只针对已验证的文件入口，不保证阻止所有位置推断。162 已单独接入，无需重复执行。


## v3.2.3 also matches CN162 model defaults

The small archive now contains set_agent_defaults.py alongside set_agent_timezone.py. Run each with the installed Python 3.14 and sudo: first without flags to preview, then with --apply. The defaults tool sets model=sonnet and maps all three default aliases to remote-magpie/group/cn-default. It preserves effort/auth/permissions, providers and enrollment request. It requires an already configured central-group managed installation; no automatic adoption of legacy pilots.

Each tool has its own backup directory and --rollback preview/apply flow. Do not mix backup directories. Reopen the parent controlled shell and start a new conversation. This does not hide model/effort menus, add a server model allowlist, or upgrade Claude. CN162 is already configured and requires no repeat application.
