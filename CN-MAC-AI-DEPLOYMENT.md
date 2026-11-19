# CN MAC 安装部署手册：交给 AI 执行

手册/发行版 3.1.0（JP 统一模型入口）· 2026-11-18。配套：同版本 `CN-MAC-AI-DEPLOYMENT-KIT.zip`；另有仅交给 JP 管理员的 `JP-MAC-ENROLLMENT-ADMIN-KIT.zip`。

## 直接交给另一台电脑的 AI

新 CN 不必先手动复制安装包。把下面这段指令发给有本机终端权限的 AI，它应先从 GitHub 读取本手册，再下载同版 Release。已复制文件的离线方式仍可使用。

> 从 https://github.com/saltonzhang/cnagent/blob/main/CN-MAC-AI-DEPLOYMENT.md 读取手册，下载并校验 v3.1.0 的 CN-MAC-AI-DEPLOYMENT-KIT.zip（不要误用 JP 管理员工具包），根据这份手册帮我安装并配置好整套受控 Claude 环境，包括缺失的软件。实际执行，不要只解释方案。复用现有办公室 WireGuard 和 JP MAC。先读手册，验证安装包，再运行安装入口并完成实际验收。不要覆盖已有试点或修改 JP 的翻译、门禁、审计及两个开关。只在需要时进行本机管理员认证。CN 不得 SSH 登录 JP、索取 JP 登录凭据或配置 JP 登录密钥。先生成登记申请交给管理员；拿到签名接入包后继续安装。API Key 默认由接入包自动配置，若管理员选择不随包交付，则通过本机隐藏输入填写，不贴到聊天。只有所有必需验收通过后才告诉我可以使用。

执行 AI 需要有这台 CN MAC 的终端执行权限；只有聊天能力不能安装。软件已随包携带，不要求新电脑预先安装 Homebrew、Node 或 Python。CN 只需要本机管理员授权；JP 的管理认证仅发生在管理员自己的电脑或 JP 本机，不能在新 CN 上进行。设备授权仍需要管理员审批：CN 先生成申请，管理员在 JP 签发接入包，CN 导入后继续。因此这是可恢复的两阶段安装，不是无需任何授权的自助入网。**包内不含任何密码、设备私钥、JP CA 私钥或 Gateway Key。**

本包以当前已验证的 Claude 工作流为目标。Codex 工具链曾与外层沙箱不兼容，普通 VS Code 的 Claude 不属于受控入口；不要把它们包装成已支持。无需安装 Docker、Little Snitch、Clash、Tailscale、Sub2API 或每机 WireGuard 客户端。它们不是这套当前方案的依赖，也不重装或卸载用户已有的软件。

## JP 统一管理模型（v3.1.0）

新 CN 的默认模型为 `remote-magpie/group/cn-default`，CN Magpie 的远程模型入口为 `group/cn-default`。JP 端该组默认只有 `claude/claude-opus-5-5`，失败不会回退到 Codex。今后只改 JP 的组成员，CN 不需要逐台改实际模型 ID；设备账号、证书、Key、翻译和门禁策略保持原有配置。

管理员仅在 JP 本机（或指定管理 CN SSH 到 JP）运行：

```bash
python3 admin/central_model.py
python3 admin/central_model.py --model claude/claude-opus-5-5
python3 admin/central_model.py --model claude/claude-opus-5-5 --apply
```

前两条只检查，`--apply` 才修改。工具验证固定核心与实际模型 ID，备份 providers.json，只改 cn-default 组，不重启服务。以后可替换 `--model` 为 JP 实际可调用的模型 ID。已开始的请求/旧 Claude 会话可能仍有自身上下文和粘滞状态，切换后用新会话验收。首次新建组的回滚为使用固定核心、正确 XDG_CONFIG_HOME 执行 `group rm cn-default`；已有组修改则根据工具备份恢复该组原成员，不能覆盖其他供应商或并发修改。

### 已安装 CN 一次性迁移

下载/校验/解压本版安装包，但不要为迁移重装账户或运行首次初始化。仅对有 v3 安装记录的 CN，在本机管理员终端运行：

```bash
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14   /绝对解压路径/fleet-kit/setup/use_central_model.py
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14   /绝对解压路径/fleet-kit/setup/use_central_model.py --apply
```

默认只预览；`--apply` 保留原 Key、证书、地址、其他供应商和 Claude 权限，仅增加远程组、切换默认模型并同步本机安装记录和下一次登记申请。它不重启服务，结束后新开受控 Claude 会话验收。备份路径会输出，必要时用同脚本 `--rollback /完整备份目录` 恢复原四个文件，并新开会话。不要重新导入旧模型路由的接入包；确需重新签发时使用迁移后生成的申请。

历史首台试点没有 v3 安装记录时，脚本明确拒绝接管，不能删除目录绕过；需管理员单独核实并迁移，不能宣称所有旧 CN 已自动切换。本次未远程重启或批量迁移已有 CN。

## 1. 安装后是什么样

- iTerm2 中新增 **JP Agent (WireGuard)** Profile。从这里进入专用非管理员账户，运行原生 `claude`。
- 模型：受控 Claude → 本机独立 Magpie → mTLS → 现有 WireGuard → JP Magpie → 原上游。
- curl 等 HTTP/HTTPS 工具：本机出口适配器 → mTLS → 现有 WireGuard → JP 公网出口。正常请求走日本；无法代理或被拒绝时不能回退国内直连。
- 普通账户的终端和普通 VS Code 不能借用受控本机端口，也不能通过 JP 原 3425 入口调用模型。它们其他上网行为保持原样。
- Agent 与持有客户端私钥的网络账户分离。每台新机器现场生成自己的私钥，JP 只接收 CSR，签发该设备证书并创建该设备 Gateway Key。
- JP 翻译、严格历史/中文工具结果门禁、审计及两个管理开关继续使用 JP 现有配置；安装 CN 不改变开关状态，也不开放审计管理端口。

默认 JP `10.9.8.30`：模型 mTLS 43425，工具出口 mTLS 43480。CN 默认回环端口 3435、44337、18190。办公室路由器上的 WireGuard 已经存在；新 CN 安装器不调用 SSH，也不获得 JP 登录权限。**没有每机 SSH 数据隧道，也没有开放自助登记服务。** JP 本机或管理员既有管理电脑负责签发。

## 2. 随包软件与文件

| 软件 | 随包版本/方式 | 安装策略 |
|---|---|---|
| iTerm2 | 3.7.7，官方签名通用 App | 已有签名正确的 iTerm 时复用；缺失时安装。只加独立 Profile，不安装 Claude 集成、不重置用户偏好 |
| Claude Code | 2.1.198，官方 npm 平台包中的签名原生程序，arm64/x64 | 安装到专用账户 `.local/bin/claude`；不依赖 Node，不复制普通账户历史或登录凭证 |
| Magpie | 0.1.3032，官方 arm64/Intel App | 独立安装到本工具的 root 管理目录，使用专用账户配置；不覆盖用户的 `/Applications/magpie.app` |
| Python | 3.14.10，Python.org 签名通用 PKG | 缺少受信任的 3.14 Framework 时自动安装，供安装器和守护程序使用 |
| 出口适配器 | 本套已验证 Go 程序，两个架构 | 直接安装随包二进制，不在新电脑安装 Go 编译器 |
| PF、sandbox-exec、launchd、curl、zsh | macOS 自带 | 检查可用性；不下载替代系统组件 |

Magpie/Claude 固定为试点兼容基线，不是“自动追最新”。升级需要重新验收，不能因为官网版本较新就擅自替换 JP 自定义核心。Python PKG 会使用其官方 Framework 安装方式，可能同时添加官方命令链接与 Python 应用目录；不安装完整 Xcode/CLT 来获取 Python。

包结构：

```text
CN-MAC-AI-DEPLOYMENT.md
fleet-kit/
  install.sh                    # 无 Python 前置依赖的入口
  setup/install.py              # CN 本机安装、导出申请、导入接入包、验收
  setup/root_install.py         # 本机管理员安装/状态/停止
  enrollment.py                 # 签名、时效、设备绑定校验
  trust/jp-ca.pem               # 固定的 JP 公共 CA，不含私钥
  setup/accept.py               # 新 CN 的实际链路验收
  software/                    # 所有上述第三方安装文件及 LOCK.json
  bin/                         # arm64/amd64 出口程序
  templates/                   # 受控运行时、PF、启动器等
  render.py                    # 公共配置渲染
  admin/issue_access.py        # 仅 JP 管理员运行的签发工具（无登录凭据）
  MANIFEST.sha256 / VALIDATION.json
```

软件来源与上游完整性记录在 `software/LOCK.json`。iTerm、Magpie 和 Claude 在安装时检查代码签名，Python 安装前检查包签名。清单校验用于发现损坏，不能代替安装包来源可信性；从管理员提供的原始 ZIP 复制，不能拿陌生人修改过的清单当信任根。

## 3. AI 必须先调查

1. 读取适用的 `AGENTS.md`。确认正在操作目标 CN，而不是 JP 或原试点。
2. 查询 macOS 版本、CPU、普通用户名/Home、管理员权限、磁盘空间、现有软件与监听端口。建议 macOS 26.3 arm64 同试点；其他版本/Intel 必须实机验收，不能照抄试点结果。
3. 确认办公室 WireGuard 路由能到 JP，且没有其他 VPN 抢路由。此前“EOF/Empty reply”就是 VPN 冲突，不能靠放宽安全规则解决。
4. CN 只检查实际模型/工具内网路径，不测试 JP SSH 登录，不索取 JP 用户名、密码或 SSH Key。由管理员用独立渠道确认 JP 可登记；管理员工具只在 JP 本机运行。不要让普通员工把 JP 管理凭据输入新 CN。
5. 如果目标存在 `/Library/Application Support/CN-Agent-Egress`，安装器只允许恢复自己 v2/v3 的同设备安装记录。已有试点/他人安装会明确拒绝，**不能删除目录或账号来绕过**。
6. 默认独立账号 `cnagent` / `cnagentnet`、独立 Home。若同名账号已存在且无本安装器记录，停止调查；不能重置用户密码、改 UID 或递归覆盖其 Home。
7. 安装前预留约 3 GB 可用空间。不要关闭执行 AI 自己唯一可用的管理链路。

## 4. 实际安装入口

在新 CN 的普通管理员账户执行。优先使用以下固定版本下载，安装包与校验文件必须来自同一个 Release；不要混用 main 分支的未来手册与旧版本包。新 CN 必须能访问 GitHub 下载地址，网络失败时报告并由管理员提供已校验副本，不擅自改变 VPN/路由或索取 JP 登录凭据。

```bash
mkdir -p ~/Downloads/cnagent-v3.1.0
cd ~/Downloads/cnagent-v3.1.0
curl -fL --retry 3 https://github.com/saltonzhang/cnagent/releases/download/v3.1.0/CN-MAC-AI-DEPLOYMENT-KIT.zip -o CN-MAC-AI-DEPLOYMENT-KIT.zip
curl -fL --retry 3 https://github.com/saltonzhang/cnagent/releases/download/v3.1.0/CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256 -o CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256
shasum -a 256 -c CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256
unzip CN-MAC-AI-DEPLOYMENT-KIT.zip -d installer
cd installer/fleet-kit
shasum -a 256 -c MANIFEST.sha256
bash install.sh --plan
bash install.sh
```

逐步执行，每步必须成功才继续；校验失败禁止解压执行。若 `installer` 目录已存在，先确认其归属，不覆盖用户已有目录或重复解压混合版本。读取包内同版手册，与 Release 附件手册应一致。GitHub 校验文件用于检查损坏，仓库来源和授权仍需可信。

也可由管理员复制同版 ZIP、校验文件和手册到新 CN；离线安装的软件内容齐全，但实际接入/验收仍需要办公室内网和 JP 服务。解压后保留 MD、`fleet-kit/` 同级，再检查包内清单并执行：

```bash
cd /实际解压目录/fleet-kit
/usr/bin/shasum -a 256 -c MANIFEST.sha256
/bin/bash install.sh --plan
/bin/bash install.sh
```

`--plan` 不安装。若 Python 尚缺失，只显示下一步计划；真正安装时会自动安装随包 Python，然后继续执行 Python 协调器。不要 `sudo bash install.sh`，否则会错误识别日常操作者；入口会在需要的步骤申请本机 sudo。

默认会从本机硬件 UUID 的 SHA-256 生成稳定设备 ID，如 `cn-xxxxxxxxxxxxxxxx`，不披露原 UUID，也不复用其他设备 ID。第一次运行完成本机准备后，会返回：

```text
status: awaiting_admin_access_bundle
installation_complete: false
request_file: ~/Downloads/CN-Agent-Enrollment/<device_id>.request.json
```

把 **request.json 文件**交给管理员，而不是给 CN 一个 JP 登录密码。申请包含公开 CSR、设备 ID、请求随机数、目标路由与 CA 摘要；不含客户端私钥、API Key、JP 密码。申请文件仍需经可信渠道交付，管理员必须确认确实来自指定设备，不能自动批准陌生 CSR。

管理员按照 [JP 设备登记手册](JP-MAC-DEVICE-ENROLLMENT.md) 在 JP 本机签发 `<device_id>.access.json`，再通过受控文件渠道交付给该 CN。CN 端 AI 收到文件后继续：

```bash
/bin/bash install.sh --access-bundle /绝对路径/设备.access.json
```

默认接入包携带本设备 Gateway Key，**自动写入配置，不需要用户手填**。接入包是签名文件，签名保证来源与完整性，**不是加密文件；Base64 也不是加密**。含 Key 的包必须通过管理员认可的安全渠道传输，不发到聊天、公共网盘或共享仓库，导入后妥善清理分发副本。

如果管理员用 `--omit-api-key` 签发不含 Key 的包，CN 导入并校验签名成功后，才会在交互终端显示：

```text
输入管理员提供的本设备 Magpie Gateway Key（隐藏输入）：
```

此时才需要用户自己填 Key，不回显、不接收命令参数/环境变量、不写进手册或 AI 聊天。若 AI 的执行工具没有安全交互终端，停在这里，请用户在本机终端完成；不得把 Key 当普通文字提问。**单独填 Key 不够，仍需匹配本机私钥的有效接入包和设备证书。**

接入包绑定本机 root 保存的登记申请、CSR、随机数、路由，默认 48 小时内导入；错误设备、内容篡改、过期、假 CA 或普通客户端证书伪造签名均拒绝。CN 使用包内固定的 JP 公共 CA 验证，不信任接入包自带的任意 CA。完成导入后的正常重试可使用 root 已接受的本机配置，无需每次重签。

特殊本机端口/账号参数可由 AI 复制 `deployment.example.json` 并填写公开配置，再运行 `bash install.sh --config /绝对路径/deployment.cn.json`。接续导入时仍需传入同一配置。配置不能放 Key。`python_binary` 由实际解释器覆盖，`enable_codex` 保持 false。当前签发格式固定 JP `10.9.8.30:43425/43480`；若服务地址或 CA 变更，需要管理员发布新的可信安装包，不能自动接纳 CN 自选的新信任根。

## 5. 安装器做的工作

1. 校验所有软件文件；缺少/损坏就停止，不执行下载到一半的包。
2. 安装/复用 root 管理的 Python，复制受信任工具包到 `/Library/Application Support/CN-Agent-Installer-v3`，不把 Downloads 文件作为守护程序的长期执行路径。
3. 检查 PF 原根规则有 `com.apple/*` 锚点，检查新本机端口无冲突。若新机 PF 尚未启用且过滤根规则为空、系统默认配置仍含该锚点，仅加载这条过滤锚点，不清空 NAT/状态/其他策略；已有活动或非空的非标准根策略则停止调查。
4. 独立安装受控 Magpie，安装/复用 iTerm2；检查签名 Team ID。
5. 动态分配空闲 UID，创建两个隐藏、禁用密码、非管理员账户；不固定 501/502，不继承管理员组。
6. 安装 Claude 原生程序；配置独立 Magpie/Claude、专用工作目录和退格键。禁用该专用 Claude 的自动更新，后续按版本验收升级。
7. 在网络账户目录生成 RSA 客户端私钥和 CSR，私钥不离开 CN，不交给 Agent。
8. 导出公开登记申请并暂停。管理员将其送至 JP；JP 检查固定核心 SHA、现有 CA/实际 mTLS Job，锁定登记，保留其他设备序列号，签发该设备证书。CN 不登录 JP。
9. JP 为设备创建独立 Gateway Key，并用独立的 CA:false/codeSigning 身份签名接入包。CA 私钥只签 X.509 证书，不直接签接入包正文。签名私钥只保留在 JP。CN 以普通用户和 root 两层验证接入包；默认自动导入 Key，选择省略 Key 时才隐藏输入。
10. 安装 root-owned 启动器、监督程序、PF 子锚点和 seatbelt，启动本机专用 LaunchDaemon；不重启 JP，不改 JP 白名单和翻译配置。
11. 添加 iTerm 动态 Profile，并执行本机真实验收。任一必需验收失败，停止并报告，不能称为完成。

每阶段有 root-only 安装记录。相同设备/同 CSR/同参数可重试，已经签发的身份和 Key 会复用；不同 CSR、撤销身份或意外已存在的同名 Key 不会被静默覆盖。JP 登记在共享列表上加锁，保存原有设备。登记过程意外中断且状态不一致时要求管理员查明，不能删共享列表“重来”。同机同请求重复导入可恢复；跨机或另一随机数的重用拒绝。等待管理员签发是未完成状态，AI 不能把第一次返回 0 当成安装完成。

## 6. 必须完成的验收

安装器会执行并只输出状态，不输出秘密或模型私人内容：

- PF 开启，实际规则与监督程序记录一致。
- 普通账户和 Agent 均不能读取网络账户私钥。
- 普通 UID 访问三个本机受控端口失败，并验证对应 PF 阻挡计数增加、同端口受控 UID 连接成功；不能只用超时或 401 当作隔离成功。
- 受控环境不能直连原 JP 3425、其他本机代理、IPv6/UDP 回环和 DNS IPC。
- 受控 HTTP 代理请求 `https://ipinfo.io/json` 成功，国家为 JP；报告只含日本出口 IP 摘要，不打印国内真实 IP。
- 真实 Claude 通过现有 JP/上游返回 `OK`。
- 真实 Claude 运行固定 `printf CN_AGENT_TOOL_OK` Bash 工具任务：既检查实际 `tool_use` / `tool_result` 事件，也检查最终 DONE，不能只相信模型说“已执行”。
- 普通账户访问 JP 旧 3425 返回 403。

如果使用 `--no-public-check`，会跳过公网探测，但验收 `passed` 为 false，**只能算部分准备完成**，不能据此交付“出口已成功”。公网站点 429 不等于泄漏，应在 JP 本机和受控环境做对照，换固定公开探测站点时记录原因；不放开国内直连。

AI 还必须完成以下界面/人工交互验收，不能用单元测试替代：

1. 打开 iTerm2 并选择 **Profiles → JP Agent (WireGuard)**。必要时通过已授权 GUI/AppleScript 建立该 Profile 窗口；自动化权限弹窗由用户授权，不能偷偷改 TCC。
2. 进入后 `id -un` 应为专用 Agent 账户，运行 `claude`，不能是普通账户已有登录会话。Profile 的 sudo 可能要求日常管理员认证；本包不写 `NOPASSWD:ALL`。
3. 实际测试右上角 ⌫ 删除英文/中文字符正常、Claude TUI 正常；不安装 iTerm Claude Integration 作为修复。
4. 让受控 Claude 用 curl 查询公开 IP，确认日本出口；同时尝试绕过代理访问一个**自有的 JP 测试服务**，确认被阻断。不要为了负向测试真实访问会暴露国内 IP 的第三方公网查询站。
5. 普通终端和普通 VS Code 尝试同模型/本机受控入口应失败；VS Code 其他上网功能不受本包承诺约束。
6. 验证原有网络服务（例如 frpc 18080）、个人 Magpie、普通应用未被误停。检查没有新建 SSH 数据转发进程。

只有自动验收和本机交互验收都通过，AI 才能报告“这台可以使用”。若没有 GUI 权限，则明确列出尚待用户点击/验证的项目，不能把等待中的步骤算完成。

## 7. 日常使用与项目

在 iTerm2 选择 JP Agent Profile，输入 `claude`。原来在普通终端或普通 VS Code 启动的 Claude 被拒绝属于预期。这里真正的身份边界是账户/PF/mTLS，不是“iTerm”进程名称；启动入口需要管理员授权，普通用户不能仅伪造环境变量就获得证书。

专用目录 `/Users/cnagent/workspace` 默认是空的。AI 应在用户指定的项目范围内迁入工作副本或添加最小必要 ACL；**不要递归开放原整个 Home，不复制 `.ssh`、`.claude` 历史/登录、Keychain 或官方订阅凭证**。未知项目不能擅自授予访问。若用户暂未指定项目，先交付可用空工作区，明确原项目尚未授权。

工具出口只支持公开 HTTP/HTTPS 80/443；私网、回环、保留目标、其他端口和未适配协议会拒绝，不自动降级。Git SSH、私有 LAN Git/DB、远程 MCP 等需要另外适配和测试，不能临时放开所有端口。没有 Node 的新机也能运行此原生 Claude；具体项目的 Java/Go/Node 等编译工具链不属于网络工具包，按项目授权安装。

## 8. JP 翻译/门禁错误不能当网络故障处理

- `403 请使用受控终端 JP Agent (WireGuard)。`：旧入口/未受控身份，检查启动 Profile 和链路，不把 CN IP 加到 JP 白名单。
- `422 tool_result_contains_chinese`：JP 当前中文工具结果门禁主动拒绝；错误包含 input/call/行列/blocked。在管理员审计页定位，必要时**手动确认清理该条历史**。不能在新 CN 安装时关闭门禁。
- 旧会话可能持续带有相同中文工具结果，重试不会自动消除。新会话/手动清理需要按现行策略处理。
- `503 translation_not_verified`：查 JP 已有阶段诊断；以前已修复分类历史结构和长文本分段问题。不能为了接入新机改为 fail-open。
- `EOF` / `Empty reply`：先查国内其他 VPN、路由冲突、代理及 JP 实际监听，曾关闭冲突 VPN 后恢复；不能重建整个 WireGuard。
- curl 502/429：区分 JP 出口/DNS/站点限流；此前 DNS64 已在随包出口程序修复，JP 服务端继续用其现有修复版，不重新部署旧版本。

## 9. 诊断、重试和停止

本机私有状态：`/Library/Application Support/CN-Agent-Egress/private/`，包含 `installer-state.json`、`config.json`、脱敏 `acceptance.json`、服务日志。配置中有路径但没有 Key；Agent 的 `providers.json` 含该设备 Key，不能 `cat` 到聊天。

由 AI 用实际 Framework Python 执行：

```bash
# 安全重试（相同设备/参数）；尚未授权时仍暂停并导出申请，已导入时复用本机配置。
/bin/bash /实际解压目录/fleet-kit/install.sh

# 状态；config 是安装器保存的公开参数文件，root-only 权限。
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 \
  '/Library/Application Support/CN-Agent-Installer-v3/setup/root_install.py' status \
  --config '/Library/Application Support/CN-Agent-Egress/private/config.json'

# 重新做实际验收。
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 \
  '/Library/Application Support/CN-Agent-Installer-v3/setup/accept.py' \
  --config '/Library/Application Support/CN-Agent-Egress/private/config.json'

# 停止本机受控服务；保留账户、数据和限制，避免停止时开放直连。
sudo /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 \
  '/Library/Application Support/CN-Agent-Installer-v3/setup/root_install.py' stop \
  --config '/Library/Application Support/CN-Agent-Egress/private/config.json'
```

已有 v2 安装目录可保留并按原 CSR 重新生成/签发接入包；原历史试点不是本安装器创建的目录时仍拒绝接管，不得删除目录绕过。已正常运行的 CN 需要重启/升级时先协调本机窗口；本次安装授权不等于许可中断共享 JP。不要直接输出 daemon 原始日志；只取固定错误原因/状态，避免将用户请求或密钥贴到对话。

## 10. 回滚/卸载

安装器不会为你删除用户数据。失败后先停止上述本机 Job，再处理该设备 JP 登记。保持其他 CN 不受影响：

1. 仅在 JP 管理员环境执行管理员包中的 `issue_client.py revoke --ca-dir <已核实CA目录> --device-id <本设备ID>`，只撤销本设备序列号。已有 CONNECT/WS 长连接可能需单独协调断开。
2. 在 JP 保护程序中从 `fleet-delivery/<device_id>.json` **只读出 gateway_key_id**，调用当前固定核心 `gateway-key remove <id>`。不输出 `gateway_key`。不能按数组位置或删除整个 caller-keys.json。
3. 撤销/Key 删除不是自动“原路返回”，重新接入需要显式轮换身份，不复用被撤销 CSR。
4. 若要移除本机：先确认没有专用账户进程/待保存项目，再移除本包 LaunchDaemon、准确的 PF 子锚点、准确的动态 Profile。若有 `private/profile.before`，恢复它；不重置全部 iTerm/PF。
5. 账户/Home、网络私钥和项目目录的永久删除需明确授权；由安装记录确认 UID/Home，不能凭名字删其他用户。
6. 不自动卸载复用的 iTerm/Python/个人 Magpie。独立软件随工具目录处理；官方 PKG 的全局组件可能被其他程序使用，删除前调查。

本包提供的 `stop` 是可逆安全停用，不冒充完整破坏性卸载器。原试点已有但非本安装器管理的目录不可用本安装器接管或回滚。

## 11. 安全边界与当前验证状态

- 保证范围是当前受控账户及其子进程的网络策略，不是完整文件系统容器；公开可读文件仍可能被读取。root/管理员、物理访问、任意恶意 GUI 委托不在隔离承诺内。
- PF 监督程序每秒检查规则；规则异常停止服务，启动入口也检查。不能把它描述为抵御管理员主动关闭 PF 的原子安全系统。
- mTLS CA/序列号 + 每设备 Gateway Key 提供两层认证；证书与 Key 的服务器端一对一绑定尚未实现，不能宣称已实现。
- 证书默认 90 天，当前没有自动续签。到期前需要管理员轮换，不能延长旧证书无限期有效。
- sandbox-exec 为版本相关的旧机制，系统升级必须重新验收；Codex 工具/受控 VS Code 未纳入本版完整支持。
- `VALIDATION.json` 记录本包实际执行过的测试。本版在临时目录用真实 OpenSSL 验证签名接入包、证书/请求绑定、默认自动导入与可选隐藏输入，以及篡改/过期/错误证书拒绝；现有试点提供运行时真实验证依据。**没有在第二台空白 CN 上执行完整系统安装，不能把该事实改写为“所有新机已经验证”。**因此每台安装入口强制真实验收，执行 AI 还须完成界面验收。

CN 不再有任何自动 SSH 登录 JP 的步骤，也不增加 JP 用户或 SSH Key。这是移除管理凭据/登录需求，不是修改 JP 22 端口的网络 ACL；若另需端口网络层不可达，应单独准备网关/服务器规则并协调变更。

交付时输出：设备 ID、版本、无秘密路径、各验收结果、Profile 使用方式、尚未授权的项目/未完成项、停止/回滚入口。不得输出认证信息或声称跳过的步骤完成。不需要做人数规划或并发评估，本手册专注于把当前整套环境装到这台新 CN。

官方来源：[iTerm2](https://iterm2.com/downloads.html)、[Magpie 官方发布](https://github.com/yetone/magpie-releases/releases/tag/v0.1.3032)、[Claude 安装说明](https://code.claude.com/docs/en/setup)、[Python 3.14.10](https://www.python.org/downloads/release/python-31410/)。

## v3.0.2 安装权限修复与验证范围

v3.0.1 在严格 umask 下将受控运行目录创建为 root-only，并遗漏专用账户 `.local`、`.config` 父目录所有权，导致降权服务无法访问。v3.0.2 显式设置运行目录为 root-owned 0755、私有目录为 0700，并逐级设置专用账户目录为该账户所有的 0700；不递归修改既有数据。只对本安装器识别的同设备安装恢复，仍拒绝接管试点和同名未知账户。

已完成本机权限修复后的 PF、端口账户隔离、私钥读取限制、受控网络负向测试和日本出口验收；真实 Claude 回复和工具调用仍失败，原因待定位，iTerm2 界面/退格键验收仍未完成。本版本不宣称整套环境已经通过验收。回归测试覆盖 umask 077、新建/恢复、父目录服务 UID 所有权及符号链接拒绝；不替代目标机实际验收。

源码在 `fleet-kit/`；Git 仓库不包含大型软件和出口二进制，实际安装必须下载同版本完整 Release ZIP 并校验，不能直接运行不完整源码目录。旧 v3.0.1 附件保留供追溯，不覆盖。已安装设备请读取同版本手册后以原设备参数重跑安装入口恢复权限，并重新做全部验收；不要手动删除状态或重新生成身份。

上述为 v3.0.2 当时的目标机验收记录；v3.1.0 保留权限修复。本次验证 JP/隔离严格链路成功，不代表旧 CN 原操作已恢复，迁移后仍须实际验收。
