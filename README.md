# CNAGENT v3.2.1

受控 Claude、本机独立 Magpie 与 JP 网络出口。新 CN 不获得 JP SSH 管理权限。

- [新 CN 完整安装包](https://github.com/saltonzhang/cnagent/releases/download/v3.2.1/CN-MAC-AI-DEPLOYMENT-KIT.zip) · [SHA256](https://github.com/saltonzhang/cnagent/releases/download/v3.2.1/CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256)
- **已装 v3.1.1 / v3.2.0 无需重装**：[日本时区小更新包](https://github.com/saltonzhang/cnagent/releases/download/v3.2.1/CN-MAC-JST-UPDATE.zip) · [SHA256](https://github.com/saltonzhang/cnagent/releases/download/v3.2.1/CN-MAC-JST-UPDATE.zip.sha256) · [步骤与回滚](CN-MAC-JST-UPDATE-README.md)
- [新 CN 安装 AI 提示词](AI-INSTALL-PROMPT.md)
- [已安装 CN 增量更新 AI 提示词](AI-UPDATE-PROMPT.md)
- [管理 CN 签发与设置额度 AI 提示词](AI-ADMIN-PROMPT.md)
- [CN 完整手册](CN-MAC-AI-DEPLOYMENT.md) · [JP 管理手册](JP-MAC-DEVICE-ENROLLMENT.md) · [Release](https://github.com/saltonzhang/cnagent/releases/tag/v3.2.1)

新 CN：校验完整 Release ZIP → 安装依赖与独立账户 → 导出 request.json → 管理员确认设备及额度 → 签发 access.json → CN 导入并完成真实验收。不能直接从缺少软件/二进制的源码目录安装。

管理员使用[同版管理员 ZIP](https://github.com/saltonzhang/cnagent/releases/download/v3.2.1/JP-MAC-ENROLLMENT-ADMIN-KIT.zip)及[校验文件](https://github.com/saltonzhang/cnagent/releases/download/v3.2.1/JP-MAC-ENROLLMENT-ADMIN-KIT.zip.sha256)。额度工具 v3.2.0 与本版兼容，JP 不需要因时区变化重装、重启、重签或更改现有额度。

## 时区更新

新安装的受控启动器默认 TZ=Asia/Tokyo，date 显示 JST/UTC+09:00；系统时区与语言保持原样。已安装设备用小更新包中的 set_agent_timezone.py 先预览，再 --apply，不重跑完整安装器。只修改受控启动器的一处环境变量，不修改证书、Key、额度、模型、代理、PF 或服务配置。退出旧 Claude 和受控 shell，再从原入口打开生效。已生效时重复运行不修改；提供备份和冲突检测回滚。

通用更新只接管身份匹配的 v3 安装，拒绝未知/历史试点，不得伪造安装记录。162 试点已单独验证 JST/+0900、普通终端 +0800，无需重复更新。更新旧设备不修改保存的旧版安装器；以后完整恢复时使用 v3.2.1，避免旧 configure 恢复旧模板。

这是默认显示设置，不是阻止系统元数据读取。命令仍在 CN 执行，覆盖 TZ 或读取系统文件仍可能识别本机设置。

## 每设备额度

JP 签发必须明确 --period day|week|month 配合正数 --tokens/--cost，或管理员明确批准 --unlimited；省略额度、设置失败或核验失败不交付。Key/私钥/接入包正文不打印、不上传。重复签发不重置用量，调整用 admin/manage_budget.py 先预览再 --apply。

额度在 JP **受控实例**按独立 Key 统计；官方 App 的共享上游服务 Key 是另一层。在途请求可能超额，金额是估算，未知价格不能可靠按金额控制；证书/Key 尚未严格一对一绑定。无管理授权不得改变策略或共享其他设备 Key。

## 验证边界

63 项 Python 测试通过（新增 8 项时区增量测试）。此前当前 JP 核心的 8 项独立预算检查保留，结果见 [BUDGET-VALIDATION.json](BUDGET-VALIDATION.json)。这不是新 CN 的系统安装或 20 人压测。新机必须完成真实工具、日本出口、普通账户拒绝和界面验收。

随包软件基线不变，Claude 仍为 2.1.198；尚待确认的 2.1.302/Codex 分类修复未包含。普通 VS Code 和 Codex 工具链不宣称已支持。
