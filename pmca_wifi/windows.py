"""Small, scoped Windows networking operations. No router configuration."""
import ctypes
import ipaddress
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass

from .i18n import UserError


def powershell(code, timeout=25):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); " + code],
        capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise UserError("windows_network", detail=result.stderr.strip())
    return result.stdout.strip()


def is_admin():
    return sys.platform == "win32" and bool(ctypes.windll.shell32.IsUserAnAdmin())


@dataclass(frozen=True)
class HotspotAdapter:
    ip: str
    prefix: int
    index: int

    @property
    def network(self):
        return ipaddress.ip_network(f"{self.ip}/{self.prefix}", strict=False)


def find_hotspot_adapter():
    code = """
    $rows=@(Get-NetAdapter -IncludeHidden | Where-Object {
        $_.Status -eq 'Up' -and $_.InterfaceDescription -match 'Wi-Fi Direct|Hosted Network'
    } | ForEach-Object {
        Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {$_.IPAddress -notlike '169.254.*'} |
        Select-Object @{n='ip';e={$_.IPAddress}},@{n='prefix';e={$_.PrefixLength}},@{n='index';e={$_.InterfaceIndex}}
    }); ConvertTo-Json -InputObject $rows -Compress
    """
    rows = json.loads(powershell(code))
    if len(rows) != 1:
        raise UserError("adapter_missing")
    adapter = HotspotAdapter(**rows[0])
    if not ipaddress.ip_address(adapter.ip).is_private or not 16 <= adapter.prefix <= 30:
        raise UserError("adapter_address")
    return adapter


class FirewallRule:
    def __init__(self, adapter, port=80):
        self.name = "SonyPmcaWifi-" + uuid.uuid4().hex
        self.adapter = adapter
        self.port = int(port)
        self.created = False

    def start(self):
        if not is_admin():
            raise UserError("firewall_admin")
        # The rule is limited to this process, this hotspot address and subnet.
        executable = sys.executable.replace("'", "''")
        a = self.adapter
        powershell(f"New-NetFirewallRule -Name '{self.name}' -DisplayName 'Sony camera app installer (temporary)' "
                   f"-Direction Inbound -Action Allow -Protocol TCP -LocalPort {self.port} "
                   f"-LocalAddress '{a.ip}' -RemoteAddress '{a.network}' -Profile Any "
                   f"-Program '{executable}' | Out-Null")
        self.created = True

    def close(self):
        if self.created:
            powershell(f"Remove-NetFirewallRule -Name '{self.name}'")
            self.created = False
