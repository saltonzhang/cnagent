# 给新 CN Mac 安装 AI 的提示词（v3.2.0）

把下面内容交给有本机终端权限的 AI：

```text
请实际安装本机的受控 Claude 环境，按 https://github.com/saltonzhang/cnagent/releases/tag/v3.2.0 下载 CN-MAC-AI-DEPLOYMENT-KIT.zip 和同版 SHA256 文件，校验后阅读包内 CN-MAC-AI-DEPLOYMENT.md 及适用 AGENTS.md，安装所有必需软件并完成真实验收，不要只给方案。
复用现有办公室 WireGuard 和 JP 10.9.8.30；不要覆盖个人 Magpie/Claude、已有试点或修改 JP 模型组、翻译、门禁、审计和开关。主对话使用 JP 统一入口 remote-magpie/group/cn-default，实际模型由 JP 管理员决定。
先生成本设备 .request.json，告诉我文件路径，等待管理员确认设备、设置并核验独立 Key 的额度后交付 .access.json；拿到文件后继续导入安装。不替管理员决定额度，不默认不限额，不使用他人 Key。等待授权不能报告安装完成。
新 CN 不得 SSH 登录 JP、索取 JP 管理凭据或复制其他设备私钥。API Key 默认随接入包自动配置；若省略，只让我在本机隐藏输入，不发到聊天。接入包含秘密，不打印或上传仓库。
验收专用 cnagent/iTerm JP Agent、真实 Claude 回答和工具、日本出口、无法代理时禁止国内直连、普通终端/VS Code 无法借用受控入口、私钥不可读及退格键正常；GUI 权限不足请明确等待人工验收。
不要执行 git push、改变网络放行范围或关闭门禁。超额 429 要报告管理员，不通过换 Key 或路由绕过。只有全部必需验收通过才报告可用，并交付启动、诊断、回滚说明。
本版 Claude 仍为已锁定基线；不要擅自启用尚未发布的新版分类修复或升级软件。
```
