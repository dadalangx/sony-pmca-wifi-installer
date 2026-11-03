# Third-party software

This tool is not affiliated with Sony. Each component retains its original license.

- SPK constants / format: [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE), MIT. Original notice: `licenses/Sony-PMCA-RE-MIT.txt`.
- WinDivert 2.2.2-A: [official binary release](https://github.com/basil00/WinDivert/releases/tag/v2.2.2), used under LGPLv3. Full LGPLv3 / GPL texts are included with the binary. Corresponding source: [v2.2.2 source tree](https://github.com/basil00/WinDivert/tree/v2.2.2) and [source archive](https://github.com/basil00/WinDivert/archive/refs/tags/v2.2.2.zip). The library and signed driver are unmodified. They remain separate files at `_internal/vendor/WinDivert-2.2.2-A/x64/`; users may replace them with compatible versions. This application's license imposes no restriction on debugging modifications to that library.
- [PyCryptodome](https://github.com/Legrandin/pycryptodome): BSD / public-domain components; distributed license included in the Windows build.
- [Python/WinRT](https://github.com/pywinrt/pywinrt): MIT; distributed notices included in the Windows build.
- [Python](https://www.python.org/): PSF license and notices; included in the Windows build.
- [OpenSSL](https://github.com/openssl/openssl): Apache 2.0; the license accompanies the bundled Python runtime libraries in `licenses/OpenSSL-LICENSE.txt`.
- [libffi](https://github.com/libffi/libffi): MIT; notice in `licenses/libffi-LICENSE.txt`.
- Tcl/Tk: original license notices accompany the bundled runtime.
- [PyInstaller](https://pyinstaller.org/): GPL with the bootloader distribution exception; distributed notice included in the Windows build.

Recipe Lab is a separate GPLv3 application. Its APK is not included in this repository or installer distribution. The built-in download points to [the author's v1.11.1 release](https://github.com/voxivoid/recipe-lab-sony-pmca/releases/tag/v1.11.1), with its published SHA-256 pinned in the source. Other APKs are supplied by the user and keep their respective licenses.
