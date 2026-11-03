"""Read APK metadata and create the Sony SPK container without changing the APK."""
from dataclasses import dataclass
import hashlib
import io
import re
import struct
import zipfile
import zlib

from Cryptodome.Cipher import AES
from .spk_constants import blockSize, rsaModulus, rsaExponent, sampleSpkKey
from .i18n import PackageError

MAX_APK = 16 * 1024 * 1024
RECIPE_URL = "https://github.com/voxivoid/recipe-lab-sony-pmca/releases/download/v1.11.1/RecipeLab.apk"
RECIPE_SHA256 = "e43b6914cb62cc1141799080bf8c14f216705d11eee73809b9841ca4e8c10b42"
PACKAGE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")


def _strings(data, start, hsize, size):
    if hsize < 28:
        raise ValueError("Invalid string pool header")
    count, _, flags, offset, styles = struct.unpack_from("<5I", data, start + 8)
    if (count > 100000 or hsize + count * 4 > size or offset < hsize + count * 4
            or offset > size or (styles and not offset <= styles <= size)):
        raise ValueError("Invalid string pool bounds")
    limit = start + (styles or size)
    result = []

    def length_at(pos, width):
        if pos + width > limit:
            raise ValueError("Truncated string length")
        value = int.from_bytes(data[pos:pos + width], "little")
        pos += width
        flag = 1 << (width * 8 - 1)
        if value & flag:
            if pos + width > limit:
                raise ValueError("Truncated extended length")
            value = ((value & (flag - 1)) << (width * 8)) | int.from_bytes(data[pos:pos + width], "little")
            pos += width
        return value, pos

    for index in range(count):
        relative = struct.unpack_from("<I", data, start + hsize + index * 4)[0]
        pos = start + offset + relative
        width = 1 if flags & 0x100 else 2
        if pos < start + offset or pos >= limit:
            raise ValueError("String offset outside pool")
        length, pos = length_at(pos, width)
        if width == 1:
            length, pos = length_at(pos, width)  # UTF-8 stores character and byte lengths.
        end = pos + length * width
        if end + width > limit or data[end:end + width] != b"\0" * width:
            raise ValueError("Truncated string")
        result.append(data[pos:end].decode("utf-8" if width == 1 else "utf-16-le"))
    return result


def manifest_metadata(data):
    if len(data) < 8 or len(data) > 2 * 1024 * 1024:
        raise ValueError("APK manifest size is invalid")
    kind, hsize, total = struct.unpack_from("<HHI", data)
    if kind != 3 or hsize < 8 or total != len(data):
        raise ValueError("APK must contain a compiled Android manifest")
    pos, strings, metadata = hsize, [], {}
    while pos < total:
        if pos + 8 > total:
            raise ValueError("Truncated XML chunk")
        kind, header, size = struct.unpack_from("<HHI", data, pos)
        if header < 8 or size < header or pos + size > total:
            raise ValueError("Invalid XML chunk bounds")
        if kind == 1:
            strings = _strings(data, pos, header, size)
        elif kind == 0x0102:
            if header != 16 or size < 36:
                raise ValueError("Invalid element header")
            name = struct.unpack_from("<I", data, pos + 20)[0]
            attr_start, attr_size, count = struct.unpack_from("<3H", data, pos + 24)
            base = pos + 16 + attr_start
            if name >= len(strings) or attr_size < 20 or base < pos + 36 or base + count * attr_size > pos + size:
                raise ValueError("Invalid element attributes")
            if strings[name] in ("manifest", "uses-sdk"):
                for index in range(count):
                    item = base + index * attr_size
                    attr, raw = struct.unpack_from("<2I", data, item + 4)
                    dtype, value = data[item + 15], struct.unpack_from("<I", data, item + 16)[0]
                    if attr >= len(strings):
                        raise ValueError("Invalid attribute name")
                    if raw != 0xFFFFFFFF:
                        if raw >= len(strings):
                            raise ValueError("Invalid attribute value")
                        decoded = strings[raw]
                    elif dtype == 3:
                        if value >= len(strings):
                            raise ValueError("Invalid typed string")
                        decoded = strings[value]
                    elif dtype in (0x10, 0x11):
                        decoded = value
                    else:
                        continue
                    metadata[strings[attr]] = decoded
        pos += size
    package = metadata.get("package", "")
    if not isinstance(package, str) or not PACKAGE_RE.fullmatch(package) or len(package) > 200:
        raise ValueError("APK package name is invalid")
    return metadata


def wrap_spk(apk):
    if not apk or len(apk) > MAX_APK:
        raise PackageError("apk_size")
    number = pow(int.from_bytes(sampleSpkKey, "big"), rsaExponent, rsaModulus)
    key = number.to_bytes((number.bit_length() + 7) // 8, "big")
    if len(key) != 16:
        raise ValueError("Invalid SPK key")
    aes = AES.new(key, AES.MODE_ECB)
    blocks = []
    for pos in range(0, len(apk), blockSize):
        block = apk[pos:pos + blockSize]
        pad = 16 - len(block) % 16
        blocks.append(aes.encrypt(block + bytes([pad]) * pad))
    return struct.pack("<4sII", b"1spk", 0, len(sampleSpkKey)) + sampleSpkKey + b"".join(blocks)


@dataclass(frozen=True)
class AppPackage:
    name: str
    package_name: str
    version: str
    min_sdk: int
    apk_sha256: str
    apk_md5: str
    spk: bytes

    def camera_config(self):
        return {"name": self.name, "package": self.package_name, "version": self.version,
                "minSdk": self.min_sdk, "apkMd5": self.apk_md5, "size": len(self.spk),
                "crc32": zlib.crc32(self.spk), "spkMd5": hashlib.md5(self.spk).hexdigest()}


def prepare_apk(apk, name):
    if len(apk) > MAX_APK:
        raise PackageError("apk_size")
    try:
        with zipfile.ZipFile(io.BytesIO(apk)) as archive:
            entry = archive.getinfo("AndroidManifest.xml")
            if entry.file_size > 2 * 1024 * 1024 or len(archive.infolist()) > 50000:
                raise PackageError("apk_contents")
            metadata = manifest_metadata(archive.read(entry))
    except (zipfile.BadZipFile, KeyError) as error:
        raise PackageError("apk_invalid", detail=str(error)) from error
    try:
        min_sdk = int(metadata.get("minSdkVersion", 1))
    except (ValueError, TypeError) as error:
        raise PackageError("apk_sdk") from error
    return AppPackage(str(name)[:120], metadata["package"], str(metadata.get("versionName", ""))[:100],
                      min_sdk, hashlib.sha256(apk).hexdigest(), hashlib.md5(apk).hexdigest(), wrap_spk(apk))


def download_recipe(progress=lambda *args: None):
    from .download import https_get
    data = https_get(RECIPE_URL, MAX_APK, progress)
    if hashlib.sha256(data).hexdigest() != RECIPE_SHA256:
        raise PackageError("recipe_checksum")
    return prepare_apk(bytes(data), "Recipe Lab")
