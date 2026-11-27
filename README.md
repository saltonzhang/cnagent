# CNAGENT v3.3.0

受控 Claude、本机独立 Magpie 与 JP 网络出口。新 CN 不获得 JP SSH 管理权限。

- [完整安装包](https://github.com/saltonzhang/cnagent/releases/download/v3.3.0/CN-MAC-AI-DEPLOYMENT-KIT.zip) · [SHA256](https://github.com/saltonzhang/cnagent/releases/download/v3.3.0/CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256)
- **已有 CN 无需重装**：[仓库共享组件小更新](https://github.com/saltonzhang/cnagent/releases/download/v3.3.0/CN-MAC-REPO-SHARING-UPDATE.zip) · [SHA256](https://github.com/saltonzhang/cnagent/releases/download/v3.3.0/CN-MAC-REPO-SHARING-UPDATE.zip.sha256)
- [新 CN 安装提示词](AI-INSTALL-PROMPT.md) · [已有 CN 升级提示词](AI-UPDATE-PROMPT.md) · [管理员签发提示词](AI-ADMIN-PROMPT.md)
- [安装手册](CN-MAC-AI-DEPLOYMENT.md) · [仓库共享手册](fleet-kit/repo-sharing/README.md) · [JP 管理手册](JP-MAC-DEVICE-ENROLLMENT.md)

## 本机仓库共享

整合并改造用户提供的 share-git-repo.py：识别本机宿主账号，不写死 chase；宿主与 cnagent 可在同一个明确授权仓库里读写、提交，使用个人的提交身份。默认只给已跟踪文件增加 ACL；新文件 git add 或编辑器原子保存后，使用一键刷新。

```sh
"/Library/Application Support/CN-Agent-Egress/share-repo" /Users/Shared/projects/example --git-name 'Agent Name' --git-email 'agent@example.com'
"/Library/Application Support/CN-Agent-Egress/share-repo" /Users/Shared/projects/example --refresh
```

不自动共享 Home、宿主 SSH/Keychain/Token，不设置 safe.directory=*。默认敏感文件排除，有组/其他用户可读的敏感排除项会阻止处理，要求先核实权限。Git 对象库历史及 hooks/config 为共同信任范围，不承诺隔离历史秘密。推荐 /Users/Shared 专用目录；Home 父目录遍历必须明确接受影响，不能自动加权限。私有远端的推送仍需要 Agent 独立凭证，工具不提供远端授权。

安装 helper 本身不改变任何仓库权限。既有 CN 用小更新内 install_repo_sharing.py 预览／apply，只添加组件，不重启原模型/网络服务，不改变设备身份；旧试点只做此组件升级，不接管其服务状态。仓库变更有每账户私密操作记录及冲突保护回滚，不撤销后续提交。

## 设备接入

新 CN：下载并校验完整 ZIP → 安装依赖和独立账户 → 导出 request.json → 管理员确认、签发独立 access.json → 管理员在 JP 管理台启用设备策略 → CN 导入验收。源码目录不含软件大文件，不直接用它安装。每台一个 Key；设备证书与 Key 由当前 JP 入口绑定。普通 CN 不需要管理员网页账号或 JP SSH。

JP 管理台分别控制模型、effort 和每设备 5H Token 预算，并显示备注及每日用量。原生签发/额度脚本支持 --period 5h|day|week|month，或明确批准的 --unlimited，默认不擅自放开额度。上游服务 Key 与设备 Key 是不同层，禁止交换设备 Key。

## 验证与范围

77 项 setup 测试 + 9 项基础测试通过。真实 CN162 双账户/受控启动器测试覆盖：双方提交、原子保存及新跟踪文件刷新、忽略 .env 仍不可读、初次共享回滚。双方均用临时 HOME 和临时仓库；没有修改个人 Git 配置或真实项目。见 [验收证据](REPO-SHARING-VALIDATION.json)。这不是全新 CN 完整系统安装或 20 人压测。

软件基线保持 Claude 2.1.198、官方前端 Magpie 0.1.4777、Python 3.14.10、iTerm2；JP 定制核心及账户不替换。默认 model=sonnet，三个默认别名指向 remote-magpie/group/cn-default，实际模型/effort 由 JP 设备策略决定。普通 VS Code、Codex 工具链以及尚待确认的自动模式分类修复不宣称已支持。

时区与默认别名小更新继续提供，不改系统时区、网络或凭证。受控进程 JST、Agent localtime 文件读取限制等保留；这些不保证完整隐藏宿主位置。既有 162 的 Mobile/Office、专用 SSH 目标、证书和 UID 不复制给别的 CN。
