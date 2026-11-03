"""Per-user preferences; hotspot credentials are protected with Windows DPAPI."""
import ctypes as C
import json
import os
from pathlib import Path
import re
import secrets

from .i18n import LANGUAGES, system_language


def state_dir():
    path = Path(os.environ["LOCALAPPDATA"]) / "SonyPmcaWifiInstaller"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_language():
    try:
        language = json.loads((state_dir() / "preferences.json").read_text(encoding="utf-8"))["language"]
        if isinstance(language, str) and language in LANGUAGES:
            return language
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return system_language()


def save_language(language):
    if language not in LANGUAGES:
        raise ValueError("Unsupported language")
    file = state_dir() / "preferences.json"
    temporary = file.with_suffix(".new")
    temporary.write_text(json.dumps({"language": language}) + "\n", encoding="utf-8")
    temporary.replace(file)


class Blob(C.Structure):
    _fields_ = [("size", C.c_uint32), ("data", C.POINTER(C.c_ubyte))]


def dpapi(data, decrypt=False):
    storage = C.create_string_buffer(data)
    source = Blob(len(data), C.cast(storage, C.POINTER(C.c_ubyte)))
    target = Blob()
    if decrypt:
        ok = C.windll.crypt32.CryptUnprotectData(C.byref(source), None, None, None, None, 1, C.byref(target))
    else:
        ok = C.windll.crypt32.CryptProtectData(C.byref(source), None, None, None, None, 1, C.byref(target))
    if not ok:
        raise C.WinError()
    try:
        return C.string_at(target.data, target.size)
    finally:
        C.windll.kernel32.LocalFree.argtypes = [C.c_void_p]
        C.windll.kernel32.LocalFree(target.data)


def credentials():
    file = state_dir() / "hotspot.bin"
    if file.exists():
        try:
            result = json.loads(dpapi(file.read_bytes(), decrypt=True))
            if re.fullmatch(r"SONY-APPS-[0-9A-F]{4}", result["ssid"]) and re.fullmatch(r"[0-9]{8}", result["password"]):
                return result
        except (OSError, ValueError, KeyError, TypeError):
            pass
    result = {"ssid": "SONY-APPS-" + secrets.token_hex(2).upper(),
              "password": "".join(secrets.choice("0123456789") for _ in range(8))}
    temporary = file.with_suffix(".new")
    temporary.write_bytes(dpapi(json.dumps(result).encode()))
    temporary.replace(file)
    return result
