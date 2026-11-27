# CN installer kit v3.3.0 — no JP login from CN

Read archive-root `CN-MAC-AI-DEPLOYMENT.md`. On a new CN Mac, its ordinary administrator runs `bash install.sh`. All baseline software is bundled for arm64/Intel. The installer prepares local accounts/software and exports a public device request, then reports **awaiting_admin_access_bundle**, not success.

Only the JP administrator processes that request locally with `admin/issue_access.py`; see `JP-MAC-DEVICE-ENROLLMENT.md`. No new CN SSH login, JP password, management account or remote-command flag exists. Source tools do not grant JP authority: the administrator-only issuer requires the existing JP private CA, pinned gateway and local administrator files. No such private material is included.

Continue on CN with `bash install.sh --access-bundle /path/device.access.json`. By default the signed access bundle includes this device's Gateway Key and configuration is automatic. If the administrator signs with `--omit-api-key`, importing a verified bundle asks for the Key through a hidden interactive-terminal prompt. Never put it in chat, arguments or environment variables. A Key alone does not replace the required device certificate.

Bundles are signature-protected, not encrypted; safely transfer any bundle containing a Key. They are bound to the root-saved request/CSR/nonce/route and expire for import. A pinned public JP CA validates a dedicated codeSigning identity; a normal TLS client certificate cannot forge a bundle. Root independently repeats verification.

Default supported workflow is controlled Claude, not Codex tools/controlled VS Code. See `VALIDATION.json` for the exact isolated versus live scope. A fresh second-CN privileged end-to-end installation has not been performed; actual target kernel, GUI and upstream acceptance are required.

Default model is group/cn-default, centrally managed on JP, actual model is whatever JP currently configures (recently Sonnet 5.5). Admin uses admin/central_model.py. Existing v3 CNs may preview/apply setup/use_central_model.py; it preserves keys, has per-file rollback, and requires a fresh Claude session. Historical unmanaged pilot migration is refused.

Issuance now requires an explicit --period day|week|month with positive --tokens/--cost, or an explicitly approved --unlimited. Budget setup and verification must succeed before delivery. Use admin/manage_budget.py for per-device status, preview and changes. No current production budgets are changed by installing this kit. See AI-INSTALL-PROMPT.md and AI-ADMIN-PROMPT.md at archive root.

Default controlled process TZ is Asia/Tokyo. Existing managed v3.1.1/v3.2.0 CNs use setup/set_agent_timezone.py preview then --apply, or the small CN-MAC-JST-UPDATE.zip; do not reinstall. System timezone/locale and credentials are unchanged. Reopen the controlled shell; this is not a block on reading host metadata. Legacy unmanaged pilots are refused.

Agent-only localtime guard: load the current network sandbox and append a deny on /etc/localtime and /private/etc/localtime; service policy and host timezone remain unchanged. This does not guarantee complete host location secrecy. Old conversation data is not removed.

CN162 baseline: Claude model=sonnet; Sonnet/Opus/Haiku defaults all map to remote-magpie/group/cn-default. No forced effort or new model allowlist. Existing managed central-group devices can preview/apply setup/set_agent_defaults.py without re-enrollment; the small update bundles both defaults and timezone helpers. Fresh installs add a per-operator Desktop entry without overwriting unrelated files. No CN162 identity, Mobile mode, or special SSH grants are copied.

Repository sharing: setup installs root-managed share-repo and public account context, never shares a repo automatically. See repo-sharing/README.md. Select paths with --share-repo, explicit Git identity, or invoke share-repo afterward. Existing CNs use setup/install_repo_sharing.py preview/apply; no reinstall, network/model restart or credential transfer. Only tracked files, explicit refresh; Home traversal is opt-in.
