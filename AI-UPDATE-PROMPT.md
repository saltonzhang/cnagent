# 已安装 CN 增量配置更新提示词（v3.2.3）

在普通管理员账户中执行，不从非管理员 cnagent shell 尝试提权：

```text
这台 CN 已有 v3 受管理安装，请按 https://github.com/saltonzhang/cnagent/releases/tag/v3.2.3 对齐 162 当前配置，不要重装或重跑初始化。
下载 CN-MAC-JST-UPDATE.zip 和同版 SHA256，校验后解压到独立目录，再校验 MANIFEST.sha256，阅读 README.md 和适用 AGENTS.md。这个小包同时含 set_agent_timezone.py、set_agent_defaults.py。
用本机已安装的 Python 3.14 和 sudo，分别不带 --apply 运行两个工具预览；确认设备、账户和中央组匹配后，再分别加 --apply。
目标：受控默认 TZ=Asia/Tokyo 并拒绝 localtime 文件查询；Claude 默认 model=sonnet，Sonnet/Opus/Haiku 三个默认别名都指向 remote-magpie/group/cn-default。不强制 effort、不隐藏菜单、不新增服务端模型白名单。
保留系统时区、语言、证书、Key、额度、权限、effort、代理、其他供应商及已使用同一组时的登记申请。不要 SSH 登录 JP、不重签接入包、不升级 Claude、不替换正在运行的 Magpie。小更新只改配置，不代表前端二进制已升级；需要软件升级时单独准备备份与本机切换窗口。
无安装记录、账户变化、路由不匹配或自定义环境冲突时停止调查，不能伪造安装记录。162 历史试点已处于此状态，不重复套用通用工具。
保存两个备份路径，分别提供对应工具的 --rollback 预览/--apply 命令；后续配置变化时不得强行覆盖。
退出旧 Claude 和旧父 shell，从普通账户执行 sudo "/Library/Application Support/CN-Agent-Egress/launch" shell，再新开 Claude 会话。实际确认 id 为 cnagent，readlink /etc/localtime 失败，date 显示 JST/+0900，普通账户时区不变；确认三个默认别名都映射同一 JP 组。
旧历史中的已读时区不会被清除。这只保护已验证的文件入口，不保证隐藏所有本机元数据。未验证的项目如实列出，不能把旧会话仍然记得上海当作文件访问成功。
```
