# 新 CN Mac 安装提示词（v3.3.0）

在普通管理员账户有终端权限的 AI 中使用：

```text
请按 https://github.com/saltonzhang/cnagent/releases/tag/v3.3.0 实际安装本机受控 Claude 环境，不要只给方案。
下载同版 CN-MAC-AI-DEPLOYMENT-KIT.zip 和 SHA256，校验后阅读包内 CN-MAC-AI-DEPLOYMENT.md、适用 AGENTS.md，先检查系统、账户、端口及已有安装，安装所有必要软件。未知试点或账户冲突时停止，不删除状态绕过。
按 162 当前配置规则：Claude 默认 model=sonnet；ANTHROPIC_DEFAULT_SONNET_MODEL、ANTHROPIC_DEFAULT_OPUS_MODEL、ANTHROPIC_DEFAULT_HAIKU_MODEL 全部指向 remote-magpie/group/cn-default，实际模型由 JP 统一选择。菜单可以保留多个 Custom 标签；不隐藏菜单、不新加模型白名单、不强制 effort。Claude 保持 2.1.198；新装 CN 前端 Magpie 为经验证的官方 0.1.4777；JP 定制核心不替换，不加入未接入的分类修复。
复用办公室现有 WireGuard 和 JP 10.9.8.30。CN 不 SSH 登录 JP，不索取其管理凭据。逐机生成私钥和 request.json，告诉我申请文件路径，等待管理员确认设备并设置、核验独立 Key 的额度后返回 access.json，管理员还需在 JP 管理台配置并启用该设备策略（普通 CN 不索要管理账号），再导入继续安装；不自行默认不限额，不共享其他设备 Key。
接入包含秘密，Key 默认自动配置；如管理员省略 Key，仅通过本机隐藏输入。不打印 Key、私钥、接入包正文，不上传到仓库。
保留现有翻译、门禁、审计和两个开关，失败不能回退国内直连。不要复制 162 的设备身份、UID、Mobile 路由或专用 SSH 授权；这些不属于通用基线。
使用 JP Agent Profile 或新建的 Start-JP-Agent-Fresh.command 进入专用账户；不要安装 iTerm Claude 集成或重置个人偏好。要退出旧 Claude 和旧父 shell，再新开会话，不能把恢复旧终端当作新沙箱。
实际验收 Claude 回答与工具调用、日本出口、普通账户不能借用受控入口、私钥不可读、readlink /etc/localtime 被拒绝、date 为 JST/+0900、普通账户保留系统时区、退格键和 TUI 正常。GUI 授权不足明确等待人工，未完成不能称为可用。
安装仓库共享组件。先询问我要共享的具体仓库路径及 Agent 提交姓名/邮箱；不要自动扫描或开放 Home，也不要设置 safe.directory=*。默认仅 Git 已跟踪文件共享，提供 share-repo --refresh 一键刷新；保留 ignored、.env、SSH/GPG 凭据排除。优先 /Users/Shared 专用目录；如果需要 Home 父目录遍历，先说明影响再获取授权，不要擅自加 --allow-home-traverse。
仓库选择可用 --share-repo 与 --git-name/--git-email；导入访问包继续安装时也要重复传入这些参数。没有提供项目时，只安装工具并说明项目授权待完成。阅读包内 repo-sharing/README.md，使用临时仓库验证双方读写/提交，禁止对用户项目做试验提交。旧版用 install_repo_sharing.py 单组件升级，不重装、不改 UID/Key/网络。
不要执行 git push。交付版本、设备 ID、无秘密路径、真实验收结果、启动方法及诊断/回滚说明。
```
