"""Fetch the unmodified official WinDivert archive; verify before use."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/basil00/WinDivert/releases/download/v2.2.2/WinDivert-2.2.2-A.zip"
SHA256 = "63cb41763bb4b20f600b6de04e991a9c2be73279e317d4d82f237b150c5f3f15"


def main():
    data = urllib.request.urlopen(URL, timeout=30).read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("Official WinDivert archive checksum did not match")
    vendor = ROOT / "vendor" / "WinDivert-2.2.2-A"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in ("x64/WinDivert.dll", "x64/WinDivert64.sys", "LICENSE", "README", "VERSION"):
            dest = vendor / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = archive.read("WinDivert-2.2.2-A/" + name)
            if not dest.exists() or dest.read_bytes() != content:
                dest.write_bytes(content)
    print("WinDivert 2.2.2-A verified and prepared.")


if __name__ == "__main__":
    main()
