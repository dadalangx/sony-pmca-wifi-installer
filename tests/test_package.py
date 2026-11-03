import hashlib
import struct

import pytest
from Cryptodome.Cipher import AES
from pmca_wifi.package import manifest_metadata, wrap_spk
from pmca_wifi.spk_constants import rsaModulus, rsaExponent, blockSize


def manifest(package="com.example.camera", utf8=True):
    strings = ["manifest", "package", package, "versionName", "1.2"]
    encoded = []
    for value in strings:
        raw = value.encode("utf-8" if utf8 else "utf-16-le")
        encoded.append((bytes([len(value), len(raw)]) + raw + b"\0") if utf8
                       else struct.pack("<H", len(value)) + raw + b"\0\0")
    offsets, pos = [], 0
    for raw in encoded:
        offsets.append(pos)
        pos += len(raw)
    content = b"".join(encoded)
    content += b"\0" * (-len(content) % 4)
    start = 28 + len(strings) * 4
    pool = struct.pack("<HHI5I", 1, 28, start + len(content), len(strings), 0, 0x100 if utf8 else 0, start, 0)
    pool += struct.pack("<" + "I" * len(offsets), *offsets) + content
    attrs = b""
    for name, value in ((1, 2), (3, 4)):
        attrs += struct.pack("<IIIHBBI", 0xFFFFFFFF, name, value, 8, 0, 3, value)
    element = struct.pack("<HHIII", 0x102, 16, 36 + len(attrs), 1, 0xFFFFFFFF)
    element += struct.pack("<II6H", 0xFFFFFFFF, 0, 20, 20, 2, 0, 0, 0) + attrs
    return struct.pack("<HHI", 3, 8, 8 + len(pool) + len(element)) + pool + element


@pytest.mark.parametrize("utf8", [True, False])
def test_android_binary_manifest_strings(utf8):
    metadata = manifest_metadata(manifest(utf8=utf8))
    assert metadata["package"] == "com.example.camera"
    assert metadata["versionName"] == "1.2"


def test_manifest_rejects_command_in_package_and_bad_bounds():
    with pytest.raises(ValueError):
        manifest_metadata(manifest("com.example;echo BAD"))
    original = manifest()
    for end in (0, 7, len(original) - 1):
        with pytest.raises(ValueError):
            manifest_metadata(original[:end])
    corrupt = bytearray(original)
    struct.pack_into("<I", corrupt, 8 + 20, 0xFFFFFFFF)
    with pytest.raises(ValueError):
        manifest_metadata(bytes(corrupt))


@pytest.mark.parametrize("size", [1, 16, blockSize, blockSize + 17])
def test_spk_is_recoverable_by_upstream_format(size):
    apk = (bytes(range(256)) * ((size + 255) // 256))[:size]
    wrapped = wrap_spk(apk)
    magic, offset, length = struct.unpack_from("<4sII", wrapped)
    assert (magic, offset, length) == (b"1spk", 0, 256)
    number = pow(int.from_bytes(wrapped[12:12 + length], "big"), rsaExponent, rsaModulus)
    cipher = AES.new(number.to_bytes(16, "big"), AES.MODE_ECB)
    ciphertext = wrapped[12 + length:]
    decoded = bytearray()
    # Upstream decryption treats each padded 1 MB source block separately.
    for pos in range(0, len(ciphertext), blockSize + 16):
        block = cipher.decrypt(ciphertext[pos:pos + blockSize + 16])
        pad = block[-1]
        assert 1 <= pad <= 16 and block[-pad:] == bytes([pad]) * pad
        decoded.extend(block[:-pad])
    assert hashlib.sha256(decoded).digest() == hashlib.sha256(apk).digest()
