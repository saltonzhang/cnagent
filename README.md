# CN Agent — 新 CN MAC 完整安装包 v3.1.0

在新 CN MAC 安装受控 Claude、Magpie、日本出口及依赖。新 CN 不需要 JP 的 SSH 账号、密码或登录密钥。

## 新 CN 下载

- **[完整安装包（约 338 MB，Apple Silicon + Intel）](https://github.com/saltonzhang/cnagent/releases/download/v3.1.0/CN-MAC-AI-DEPLOYMENT-KIT.zip)**
- [SHA-256 校验文件](https://github.com/saltonzhang/cnagent/releases/download/v3.1.0/CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256)
- **[给安装 AI 阅读的手册](CN-MAC-AI-DEPLOYMENT.md)**
- [版本下载页](https://github.com/saltonzhang/cnagent/releases/tag/v3.1.0)

包内含 iTerm2、Claude 原生程序、独立 Magpie、Python 和出口程序，无需预装 Node/Homebrew。固定兼容版本与适用范围见手册。Codex 工具及受控 VS Code 未完成适配，不宣称支持。

将下面的指令交给新 CN 的 AI：

> 根据仓库 CN-MAC-AI-DEPLOYMENT.md，下载 v3.1.0 完整 CN 安装包并核对校验值，安装所有依赖并生成设备申请。不要 SSH 登录 JP 或索取 JP 登录信息。等待管理员提供签名接入包后，导入并继续安装，完成实际链路和界面验收；不能把等待授权算作安装成功。密码和 Key 不要输出到聊天。

也可在新 CN 的普通管理员终端下载：

```bash
mkdir -p ~/Downloads/cnagent-v3
cd ~/Downloads/cnagent-v3
curl -fL https://github.com/saltonzhang/cnagent/releases/download/v3.1.0/CN-MAC-AI-DEPLOYMENT-KIT.zip -o CN-MAC-AI-DEPLOYMENT-KIT.zip
curl -fL https://github.com/saltonzhang/cnagent/releases/download/v3.1.0/CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256 -o CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256
shasum -a 256 -c CN-MAC-AI-DEPLOYMENT-KIT.zip.sha256
unzip CN-MAC-AI-DEPLOYMENT-KIT.zip -d installer
cd installer/fleet-kit
bash install.sh
```

第一次运行准备本机并生成申请文件，管理员签发后再运行 `bash install.sh --access-bundle /绝对路径/设备.access.json`。管理员默认将 Key 包含在接入包中，CN 自动配置；若省略 Key，则通过 CN 本机隐藏输入填写。不要把接入包或 Key 提交到仓库。

## 管理员签发

### 管理员工具下载

- [管理员工具包 ZIP](https://github.com/saltonzhang/cnagent/raw/refs/heads/main/JP-MAC-ENROLLMENT-ADMIN-KIT.zip)
- [SHA-256 校验文件](https://github.com/saltonzhang/cnagent/raw/refs/heads/main/JP-MAC-ENROLLMENT-ADMIN-KIT.zip.sha256)
- [完整签发手册](JP-MAC-DEVICE-ENROLLMENT.md)
- [对应源码](jp-admin-kit/)

管理员工具使用已有 JP 服务，不安装或替换 JP Magpie。完整 CN 安装包在上方 Release 下载。

## 最新流程

1. 新 CN 的安装 AI 生成 `.request.json`；私钥留在 CN。
2. 管理员确认申请来自指定设备。在 JP 本机运行签发工具；也可从**指定管理 CN**通过 SSH 到 JP 运行，普通 CN 不参与管理登录。
3. 工具自动签发证书、创建/复用本设备 Key，生成签名 `.access.json` 接入包。
4. 管理员将接入包安全交回对应 CN，CN 安装 AI 导入后继续安装和实际验收。

## 命令

在 JP 管理员环境下载、校验、解压：

```bash
curl -fL https://github.com/saltonzhang/cnagent/raw/refs/heads/main/JP-MAC-ENROLLMENT-ADMIN-KIT.zip -o JP-MAC-ENROLLMENT-ADMIN-KIT.zip
curl -fL https://github.com/saltonzhang/cnagent/raw/refs/heads/main/JP-MAC-ENROLLMENT-ADMIN-KIT.zip.sha256 -o JP-MAC-ENROLLMENT-ADMIN-KIT.zip.sha256
shasum -a 256 -c JP-MAC-ENROLLMENT-ADMIN-KIT.zip.sha256
unzip JP-MAC-ENROLLMENT-ADMIN-KIT.zip
cd jp-admin-kit
shasum -a 256 -c MANIFEST.sha256
```

先检查申请，不登记：

```bash
python3 admin/issue_access.py --request /绝对路径/设备.request.json --out /管理员私有目录/设备.access.json
```

确认设备和申请来源后签发：

```bash
python3 admin/issue_access.py --request /绝对路径/设备.request.json --out /管理员私有目录/设备.access.json --approve
```

默认接入包带本设备 Key，CN 自动配置，无需用户手填。若管理员增加 `--omit-api-key`，CN 在验证有效接入包后，通过本机隐藏输入提示填写 Key。Key 不能放进聊天、命令参数或公开配置。只有 Key 不足以替代设备证书。

## 边界

- 通用工具包只含程序、文档和固定的 JP **公共 CA**，不含密码、CA/客户端私钥或现成 Gateway Key；公共 CA 不是登录凭据。
- **不得上传真实 request/access 文件、私有交付记录、设备 Key 或私钥。** 接入包可能含 Key，签名不等于加密，Base64 也不是加密；必须通过受控渠道交付。
- 当前目标是现有 `10.9.8.30:43425/43480` 和匹配公共 CA。地址或 CA 变更需管理员重新发布可信版本，不自动接受新信任根。
- 接入包默认 48 小时内导入，证书默认 90 天；没有自动续签承诺。
- 46 项安装/登记隔离测试通过；签名和证书使用真实 OpenSSL，Gateway CLI 采用临时模拟。没有以此声称已在第二台空白 CN 完成系统级安装或在生产 JP 签发测试身份。
- 不重建 WireGuard，不建立 SSH 数据隧道，不修改 JP 翻译、门禁、审计和现有开关。具体前置条件、审批、撤销和维护见手册。

版本日期：2026-11-18。

## v3.0.2 安装权限修复与验证范围

v3.0.1 在严格 umask 下将受控运行目录创建为 root-only，并遗漏专用账户 `.local`、`.config` 父目录所有权，导致降权服务无法访问。v3.0.2 显式设置运行目录为 root-owned 0755、私有目录为 0700，并逐级设置专用账户目录为该账户所有的 0700；不递归修改既有数据。只对本安装器识别的同设备安装恢复，仍拒绝接管试点和同名未知账户。

已完成本机权限修复后的 PF、端口账户隔离、私钥读取限制、受控网络负向测试和日本出口验收；真实 Claude 回复和工具调用仍失败，原因待定位，iTerm2 界面/退格键验收仍未完成。本版本不宣称整套环境已经通过验收。回归测试覆盖 umask 077、新建/恢复、父目录服务 UID 所有权及符号链接拒绝；不替代目标机实际验收。

源码在 `fleet-kit/`；Git 仓库不包含大型软件和出口二进制，实际安装必须下载同版本完整 Release ZIP 并校验，不能直接运行不完整源码目录。旧 v3.1.0 附件保留供追溯，不覆盖。已安装设备请读取同版本手册后以原设备参数重跑安装入口恢复权限，并重新做全部验收；不要手动删除状态或重新生成身份。

## JP 统一模型管理

新 CN 默认使用 `group/cn-default`，JP 当前指向 Claude Opus 5.5。以后只在 JP 调整路由组。已安装 v3 CN 可按手册预览并运行 `setup/use_central_model.py --apply` 一次；历史无安装记录的试点需单独迁移。JP 当前总开关关闭，本次没有改变翻译/门禁开关。
