# CN Agent — JP 管理员登记工具 v3.0

为新 CN MAC 签发设备证书和独立 Magpie Gateway Key。**新 CN 不需要也不应取得 JP SSH 登录权限。**

## 下载

- [管理员工具包 ZIP](https://github.com/saltonzhang/cnagent/raw/refs/heads/main/JP-MAC-ENROLLMENT-ADMIN-KIT.zip)
- [SHA-256 校验文件](https://github.com/saltonzhang/cnagent/raw/refs/heads/main/JP-MAC-ENROLLMENT-ADMIN-KIT.zip.sha256)
- [完整签发手册](JP-MAC-DEVICE-ENROLLMENT.md)
- [对应源码](jp-admin-kit/)

本仓库仅发布管理员工具，不含 CN 端完整软件安装包。工具使用已有 JP 服务，不安装或替换 JP Magpie。

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
- 41 项安装/登记隔离测试通过；签名和证书使用真实 OpenSSL，Gateway CLI 采用临时模拟。没有以此声称已在第二台空白 CN 完成系统级安装或在生产 JP 签发测试身份。
- 不重建 WireGuard，不建立 SSH 数据隧道，不修改 JP 翻译、门禁、审计和现有开关。具体前置条件、审批、撤销和维护见手册。

版本日期：2026-11-18。
