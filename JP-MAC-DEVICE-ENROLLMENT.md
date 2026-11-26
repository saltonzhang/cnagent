# JP MAC 管理员：签发 CN 设备接入包

版本 3.2.1 · 2026-11-26。此流程仅由管理员在 JP 本机运行，或从管理员自己的可信管理电脑操作 JP；不让新 CN SSH 登录 JP，不向 CN 分发 JP 登录账号、密码或 SSH Key。

## 给 JP 管理 AI 的指令

> 按本手册处理指定 CN 的登记申请，只使用当前 JP 已有 CA、固定核心和 mTLS 服务，确认申请来源及设备 ID 后，要求管理员明确日/周/月额度或批准不限额；设置并核验独立设备 Key 的限额成功后才签发接入包。不得擅自决定额度。不要重建 CA、替换网关、重启服务或更改其他设备。不要输出 Key/私钥/接入包正文。返回接入包文件路径和无秘密状态，使用受控文件渠道交付。

复制并解压 `JP-MAC-ENROLLMENT-ADMIN-KIT.zip` 到 JP 的管理员私有目录；无需安装 CN 的软件和守护程序。使用 JP 现有 Python 3（3.8+），先读取适用的 AGENTS.md。检查管理员包清单及受信任来源，不执行 CN 提供的程序，只读取 `.request.json` 数据文件。

## JP 统一模型入口

新 CN 默认申请 `group/cn-default`，实际模型由 JP 当前组配置决定，最近核对为 Sonnet 5.5；不得为安装新 CN 改回旧示例的 Opus。在批准新申请前运行 `python3 admin/central_model.py` 确认组存在。需要切换时先运行 `python3 admin/central_model.py --model <实际模型ID>` 预览，再加 `--apply` 修改；程序备份完整 providers.json，仅改此组，不重启 JP。所有使用该入口的 CN 在后续请求使用新目标，无需改 CN 的实际模型名。

旧申请仍绑定旧模型，不应篡改申请或已签名接入包；已有 v3 CN 可按 CN 手册运行一次本地迁移工具。管理员 Key 若有模型限制，需要明确允许 `group/cn-default`，不能通过扩大到所有模型绕过授权；新签发工具保留当前 Key 策略。

## 1. 检查申请，不做任何登记

```bash
cd /实际解压目录/jp-admin-kit
/usr/bin/shasum -a 256 -c MANIFEST.sha256
python3 admin/issue_access.py \
  --request /绝对路径/设备.request.json \
  --out /管理员私有目录/设备.access.json
```

没有 `--approve` 时只显示设备 ID、CSR 摘要和路由，不签证书、不创建 Key。通过可信管理渠道确认设备归属及摘要，不能把“文件里写着这个 ID”当成身份证明。

签发器检查当前管理员 Home 下的：

- `ai/cn-agent-egress-pilot/wg-private/`：已有 CA/允许序列号。
- `Library/LaunchAgents/local.cn-agent-wireguard.api.plist` 与 `.egress.plist`：已有端口/允许列表路径。
- `ai/magpie-migration/magpie-prompt-translator/.runtime/cutover/deployment.json`：固定核心、SHA 和 configDir。

CA 必须与安装包内固定公共 CA 一致，核心 SHA 必须正确；路径/证书变更会拒绝，不能初始化一个新 CA 或清空记录“修复”。

## 2. 默认：接入包自动带 Key，CN 无需手填

确认设备与额度后运行（下面的 1000000 仅为语法示例，必须替换为管理员实际批准的数额）：

```bash
python3 admin/issue_access.py \
  --request /绝对路径/设备.request.json \
  --out /管理员私有目录/设备.access.json \
  --approve --period day --tokens 1000000 --cache-reads
```

这会增量登记本设备、签发客户端证书、创建/复用独立 Magpie Gateway Key，设置并核验批准的额度后才生成交付包。省略额度（除非明确 `--unlimited`）、设置失败或核验不符均不交付接入包。接入包绑定申请/CSR/随机数/路由，默认 48 小时内导入。可用 `--valid-hours 1..168` 显式设置有效期。客户端证书默认 90 天，接入包导入时效不是证书或 Key 的有效期。

包由独立 CA:false、codeSigning 身份签名。首次签发会在 JP 私有 CA 目录生成专用签名密钥与证书，不注册为可访问模型/代理的客户端，不重启任何 JP 服务。它们仅用于签名接入包，私钥不能复制到 CN。管理员包只包含公开 CA 和程序，不含任何现成私钥/Key。

把 `.access.json` 通过管理员认可的安全文件渠道交给对应 CN。**文件含该设备 Gateway Key，签名不等于加密，Base64 不是加密；不得贴到 AI 聊天或公共共享位置。** CN 导入命令：

```bash
bash install.sh --access-bundle /绝对路径/设备.access.json
```

CN 自动配置 Key 并验收；全过程不接触 JP 登录凭据。程序 stdout 只显示路径、状态和是否包含 Key，不显示秘密。CSR 和 CA 公共证书不是登录凭据；客户端私钥只在 CN 现场生成，接入包不能替代该私钥，不能拿给另一台电脑使用。

## 3. 可选：用户在 CN 私密输入 Key

如果不希望 Key 在接入包里携带：

```bash
python3 admin/issue_access.py \
  --request /绝对路径/设备.request.json \
  --out /管理员私有目录/设备.access.json \
  --approve --period day --tokens 1000000 --cache-reads --omit-api-key
```

此包仍包含必需的设备证书和签名，但不含 Key。管理员通过受控密码管理器/私密通道交付本设备 Key。JP 的 root/管理员私有记录 `wg-private/fleet-delivery/<device_id>.json` 保存对应 Key 和 ID；不要让 AI `cat` 到终端/聊天。需要查看/交付时只在管理员自己的安全界面或程序内处理，不显示其他设备信息。

CN 导入时先验证签名、设备绑定和时效，再提示隐藏输入 Key。没有安全交互终端时必须暂停，不能改成聊天提问、命令行参数、环境变量或写入公共配置。即使手动填 Key，也不能省略设备证书或放开门禁。

## 4. 幂等、错误和维护

- 相同设备、同 CSR、同申请的已有有效输出可复用，不重复创建 Key。
- 申请默认 7 天内处理；超期回 CN 重新运行安装器生成新随机数。过期接入包需管理员生成新的输出文件，不能在 CN 修改时间。
- 不同 CSR、撤销身份、同名但无交付记录的 Key、损坏登记记录：明确拒绝，管理员调查，不能删其他设备/Key 或复制试点私钥。
- 签名身份约 90 天；接近到期或不完整时会停止签发，需管理员准备签名身份轮换。当前无自动续签承诺；此身份轮换与模型运行时无关，不需要替换 CA 或重启网关。
- CA/签名私钥与交付记录仅管理员可读；含 Key 输出文件 0600。默认不覆盖已有不同/过期/错误模式输出，换新文件名重签，保留审计依据。
- 撤销本设备时，在 JP 执行 `issue_client.py revoke --ca-dir <核实目录> --device-id <设备ID>`，再用固定核心删除交付记录里的准确 `gateway_key_id`。不删除整个 Key 列表。已建立的长连接可能需另行协调断开。
- 这不是自助注册 API；不会开放远程管理端口。仅凭 Generic 安装包或陌生 CSR 不能自动获得 JP 使用权限。

## 验证边界

新版签名/导入流程以临时 CA、真实 CSR/客户端证书和签名验签完成隔离测试；Gateway Key CLI 在隔离环境模拟。没有在生产 JP 签发测试身份或重启服务，也没有在第二台空白 CN 执行完整安装。最终以新 CN 实际 mTLS、Claude 工具、日本出口和普通账户拒绝验收为准，不能用单元测试冒充生产验证。


## v3.2.0：额度选择、查看和调整

首次签发，先不加 `--approve` 预览设备与管理员选择的额度：

```bash
python3 admin/issue_access.py --request /绝对路径/设备.request.json --out /管理员私有目录/设备.access.json --period month --tokens 10000000 --cache-reads
# 数额仅为示例；确认后在同一命令末尾加 --approve。
```

可选 `--cost 20` 为预估 USD 上限，不能当作 Claude 订阅真实扣费或剩余百分比；未知价格不能可靠按金额计量。`--cache-reads` 表示 Token 统计也包含缓存读取。例外批准不限额必须显式 `--unlimited`，与周期、Token、金额参数互斥。

已有设备只查看状态和当前周期消耗（不显示 Key）：

```bash
python3 admin/manage_budget.py --device-id <设备ID>
```

调整额度先预览，再应用（数额仅为示例）：

```bash
python3 admin/manage_budget.py --device-id <设备ID> --period month --tokens 10000000 --cache-reads
python3 admin/manage_budget.py --device-id <设备ID> --period month --tokens 10000000 --cache-reads --apply
```

工具使用部署记录中的固定核心与受控 `configDir`，只操作该设备的准确 Key ID；核验其他设备未改变后同步私密交付记录。应用前保存限额快照，路径输出但不输出 Key；不重启服务，不重签证书。
多条/按模型限制需管理员单独审查，工具不会静默清除。恢复时以快照中的原周期/数额预览再应用，不能覆盖整份 caller-keys.json 或回滚其他设备。`--unlimited --apply` 只限管理员明确批准取消额度时使用。

重复签发同一策略不调用重置；改变策略需先用管理工具明确应用，再用新输出文件签发。旧接入包仍绑定原设备/申请，后端额度以 JP 当前设置为准，CN 不能自行更改。更改周期可能改变用量窗口；限额周期使用 JP 本机时区。
超额请求在受控网关返回 429，预先阻止转发；在途请求按实际用量结算，可能少量超过上限。额度按独立 Key 统计，当前证书/Key 未实现严格一对一绑定，禁止共享设备 Key。

v3.2.0 的真实核心测试使用独立临时 HOME、假设备 Key 和模拟 HTTP 上游，验证设备分别计量、超额不转发、另一设备不受影响、重启保留、过往日窗口不占当天额度、管理员预览不修改及单设备调整。不会据此声称已在新 CN 完成系统安装或 20 人并发压测；本次没有签发生产身份或修改现有设备额度。

## v3.2.1 兼容说明

新增 CN 默认日本时区和旧 CN 的启动器小更新包；JP 签发协议和额度工具未改变，现有 v3.2.0 管理员工具仍兼容，不需要为时区重启 JP、重签证书或重新分配 Key/额度。
