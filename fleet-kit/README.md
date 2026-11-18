# CN installer kit v3 — no JP login from CN

Read archive-root `CN-MAC-AI-DEPLOYMENT.md`. On a new CN Mac, its ordinary administrator runs `bash install.sh`. All baseline software is bundled for arm64/Intel. The installer prepares local accounts/software and exports a public device request, then reports **awaiting_admin_access_bundle**, not success.

Only the JP administrator processes that request locally with `admin/issue_access.py`; see `JP-MAC-DEVICE-ENROLLMENT.md`. No new CN SSH login, JP password, management account or remote-command flag exists. Source tools do not grant JP authority: the administrator-only issuer requires the existing JP private CA, pinned gateway and local administrator files. No such private material is included.

Continue on CN with `bash install.sh --access-bundle /path/device.access.json`. By default the signed access bundle includes this device's Gateway Key and configuration is automatic. If the administrator signs with `--omit-api-key`, importing a verified bundle asks for the Key through a hidden interactive-terminal prompt. Never put it in chat, arguments or environment variables. A Key alone does not replace the required device certificate.

Bundles are signature-protected, not encrypted; safely transfer any bundle containing a Key. They are bound to the root-saved request/CSR/nonce/route and expire for import. A pinned public JP CA validates a dedicated codeSigning identity; a normal TLS client certificate cannot forge a bundle. Root independently repeats verification.

Default supported workflow is controlled Claude, not Codex tools/controlled VS Code. See `VALIDATION.json` for the exact isolated versus live scope. A second Intel/macOS 13 CN reached enrollment/import and passed network checks after directory permission repair; Claude reply/tool and GUI acceptance remain incomplete. Full target acceptance is required.

## v3.0.2 安装权限修复与验证范围

v3.0.1 在严格 umask 下将受控运行目录创建为 root-only，并遗漏专用账户 `.local`、`.config` 父目录所有权，导致降权服务无法访问。v3.0.2 显式设置运行目录为 root-owned 0755、私有目录为 0700，并逐级设置专用账户目录为该账户所有的 0700；不递归修改既有数据。只对本安装器识别的同设备安装恢复，仍拒绝接管试点和同名未知账户。

已完成本机权限修复后的 PF、端口账户隔离、私钥读取限制、受控网络负向测试和日本出口验收；真实 Claude 回复和工具调用仍失败，原因待定位，iTerm2 界面/退格键验收仍未完成。本版本不宣称整套环境已经通过验收。回归测试覆盖 umask 077、新建/恢复、父目录服务 UID 所有权及符号链接拒绝；不替代目标机实际验收。

源码在 `fleet-kit/`；Git 仓库不包含大型软件和出口二进制，实际安装必须下载同版本完整 Release ZIP 并校验，不能直接运行不完整源码目录。旧 v3.0.1 附件保留供追溯，不覆盖。已安装设备请读取同版本手册后以原设备参数重跑安装入口恢复权限，并重新做全部验收；不要手动删除状态或重新生成身份。
