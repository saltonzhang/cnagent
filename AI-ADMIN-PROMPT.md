# 给 JP 管理 AI 的提示词（v3.2.0）

仅在 JP 本机或指定可信管理电脑执行，不能发给普通新 CN：

```text
请使用 https://github.com/saltonzhang/cnagent/releases/tag/v3.2.0 的 JP-MAC-ENROLLMENT-ADMIN-KIT.zip 和同版校验文件，校验并阅读 JP-MAC-DEVICE-ENROLLMENT.md 及适用 AGENTS.md。
处理我提供的设备 .request.json，先验证来源和设备 ID，然后询问我该设备的额度周期（日/周/月）、Token 上限、是否包含缓存读取；金额仅为可选预估 USD 上限。没有我明确选择，不签发、不默认不限额。只有我明确批准不限额才使用 --unlimited。
先预览，确认后用 --approve，为设备创建独立 Gateway Key、设置并核验限额成功后才交付签名 .access.json。失败时不交付。默认 Key 随包自动配置，不需要另外在官方 App 新建 Key。
必须操作部署记录中的 JP 受控实例，保留现有 CA、核心、其他设备、模型组、翻译门禁和开关；不重启服务，不使用上游共享服务 Key 代替设备 Key。
不打印 Key、私钥或接入包正文。只返回设备 ID、额度、Key ID 和接入包文件路径，通过我认可的私密文件渠道交付。
重复签发不要重置用量。已有设备调整额度使用 admin/manage_budget.py 先预览后 --apply；额度异常或漂移先报告，不自动改成不限额。不要创建生产测试身份或执行 git push。
```
