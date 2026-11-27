# 已安装 CN：只升级仓库共享组件（v3.3.0）

适用于已有 3.1.1／3.2.x 或明确核实的旧试点；不重装、不重新登记，不改变现有 UID、Key、证书、模型、额度、网络和 Mobile/Office 模式。

```text
请下载 https://github.com/saltonzhang/cnagent/releases/download/v3.3.0/CN-MAC-REPO-SHARING-UPDATE.zip 和同名 .sha256，校验 ZIP 及包内 MANIFEST.sha256，阅读 fleet-kit/repo-sharing/README.md 和适用 AGENTS.md。
先检查本机已有的宿主账号、受控账号、启动器和 root 管理的 Python 3.9+。优先使用现有合格运行时，不为这个组件重装整个环境。用 setup/install_repo_sharing.py --operator-user 当前宿主账号预览，再按本次已授权范围加 --apply；只安装 root 管理 helper，不启动或重启任何模型、代理、PF 或网络服务，不复制任何凭据。
安装组件本身不共享项目。先询问具体仓库路径及 Agent 的 Git 提交姓名/邮箱；只处理我明确选中的仓库。安全默认是已跟踪文件共享；排除 ignored、.env、SSH/GPG 等，遇到敏感项原权限过宽先停止核实。优先 /Users/Shared 专用项目目录；不得擅自开放 Home、加 --allow-home-traverse 或 safe.directory=*。明确说明共享 Git 历史和 hooks/config 的共同信任边界，父目录遍历需另行说明授权。
使用 share-repo 配置、--refresh 一键刷新。新文件 git add／编辑器原子保存后需要刷新；不宣称会自动共享所有新文件。先在临时仓库和临时 HOME 验证双方读写、本地提交、忽略文件保留权限和回滚，不用真实项目做试验提交，不执行 git push。
不顺带更改时区、默认模型、effort 或升级 Claude/Magpie。交付已安装组件版本、所选项目实际结果、刷新命令、私密操作记录位置和冲突保护回滚方法；未选项目时明确“工具就绪，项目共享待选择”。
```

若用户另行要求日本时区／别名修复，才使用同版本独立的 `CN-MAC-JST-UPDATE.zip`，先阅读对应手册预览，再应用；本次仓库共享更新不要求它。
