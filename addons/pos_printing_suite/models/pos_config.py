# -*- coding: utf-8 -*-
import base64
import io
import json
import logging
import os
import re
import secrets
import subprocess
import zipfile

from odoo import api, fields, models, _
from odoo.modules.module import get_module_resource
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = "pos.config"

    AGENT_ARTIFACT_VERSION = "0.1.0"

    printing_mode = fields.Selection(
        [
            ("odoo_default", "Odoo (Standard)"),
            ("local_agent", "Local Agent (Windows)"),
            ("hw_proxy", "HW Proxy / Any Printer"),
        ],
        default="odoo_default",
        required=True,
    )
    local_agent_host = fields.Char(
        string="Local Agent IP",
        default="127.0.0.1",
    )
    local_agent_port = fields.Integer(
        string="Local Agent Port",
        default=9060,
    )
    local_printer_cashier_name = fields.Char(string="Printer (Cashier)")
    local_printer_kitchen_name = fields.Char(string="Printer (Kitchen)")
    any_printer_ip = fields.Char(
        string="HW Proxy Host",
        help="Host/IP for HW Proxy when printing_mode is HW Proxy.",
        default="127.0.0.1",
    )
    any_printer_port = fields.Integer(
        string="HW Proxy Port",
        default=8069,
    )
    printing_suite_allowed = fields.Boolean(
        compute="_compute_printing_suite_allowed",
        help="True when the user is allowed to use the Printing Suite and mode is enabled.",
    )

    agent_enabled = fields.Boolean(string="Windows Agent Enabled", default=False)
    agent_token = fields.Char(
        string="Agent Token",
        copy=False,
        groups="base.group_system",
    )
    agent_token_pos = fields.Char(
        compute="_compute_agent_token_pos",
        help="Agent token exposed to POS only for authorized users.",
    )
    agent_last_seen = fields.Datetime(string="Agent Last Seen", readonly=True)
    agent_version = fields.Char(string="Agent Version", readonly=True)
    agent_status = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("online", "Online"),
            ("offline", "Offline"),
        ],
        compute="_compute_agent_status",
        string="Agent Status",
    )
    agent_artifact_id = fields.Many2one(
        "ir.attachment",
        string="Agent Installer",
        readonly=True,
        copy=False,
        groups="base.group_system",
    )
    agent_download_url = fields.Char(
        compute="_compute_agent_download_url",
        string="Agent Download URL",
        groups="base.group_system",
    )
    agent_policy_download_url = fields.Char(
        compute="_compute_agent_policy_download_url",
        string="Loopback Policy Download URL",
        groups="base.group_system",
    )
    agent_printer_ids = fields.One2many(
        "pos.printing.agent.printer",
        "pos_config_id",
        string="Agent Printers",
        readonly=True,
    )
    local_printer_cashier_id = fields.Many2one(
        "pos.printing.agent.printer",
        string="Cashier Printer (Agent)",
    )
    local_printer_kitchen_id = fields.Many2one(
        "pos.printing.agent.printer",
        string="Kitchen Printer (Agent)",
    )

    @api.depends("printing_mode")
    @api.depends_context("uid")
    def _compute_printing_suite_allowed(self):
        for rec in self:
            rec.printing_suite_allowed = rec._is_printing_suite_allowed()

    @api.depends("agent_token", "printing_mode")
    @api.depends_context("uid")
    def _compute_agent_token_pos(self):
        for rec in self:
            if rec.printing_mode == "local_agent" and rec._is_printing_suite_allowed():
                rec.agent_token_pos = rec.agent_token
            else:
                rec.agent_token_pos = False

    def _is_printing_suite_allowed(self):
        self.ensure_one()
        if self.printing_mode not in ("local_agent", "hw_proxy"):
            return False
        if self.env.user.has_group("base.group_system"):
            return True
        group = self.env.ref("pos_printing_suite.group_pos_printing_suite_printing", raise_if_not_found=False)
        if not group:
            return False
        return group in self.env.user.groups_id

    @api.depends("agent_last_seen")
    def _compute_agent_status(self):
        threshold_minutes = 5
        now = fields.Datetime.now()
        for rec in self:
            if not rec.agent_last_seen:
                rec.agent_status = "unknown"
                continue
            delta = now - rec.agent_last_seen
            rec.agent_status = "online" if delta.total_seconds() <= threshold_minutes * 60 else "offline"

    def _compute_agent_download_url(self):
        for rec in self:
            rec.agent_download_url = f"/pos_printing_suite/agent/download?config_id={rec.id}"

    def _compute_agent_policy_download_url(self):
        for rec in self:
            rec.agent_policy_download_url = f"/pos_printing_suite/agent/policy.ps1?config_id={rec.id}"

    def _generate_agent_token(self):
        return secrets.token_urlsafe(32)

    def _ensure_agent_token(self):
        for rec in self:
            if not rec.agent_token:
                rec.agent_token = rec._generate_agent_token()

    def _apply_printer_ids_to_vals(self, vals):
        if vals.get("local_printer_cashier_id"):
            printer = self.env["pos.printing.agent.printer"].browse(vals["local_printer_cashier_id"])
            if printer.exists():
                vals["local_printer_cashier_name"] = printer.name
        if vals.get("local_printer_kitchen_id"):
            printer = self.env["pos.printing.agent.printer"].browse(vals["local_printer_kitchen_id"])
            if printer.exists():
                vals["local_printer_kitchen_name"] = printer.name

    def action_regenerate_agent_token(self):
        self._ensure_admin()
        for rec in self:
            rec.agent_token = rec._generate_agent_token()
        return self._notify(_("Agent token regenerated."), "success")

    def action_build_agent_installer(self):
        self._ensure_admin()
        attachment = self._build_agent_installer()
        return self._notify(
            _("Installer generated: %s") % attachment.name, "success"
        )

    def action_download_agent_installer(self):
        self._ensure_admin()
        self.ensure_one()
        # Always rebuild to avoid stale/cached installers.
        self._build_agent_installer()
        if not self.agent_download_url:
            raise UserError(_("Download URL is not available."))
        return {
            "type": "ir.actions.act_url",
            "url": self.agent_download_url,
            "target": "self",
        }

    def action_open_agent_install_wizard(self):
        self._ensure_admin()
        self.ensure_one()
        if not self.agent_artifact_id:
            self._build_agent_installer()
        return {
            "type": "ir.actions.act_window",
            "name": _("Install Windows Agent"),
            "res_model": "pos.printing.suite.agent.install.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_pos_config_id": self.id},
        }

    def action_download_agent_policy(self):
        self._ensure_admin()
        self.ensure_one()
        if not self.agent_policy_download_url:
            raise UserError(_("Policy download URL is not available."))
        return {
            "type": "ir.actions.act_url",
            "url": self.agent_policy_download_url,
            "target": "self",
        }

    def _build_agent_installer(self):
        self.ensure_one()
        self._ensure_agent_token()
        if self.agent_artifact_id:
            self.agent_artifact_id.unlink()
            self.agent_artifact_id = False
        agent_root = get_module_resource("pos_printing_suite", "agent_src", "local_printer_agent")
        dist_root = get_module_resource("pos_printing_suite", "agent_src", "dist")
        if not agent_root:
            raise UserError(_("Agent source folder not found."))

        build_cmd = os.environ.get("POS_PRINTING_SUITE_AGENT_BUILD_CMD")
        if build_cmd:
            self._run_agent_build(build_cmd, agent_root)

        msi_path = self._find_compiled_msi(dist_root, agent_root)
        if msi_path:
            artifact_name = os.path.basename(msi_path)
            with open(msi_path, "rb") as handle:
                payload = handle.read()
            mimetype = "application/x-msi"
        else:
            artifact_name = f"windows_agent_v{self.AGENT_ARTIFACT_VERSION}.zip"
            payload = self._build_agent_zip_payload(
                agent_root=agent_root,
                dist_root=dist_root,
                run_build=False,
            )
            mimetype = "application/zip"

        attachment = self.env["ir.attachment"].create({
            "name": artifact_name,
            "type": "binary",
            "datas": base64.b64encode(payload),
            "res_model": "pos.config",
            "res_id": self.id,
            "mimetype": mimetype,
        })
        self.agent_artifact_id = attachment
        return attachment

    def _build_agent_zip_payload(self, agent_root=None, dist_root=None, run_build=True):
        self.ensure_one()
        module_root = get_module_resource("pos_printing_suite")
        agent_root = agent_root or get_module_resource("pos_printing_suite", "agent_src", "local_printer_agent")
        dist_root = dist_root or get_module_resource("pos_printing_suite", "agent_src", "dist")
        if not agent_root:
            raise UserError(_("Agent source folder not found."))

        if run_build:
            build_cmd = os.environ.get("POS_PRINTING_SUITE_AGENT_BUILD_CMD")
            if build_cmd:
                self._run_agent_build(build_cmd, agent_root)

        base_url = self._get_request_base_url() or self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        config = {
            "server_url": base_url,
            "token": self.agent_token,
            "pos_config_id": self.id,
        }
        loopback_policy = self._build_loopback_policy_script(base_url=base_url)
        installer_lines = [
            "$ErrorActionPreference = 'Stop'",
            "$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())",
            "if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {",
            "  Write-Host 'ERROR: Please run install.ps1 as Administrator.'",
            "  exit 1",
            "}",
            "$baseDir = Join-Path $env:ProgramData 'PosPrintingSuite\\Agent'",
            "New-Item -ItemType Directory -Force -Path $baseDir | Out-Null",
            "$logPath = Join-Path $baseDir 'install.log'",
            "function Log([string]$msg) {",
            "  $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')",
            "  Add-Content -Path $logPath -Value \"[$ts] $msg\"",
            "}",
            "Log 'Starting installer script.'",
            "$srcDir = (Resolve-Path $PSScriptRoot).Path",
            "$dstDir = (Resolve-Path $baseDir).Path",
            "if ($srcDir -ne $dstDir) {",
            "  Log \"Copying files from $srcDir to $dstDir\"",
            "  Copy-Item -Path (Join-Path $srcDir '*') -Destination $baseDir -Recurse -Force",
            "} else {",
            "  Log 'Source directory is already ProgramData. Skipping copy.'",
            "}",
            "$serviceName = 'PosPrintingSuiteAgent'",
            "$exe = Join-Path $baseDir 'agent.exe'",
            "$onedirExe = Join-Path $baseDir 'dist\\LocalPrinterAgent\\LocalPrinterAgent.exe'",
            "$singleExe = Join-Path $baseDir 'LocalPrinterAgent.exe'",
            "if (Test-Path $onedirExe) { $exe = $onedirExe }",
            "elseif (Test-Path $singleExe) { $exe = $singleExe }",
            "elseif (-not (Test-Path $exe)) {",
            "  $py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source",
            "  if (-not $py) { $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }",
            "  if ($py) {",
            "    $exe = $py",
            "    $script = Join-Path $baseDir 'run_agent.py'",
            "    $binPath = \"`\"$exe`\" `\"$script`\"\"",
            "  } else {",
            "    Log 'No compiled agent executable found and python not available.'",
            "    Write-Host 'No compiled agent executable found and python not available.'",
            "    exit 1",
            "  }",
            "} else {",
            "  $binPath = \"`\"$exe`\"\"",
            "}",
            "if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {",
            "  Log 'Service exists. Stopping and deleting.'",
            "  sc.exe stop $serviceName | Out-Null",
            "  sc.exe delete $serviceName | Out-Null",
            "  Start-Sleep -Seconds 1",
            "}",
            "Log \"Creating service with binPath: $binPath\"",
            "sc.exe create $serviceName binPath= $binPath start= auto | Out-Null",
            "sc.exe description $serviceName \"POS Printing Suite Windows Agent\" | Out-Null",
            "sc.exe failure $serviceName reset= 0 actions= restart/5000 | Out-Null",
            "sc.exe failureflag $serviceName 1 | Out-Null",
            "sc.exe start $serviceName | Out-Null",
            "$trayScript = Join-Path $baseDir 'tray_agent.ps1'",
            "$trayCmd = Join-Path $env:SystemRoot 'System32\\WindowsPowerShell\\v1.0\\powershell.exe'",
            "$trayArgs = \"-NoProfile -ExecutionPolicy Bypass -File `\"$trayScript`\"\"",
            "$iconPath = Join-Path $baseDir 'assets\\agent.ico'",
            "$publicDesktop = [Environment]::GetFolderPath('CommonDesktopDirectory')",
            "$startupDir = [Environment]::GetFolderPath('CommonStartup')",
            "$shortcutName = 'POS Printing Suite Agent.lnk'",
            "try {",
            "  if (Test-Path $trayScript) {",
            "    $wsh = New-Object -ComObject WScript.Shell",
            "    $desktopShortcut = $wsh.CreateShortcut((Join-Path $publicDesktop $shortcutName))",
            "    $desktopShortcut.TargetPath = $trayCmd",
            "    $desktopShortcut.Arguments = $trayArgs",
            "    $desktopShortcut.WorkingDirectory = $baseDir",
            "    if (Test-Path $iconPath) { $desktopShortcut.IconLocation = $iconPath }",
            "    $desktopShortcut.Save()",
            "    $startupShortcut = $wsh.CreateShortcut((Join-Path $startupDir $shortcutName))",
            "    $startupShortcut.TargetPath = $trayCmd",
            "    $startupShortcut.Arguments = $trayArgs",
            "    $startupShortcut.WorkingDirectory = $baseDir",
            "    if (Test-Path $iconPath) { $startupShortcut.IconLocation = $iconPath }",
            "    $startupShortcut.Save()",
            "  }",
            "} catch { Log \"Shortcut error: $($_.Exception.Message)\" }",
            "$configPath = Join-Path $baseDir 'config.json'",
            "$serverUrl = ''",
            "if (Test-Path $configPath) {",
            "  try {",
            "    $cfg = Get-Content $configPath -Raw | ConvertFrom-Json",
            "    $serverUrl = $cfg.server_url",
            "  } catch { Log \"Config parse error: $($_.Exception.Message)\" }",
            "}",
            "$policyScript = Join-Path $baseDir 'enable_loopback_policy.ps1'",
            "try {",
            "  if ($serverUrl -like 'https://*' -and (Test-Path $policyScript)) {",
            "    & $policyScript",
            "  }",
            "} catch { Log \"Loopback policy error: $($_.Exception.Message)\" }",
            "try {",
            "  if (Test-Path $trayScript) {",
            "    Start-Process $trayCmd -ArgumentList $trayArgs",
            "  }",
            "} catch { Log \"Tray start error: $($_.Exception.Message)\" }",
            "Log 'Agent installed and started.'",
            "Write-Host 'Agent installed and started.'",
        ]
        installer_ps1 = "\n".join(installer_lines) + "\n"

        uninstall_lines = [
            "$ErrorActionPreference = 'SilentlyContinue'",
            "sc.exe stop PosPrintingSuiteAgent | Out-Null",
            "sc.exe delete PosPrintingSuiteAgent | Out-Null",
            "$baseDir = Join-Path $env:ProgramData 'PosPrintingSuite\\Agent'",
            "$publicDesktop = [Environment]::GetFolderPath('CommonDesktopDirectory')",
            "$startupDir = [Environment]::GetFolderPath('CommonStartup')",
            "$shortcutName = 'POS Printing Suite Agent.lnk'",
            "Remove-Item -Force (Join-Path $publicDesktop $shortcutName) -ErrorAction SilentlyContinue",
            "Remove-Item -Force (Join-Path $startupDir $shortcutName) -ErrorAction SilentlyContinue",
            "Remove-Item -Recurse -Force $baseDir",
            "Write-Host 'Agent uninstalled.'",
        ]
        uninstall_ps1 = "\n".join(uninstall_lines) + "\n"
        readme_txt = (
            "Windows Agent (bundle)\n"
            "1) Run install.ps1 as Administrator.\n"
            "2) The service will start automatically.\n"
            "3) If your POS runs on HTTPS, run enable_loopback_policy.ps1 as Administrator.\n"
            "4) If no compiled agent is present, build it using the scripts in installer/.\n"
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("config.json", json.dumps(config, indent=2))
            zipf.writestr("install.ps1", installer_ps1)
            zipf.writestr("uninstall.ps1", uninstall_ps1)
            zipf.writestr("enable_loopback_policy.ps1", loopback_policy)
            zipf.writestr("README.txt", readme_txt)
            self._zip_directory(zipf, agent_root, base_path="")
            compiled = self._find_compiled_agent(dist_root, agent_root)
            if not compiled:
                _logger.warning(
                    "No compiled agent binary found. "
                    "Set POS_PRINTING_SUITE_AGENT_BUILD_CMD or place the compiled "
                    "binary under agent_src/dist/LocalPrinterAgent/LocalPrinterAgent.exe."
                )
            if compiled and dist_root and os.path.isdir(dist_root):
                self._zip_directory(zipf, dist_root, base_path="dist")
        return buffer.getvalue()

    def _build_loopback_policy_script(self, base_url=None):
        base_url = base_url or self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        base_url = base_url.rstrip("/")
        urls = set()
        if base_url:
            urls.add(base_url)
        if base_url.startswith("http://"):
            urls.add("https://" + base_url[len("http://"):])
        elif base_url.startswith("https://"):
            urls.add("http://" + base_url[len("https://"):])
        if not urls:
            urls = {"http://localhost", "https://localhost"}
        url_list = ", ".join([f"'{u}'" for u in sorted(urls)])
        return (
            "$ErrorActionPreference = 'Stop'\n"
            "$chromePath = 'HKLM:\\\\SOFTWARE\\\\Policies\\\\Google\\\\Chrome'\n"
            "New-Item -Path $chromePath -Force | Out-Null\n"
            "New-ItemProperty -Path $chromePath -Name InsecurePrivateNetworkRequestsAllowed -PropertyType DWord -Value 1 -Force | Out-Null\n"
            f"New-ItemProperty -Path $chromePath -Name InsecurePrivateNetworkRequestsAllowedForUrls -PropertyType MultiString -Value @({url_list}) -Force | Out-Null\n"
            "$edgePath = 'HKLM:\\\\SOFTWARE\\\\Policies\\\\Microsoft\\\\Edge'\n"
            "New-Item -Path $edgePath -Force | Out-Null\n"
            "New-ItemProperty -Path $edgePath -Name InsecurePrivateNetworkRequestsAllowed -PropertyType DWord -Value 1 -Force | Out-Null\n"
            f"New-ItemProperty -Path $edgePath -Name InsecurePrivateNetworkRequestsAllowedForUrls -PropertyType MultiString -Value @({url_list}) -Force | Out-Null\n"
            "Write-Host 'Loopback policy applied. Restart Chrome/Edge.'\n"
        )

    def _get_request_base_url(self):
        """Best-effort base URL from the current HTTP request (respects proxy headers)."""
        try:
            if request and getattr(request, "httprequest", None):
                httpreq = request.httprequest
                proto = (
                    httpreq.headers.get("X-Forwarded-Proto")
                    or httpreq.headers.get("X-Forwarded-Protocol")
                    or httpreq.headers.get("X-Forwarded-Ssl")
                )
                if proto:
                    proto = proto.split(",")[0].strip()
                    if proto.lower() in ("on", "true"):
                        proto = "https"
                else:
                    proto = httpreq.scheme
                if proto != "https":
                    origin = httpreq.headers.get("Origin") or httpreq.headers.get("Referer")
                    if origin and origin.startswith("https://"):
                        proto = "https"
                host = httpreq.headers.get("X-Forwarded-Host") or httpreq.host
                if proto and host:
                    return f"{proto}://{host}"
                return httpreq.url_root.rstrip("/")
        except Exception:
            return None
        return None

    def _run_agent_build(self, build_cmd, agent_root):
        installer_dir = os.path.join(agent_root, "installer")
        if not os.path.isdir(installer_dir):
            raise UserError(_("Agent installer folder not found: %s") % installer_dir)
        _logger.info("Running agent build command: %s", build_cmd)
        try:
            subprocess.run(
                build_cmd,
                shell=True,
                cwd=installer_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            _logger.error("Agent build failed: %s", exc.stderr)
            raise UserError(_("Agent build failed:\n%s") % (exc.stderr or exc.stdout or str(exc)))

    def _zip_directory(self, zipf, root_dir, base_path=""):
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for filename in files:
                if filename.endswith(".pyc"):
                    continue
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, root_dir)
                arc_path = os.path.join(base_path, rel_path) if base_path else rel_path
                zipf.write(abs_path, arc_path)

    def _find_compiled_agent(self, dist_root, agent_root):
        candidates = []
        if dist_root:
            candidates.extend([
                os.path.join(dist_root, "LocalPrinterAgent", "LocalPrinterAgent.exe"),
                os.path.join(dist_root, "LocalPrinterAgent.exe"),
            ])
        if agent_root:
            candidates.append(os.path.join(agent_root, "agent.exe"))
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    def _find_compiled_msi(self, dist_root, agent_root):
        candidates = []
        if dist_root and os.path.isdir(dist_root):
            for name in os.listdir(dist_root):
                if name.lower().endswith(".msi"):
                    candidates.append(os.path.join(dist_root, name))
        if agent_root and os.path.isdir(agent_root):
            for name in os.listdir(agent_root):
                if name.lower().endswith(".msi"):
                    candidates.append(os.path.join(agent_root, name))
        existing = [path for path in candidates if path and os.path.isfile(path)]
        if not existing:
            return None
        # Prefer the newest MSI by modification time.
        existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return existing[0]

    def _notify(self, message, notif_type="info"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("POS Printing Suite"),
                "message": message,
                "type": notif_type,
                "sticky": False,
            },
        }

    def _ensure_admin(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can perform this action."))

    @api.onchange("local_printer_cashier_id")
    def _onchange_local_printer_cashier_id(self):
        if self.local_printer_cashier_id:
            self.local_printer_cashier_name = self.local_printer_cashier_id.name

    @api.onchange("local_printer_kitchen_id")
    def _onchange_local_printer_kitchen_id(self):
        if self.local_printer_kitchen_id:
            self.local_printer_kitchen_name = self.local_printer_kitchen_id.name

    def _normalize_port_value(self, value, field_label):
        if value in (None, False, ""):
            return None
        if isinstance(value, str):
            cleaned = re.sub(r"[,\s]", "", value)
        else:
            cleaned = str(value)
        try:
            port = int(cleaned)
        except (TypeError, ValueError):
            raise ValidationError(_("%s must be an integer between 1 and 65535.") % field_label)
        if port < 1 or port > 65535:
            raise ValidationError(_("%s must be between 1 and 65535.") % field_label)
        return port

    def _normalize_host_value(self, value, field_label):
        if not value:
            return None
        host = value.strip()
        if not host or re.search(r"[\s,]", host):
            raise ValidationError(_("%s is invalid.") % field_label)
        return host

    @api.constrains("any_printer_ip", "any_printer_port")
    def _check_hw_proxy_settings(self):
        for rec in self:
            if rec.printing_mode != "hw_proxy":
                continue
            rec._normalize_host_value(rec.any_printer_ip, _("HW Proxy Host"))
            rec._normalize_port_value(rec.any_printer_port, _("HW Proxy Port"))

    @api.onchange("any_printer_port")
    def _onchange_any_printer_port(self):
        if isinstance(self.any_printer_port, str):
            self.any_printer_port = self._normalize_port_value(
                self.any_printer_port, _("HW Proxy Port")
            )

    @api.onchange("local_agent_port")
    def _onchange_local_agent_port(self):
        if isinstance(self.local_agent_port, str):
            self.local_agent_port = self._normalize_port_value(
                self.local_agent_port, _("Local Agent Port")
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_printer_ids_to_vals(vals)
            if "any_printer_port" in vals:
                vals["any_printer_port"] = self._normalize_port_value(
                    vals.get("any_printer_port"), _("HW Proxy Port")
                )
            if "local_agent_port" in vals:
                vals["local_agent_port"] = self._normalize_port_value(
                    vals.get("local_agent_port"), _("Local Agent Port")
                )
            if "any_printer_ip" in vals:
                vals["any_printer_ip"] = self._normalize_host_value(
                    vals.get("any_printer_ip"), _("HW Proxy Host")
                )
        records = super().create(vals_list)
        records._ensure_agent_token()
        return records

    def write(self, vals):
        self._apply_printer_ids_to_vals(vals)
        if "any_printer_port" in vals:
            vals["any_printer_port"] = self._normalize_port_value(
                vals.get("any_printer_port"), _("HW Proxy Port")
            )
        if "local_agent_port" in vals:
            vals["local_agent_port"] = self._normalize_port_value(
                vals.get("local_agent_port"), _("Local Agent Port")
            )
        if "any_printer_ip" in vals:
            vals["any_printer_ip"] = self._normalize_host_value(
                vals.get("any_printer_ip"), _("HW Proxy Host")
            )
        res = super().write(vals)
        if "agent_token" in vals:
            return res
        self._ensure_agent_token()
        return res

    def _normalize_existing_hw_proxy_ports(self):
        for rec in self.sudo().search([]):
            updates = {}
            if rec.any_printer_port:
                updates["any_printer_port"] = rec._normalize_port_value(
                    rec.any_printer_port, _("HW Proxy Port")
                )
            if rec.local_agent_port:
                updates["local_agent_port"] = rec._normalize_port_value(
                    rec.local_agent_port, _("Local Agent Port")
                )
            if updates:
                rec.write(updates)

    def _loader_params_pos_config(self):
        parent = getattr(super(), "_loader_params_pos_config", None)
        params = parent() if callable(parent) else {"fields": []}
        params["fields"].extend([
            "printing_mode",
            "printing_suite_allowed",
            "local_agent_host",
            "local_agent_port",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "agent_token_pos",
            "agent_policy_download_url",
            "any_printer_ip",
            "any_printer_port",
        ])
        return params

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        # If fields is falsy, the base loader will load all fields; keep that behavior.
        if not fields:
            return fields
        extras = [
            "printing_mode",
            "printing_suite_allowed",
            "local_agent_host",
            "local_agent_port",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "agent_token_pos",
            "agent_policy_download_url",
            "any_printer_ip",
            "any_printer_port",
        ]
        for f in extras:
            if f not in fields:
                fields.append(f)
        return fields

    # NOTE: no device/token required; printing suite is configured by printer names only.
