# 已安装 CN 的增量更新提示词（v3.2.2）

```text
这台 CN 已安装 v3.1.1 或 v3.2.0，请增量设置受控 Agent 默认日本时区，不要重装或重跑初始化。
从 https://github.com/saltonzhang/cnagent/releases/tag/v3.2.2 下载 CN-MAC-JST-UPDATE.zip 和同版 .sha256，校验后解压到独立目录，再校验包内 MANIFEST.sha256 并阅读 README.md、适用 AGENTS.md。
用本机已安装的 Python 3.14 和 sudo 运行 set_agent_timezone.py 预览。确认是身份匹配的 v3 受管理安装后再加 --apply；如无安装记录、账户变化或自定义环境冲突，请停止调查，不能删除状态、创建假记录或覆盖未知启动器。
将受控启动器默认 TZ 设为 Asia/Tokyo，并叠加 /etc/localtime 与 /private/etc/localtime 的 file-read* 拒绝规则，保留系统时区、语言、证书、Key、额度、模型、代理、门禁及其他服务。不 SSH 登录 JP，不重签接入包，不升级 Claude。
保存输出的备份路径。提醒我退出旧 Claude 和受控 shell，再从原 launch shell 入口打开，实际确认 date 显示 JST/+0900，而普通终端保持原时区；未实际验证的项目如实说明。
提供回滚命令；启动器有后续改动时不得强行覆盖。这是默认时间显示，不是禁止读取本机信息。
162 历史试点已单独设置好，无需重复应用；不能为了让通用工具通过而伪造试点安装记录。
```

验收补充：在新受控进程确认 readlink /etc/localtime 与 /private/etc/localtime 均失败、不返回目标，date 保持 JST；普通账户仍可读取原系统设置。必须新开会话复验，旧历史中已经暴露的时区不会自动消除。只声明已验证的入口，不能承诺彻底隐藏本机位置。
