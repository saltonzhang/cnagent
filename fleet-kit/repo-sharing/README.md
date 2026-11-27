# 同机 Git 仓库共享（宿主账号 + 受控 Agent）

源于用户提供的 `share-git-repo.py`，保留“仅 Git 已跟踪文件 + 明确刷新”的安全默认，移除了 `chase` 账号硬编码。默认不扫描或共享 Home，不复制 SSH、Keychain 或 GitHub Token，也不修改网络、JP、模型、额度或门禁。

新安装在配置受控账户后自动安装 `/Library/Application Support/CN-Agent-Egress/share-repo`。安装 helper 不会自动共享任何项目；必须明确选择仓库。新项目推荐放到 `/Users/Shared` 下宿主自己拥有的专用项目目录，避免开放 Home 父目录遍历。

在宿主账号的普通终端（不要 sudo 整个命令）运行：

```sh
"/Library/Application Support/CN-Agent-Egress/share-repo" "/Users/Shared/projects/example" --check
"/Library/Application Support/CN-Agent-Egress/share-repo" "/Users/Shared/projects/example" --git-name "Agent 提交姓名" --git-email "agent@example.com"
# 新文件 git add 后，或编辑器原子保存替换文件之后，一键补齐：
"/Library/Application Support/CN-Agent-Egress/share-repo" "/Users/Shared/projects/example" --refresh
```

运行时需要本机 sudo 授权，以通过原受控启动器执行 cnagent 自己拥有文件的权限步骤；不会以 root 身份运行 Git，不联网 fetch/push，不移交宿主私钥。双方交替修改、提交；不要同时执行 checkout、reset、rebase、合并等修改同一工作树和索引的操作。

仓库在宿主 Home 内且父目录无法遍历时，默认停止；明确接受影响后可加 `--allow-home-traverse`。它只给 Agent 添加必要父目录的 `search` ACL，不给 `list`，但可使原本世界可读且路径可猜的宿主文件可达，因此优先用 `/Users/Shared`。不会递归开放 Home。

可选安装参数：

```sh
bash install.sh --access-bundle /path/device.access.json \
  --share-repo /Users/Shared/projects/example \
  --git-name 'Agent Name' --git-email 'agent@example.com'
```

无 `--share-repo` 时只安装工具，AI 应先询问具体项目路径、提交身份。多个项目重复传该参数。新文件未跟踪、被忽略文件、`.env`、SSH/GPG 目录等不自动授予权限；同一 Git 对象库包含完整提交历史，**历史里提交过的敏感内容仍对双方可见**。子模块必须逐个处理；外部 alternates 对象库、异常路径、非普通文件和硬链接会停止或保持只读，不扩大授权。

Agent 使用按实际 `.git` 目录匹配的个人 `includeIf` 提交身份和 HTTPS URL 重写；不修改仓库 remote、不修改宿主身份，不设置 `safe.directory=*`。私有远端的拉取、推送仍需要 Agent 自己的远端权限及已有 JP 网络出口；本地 ACL 和提交姓名不是远端登录授权。

共享 `.git` 允许对方改配置和 hooks；宿主后续执行 Git 或构建可能执行其内容。这是对该仓库的共同信任，不能视为仓库内的恶意代码隔离。

## 现有 CN 升级（无需重装）

在现有 CN 的普通管理员终端运行，先预览，后加 `--apply`：

```sh
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 \
  fleet-kit/setup/install_repo_sharing.py --operator-user "$USER"
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 \
  fleet-kit/setup/install_repo_sharing.py --operator-user "$USER" --apply
```

若旧试点没有该版本 Python，可使用已有且 root 管理的 Python 3.9+，必须先核对版本和归属。该组件只添加 root 管理 helper 和公开账户上下文，不接管或重装旧试点，不重启服务，不改 UID、证书、Key、PF、沙箱或项目权限。

每次共享会输出操作编号。每个账户的私密记录在其 `~/.local/state/cnagent-repo-sharing/` 下；里面可能包含该账户原 Git 配置备份，不上传、不相互复制。

```sh
"/Library/Application Support/CN-Agent-Egress/share-repo" --rollback OPERATION_ID
```

回滚先处理 Agent，后处理宿主，只在文件 inode、当前 ACL、相关 Git 配置仍匹配时还原。提交或编辑替换了文件、其他配置被修改时拒绝覆盖，保留后续工作，需人工对照备份。不回滚项目内容、提交、远端授权或网络规则。

排除项不等于撤销原有权限：如果敏感文件本来就是 0644／目录 0755，开放仓库遍历后可能仍被读取。工具对预检发现的可由组／其他用户读取的敏感排除项会停止，要求先核实权限；不自动 chmod 私密文件，也不承诺撤销已有 ACL 或保护 Git 历史中的秘密。位于宿主 Home 内的项目还可能因 Claude Code 读取父级宿主 `.claude` 失败；不要因此开放宿主设置，优先使用专用 Shared 项目路径。
