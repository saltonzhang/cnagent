#!/bin/bash
# Entry point on a new CN MAC. No Homebrew, Node, Docker or preinstalled Python required.
set -euo pipefail
umask 077
cd "$(/usr/bin/dirname "$0")"
[[ "$OSTYPE" == darwin* && "$EUID" != 0 ]] || { echo '请在新 CN MAC 的普通管理员账户运行，不要 sudo 整个入口。' >&2; exit 1; }
/usr/bin/shasum -a 256 -c MANIFEST.sha256 >/dev/null || { echo '安装包校验失败，停止。' >&2; exit 1; }
major=$(/usr/bin/sw_vers -productVersion | /usr/bin/cut -d. -f1)
[[ "$major" -ge 13 ]] || { echo '本安装基线需要 macOS 13 或更高，仍须目标机验收。'; exit 1; }
py=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14
needs_python=1
if [[ -x "$py" ]]; then
  [[ "$(/usr/bin/stat -f %u /Library/Frameworks/Python.framework/Versions/3.14)" == 0 ]] || { echo 'Existing Python framework is not root managed'; exit 1; }
  if "$py" -c 'import sys;sys.exit(0 if sys.version_info >= (3,14,10) else 1)'; then needs_python=0; fi
fi
if [[ "$needs_python" == 1 ]]; then
  [[ "${1:-}" != --plan ]] || { echo '计划：安装包内 Python 3.14.10 和软件，生成登记申请；导入管理员接入包后验收。无需 JP 登录。'; exit 0; }
  /usr/sbin/pkgutil --check-signature software/python.pkg | /usr/bin/grep -Fq 'Developer ID Installer: Python Software Foundation (BMM5U3QVKW)' || { echo 'Python 签名校验失败。' >&2; exit 1; }
  echo '正在安装包内签名 Python；本机 sudo 可能要求管理员认证。'
  /usr/bin/sudo /usr/sbin/installer -pkg "$PWD/software/python.pkg" -target / >/dev/null
fi
# Root supervisor cannot depend on a user-writable interpreter/framework.
[[ "$(/usr/bin/stat -f %u /Library/Frameworks/Python.framework/Versions/3.14)" == 0 ]] || { echo 'Python runtime owner invalid'; exit 1; }
exec "$py" setup/install.py "$@"
