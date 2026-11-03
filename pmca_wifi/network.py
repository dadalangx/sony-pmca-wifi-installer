"""Own a temporary camera hotspot and restore the connections we changed."""
import asyncio
import ctypes as C
import json
import subprocess
import sys

from .hotspot import HotspotSession
from .windows import powershell, find_hotspot_adapter

COM = "$m=New-Object -ComObject HNetCfg.HNetShare; "
SNAPSHOT = COM + """
$rows=@(); foreach($c in $m.EnumEveryConnection){
 $p=$m.NetConnectionProps($c); $s=$m.INetSharingConfigurationForINetConnection($c)
 $rows+=@{name=$p.Name;guid=$p.Guid;enabled=[bool]$s.SharingEnabled;
 type=$(if($s.SharingEnabled){[int]$s.SharingConnectionType}else{-1})}
}; ConvertTo-Json -InputObject $rows -Compress
"""


def legacy_settings():
    """Read legacy AP capability/configuration with WLAN API, without mutation."""
    api = C.WinDLL("wlanapi", use_last_error=True)
    handle, version = C.c_void_p(), C.c_uint32()
    api.WlanOpenHandle.argtypes = [C.c_uint32, C.c_void_p, C.POINTER(C.c_uint32), C.POINTER(C.c_void_p)]
    api.WlanHostedNetworkQueryStatus.argtypes = [C.c_void_p, C.POINTER(C.c_void_p), C.c_void_p]
    api.WlanHostedNetworkQueryProperty.argtypes = [C.c_void_p, C.c_int, C.POINTER(C.c_uint32), C.POINTER(C.c_void_p), C.POINTER(C.c_int), C.c_void_p]
    api.WlanHostedNetworkQuerySecondaryKey.argtypes = [C.c_void_p, C.POINTER(C.c_uint32), C.POINTER(C.c_void_p), C.POINTER(C.c_int), C.POINTER(C.c_int), C.c_void_p, C.c_void_p]
    api.WlanFreeMemory.argtypes = [C.c_void_p]
    api.WlanCloseHandle.argtypes = [C.c_void_p, C.c_void_p]
    if api.WlanOpenHandle(2, None, C.byref(version), C.byref(handle)):
        return {"state": 0}
    result = {"state": 0, "ssid": "", "key": "", "enabled": True, "persistent": False}
    try:
        data = C.c_void_p()
        if not api.WlanHostedNetworkQueryStatus(handle, C.byref(data), None):
            result["state"] = C.cast(data, C.POINTER(C.c_uint32))[0]
            api.WlanFreeMemory(data)
        for opcode in (0, 3):
            length, data, source = C.c_uint32(), C.c_void_p(), C.c_int()
            if not api.WlanHostedNetworkQueryProperty(handle, opcode, C.byref(length), C.byref(data), C.byref(source), None):
                raw = C.string_at(data, length.value)
                if opcode == 0 and len(raw) >= 36:
                    size = int.from_bytes(raw[:4], "little")
                    if size <= 32:
                        result["ssid"] = raw[4:4 + size].decode("utf-8", errors="strict")
                elif opcode == 3 and len(raw) >= 4:
                    result["enabled"] = bool(int.from_bytes(raw[:4], "little"))
                api.WlanFreeMemory(data)
        length, data, phrase, persistent = C.c_uint32(), C.c_void_p(), C.c_int(), C.c_int()
        key_error = api.WlanHostedNetworkQuerySecondaryKey(handle, C.byref(length), C.byref(data), C.byref(phrase), C.byref(persistent), None, None)
        result["key_error"] = key_error
        if not key_error:
            raw = C.string_at(data, length.value)
            result["key"] = raw.rstrip(b"\0").decode("ascii") if phrase.value else raw.hex()
            result["persistent"] = bool(persistent.value)
            api.WlanFreeMemory(data)
    finally:
        api.WlanCloseHandle(handle, None)
    return result


def netsh(*args):
    result = subprocess.run(["netsh", "wlan", *args], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError("Windows 无法启动此网卡的热点。" + result.stdout.decode("mbcs", errors="replace").strip())


def sharing(public, private, enable):
    # GUIDs originate from Windows, never from camera/web requests.
    from uuid import UUID
    public, private = "{" + str(UUID(public)) + "}", "{" + str(UUID(private)) + "}"
    code = COM + f"""
    $public=$null; $private=$null
    foreach($c in $m.EnumEveryConnection){{
      $p=$m.NetConnectionProps($c)
      if($p.Guid -eq '{public}'){{$public=$c}}
      if($p.Guid -eq '{private}'){{$private=$c}}
    }}
    if(-not $public -or -not $private){{throw 'Could not identify sharing interfaces'}}
    """
    if enable:
        code += "$m.INetSharingConfigurationForINetConnection($public).EnableSharing(0); $m.INetSharingConfigurationForINetConnection($private).EnableSharing(1)"
    else:
        code += "foreach($c in @($private,$public)){$s=$m.INetSharingConfigurationForINetConnection($c);if($s.SharingEnabled){$s.DisableSharing()}}"
    powershell(code)


class NetworkSession:
    def __init__(self):
        self.mobile = None
        self.legacy = None
        self.started = False
        self.shared = False
        self.public, self.private = None, None

    async def start(self, ssid, password):
        info = legacy_settings()
        if info["state"] == 2:
            raise RuntimeError("电脑的传统热点正在使用中，请先关闭它再重试。")
        if info["state"] == 1:
            await self._start_legacy(ssid, password, info)
            mode = "传统热点"
        else:
            self.mobile = HotspotSession()
            await self.mobile.start(ssid, password)
            mode = "Windows 移动热点"
        for _ in range(20):
            try:
                return find_hotspot_adapter(), mode
            except RuntimeError:
                await asyncio.sleep(1)
        raise RuntimeError("热点已启动，但 Windows 尚未分配连接地址。")

    async def _start_legacy(self, ssid, password, info):
        from winrt.windows.networking.connectivity import NetworkInformation
        snapshot = json.loads(powershell(SNAPSHOT))
        if not snapshot:
            raise RuntimeError("无法读取 Windows 网络共享设置。")
        if any(row["enabled"] for row in snapshot):
            raise RuntimeError("电脑已有其他网络共享连接。请先结束该共享，再重试。")
        # Preserve existing idle Hosted Network credentials, if there are any.
        if info.get("key_error"):
            raise RuntimeError(f"读取现有热点配置失败（Windows 错误 {info['key_error']}）。")
        self.legacy = info
        profile = NetworkInformation.get_internet_connection_profile()
        if not profile:
            raise RuntimeError("请先让电脑连接网络。")
        self.public = str(profile.network_adapter.network_adapter_id)
        netsh("set", "hostednetwork", "mode=allow", "ssid=" + ssid, "key=" + password, "keyUsage=temporary")
        netsh("start", "hostednetwork")
        self.started = True
        for _ in range(15):
            rows = json.loads(powershell("$r=@(Get-NetAdapter -IncludeHidden | Where-Object { "
                "$_.InterfaceDescription -match 'Hosted Network' -and $_.Status -eq 'Up'} | "
                "Select-Object @{n='guid';e={$_.InterfaceGuid.ToString()}}); ConvertTo-Json -InputObject $r -Compress"))
            if len(rows) == 1:
                self.private = rows[0]["guid"]
                break
            await asyncio.sleep(1)
        if self.private is None:
            raise RuntimeError("传统热点的网卡尚未就绪。")
        self.shared = True  # Include partially failed EnableSharing in rollback.
        sharing(self.public, self.private, True)
        await asyncio.sleep(2)

    async def close(self):
        errors = []
        if self.shared:
            try:
                sharing(self.public, self.private, False)
                self.shared = False
            except Exception as error:
                errors.append(error)
        if self.started:
            try:
                netsh("stop", "hostednetwork")
                self.started = False
            except Exception as error:
                errors.append(error)
        if self.legacy:
            try:
                old = self.legacy
                if old["ssid"]:
                    args = ["set", "hostednetwork", "ssid=" + old["ssid"]]
                    if old["key"]:
                        args += ["key=" + old["key"], "keyUsage=" + ("persistent" if old["persistent"] else "temporary")]
                    netsh(*args)
                if not old["enabled"]:
                    netsh("set", "hostednetwork", "mode=disallow")
                self.legacy = None
            except Exception as error:
                errors.append(error)
        if self.mobile:
            try:
                await self.mobile.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise RuntimeError("热点清理未完成：" + "; ".join(str(e) for e in errors))
