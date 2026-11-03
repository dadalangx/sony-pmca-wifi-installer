# Sony PMCA Wi-Fi Installer

**USB 接口坏了，也能通过 Wi-Fi 给支持的 Sony PMCA 相机安装应用。**

Windows 中文图形向导，支持下载 Recipe Lab 或选择本地兼容 APK。电脑自动创建热点并处理安装所需的网络连接；使用者不需要 OpenWrt、路由器账号、IP 地址或 DNS 知识。

当前版本：**0.1.0 实验版**。已在一台 Sony A7R II 上，用打包后的 Windows EXE 完成 Recipe Lab 安装、安装文件校验及临时包清理。

## 如何使用

1. 下载 Windows x64 ZIP，**完整解压**到一个文件夹。不要在压缩包里直接运行，也不要单独移动 EXE。
2. 双击 `SonyPmcaWifiInstaller.exe`，确认 Windows 管理员权限提示。
3. 使用默认的 Recipe Lab，或点击“选择本地 APK”，然后点击“开始安装”。
4. 等待“热点已就绪”。在相机 **MENU → 无线 → 访问点手动设置**中，选择窗口显示的 Wi-Fi，输入显示的 8 位数字密码。“优先连接”设为开，“IP 地址设置”保持自动。
5. 打开相机 **应用程序列表 → PlayMemories Camera Apps／应用程序下载**。在安装页面选择 `Install app`，按相机原生安装提示确认。
6. 安装完成后，**再打开一次 PlayMemories 商店**，等待校验完成。退出相机商店，再点击电脑上的“结束并关闭热点”。

电脑可以用网线上网，但需要一张能够开启热点的无线网卡。不需要给相机连接 USB。普通使用者不需要安装 Python。

工具保存自己生成的 Wi-Fi 名称和数字密码，方便下次连接；凭据使用 Windows DPAPI 加密，只保存在本机用户目录。

## 应用来源

- 默认下载 [Recipe Lab 作者发布的 v1.11.1 原版 APK](https://github.com/voxivoid/recipe-lab-sony-pmca/releases/tag/v1.11.1)，并核对作者发布的 SHA-256。
- 本地 APK 必须是为 Sony PMCA 相机制作的兼容应用，当前大小上限 16 MB。普通安卓手机应用不能直接视为兼容。
- 本工具不内置或修改 Recipe Lab APK，也不提供 Sony 付费应用包。

## 实测范围

| 项目 | 结果 |
| --- | --- |
| 相机 | Sony A7R II，一台实机；固件版本未记录；机内 Android API 16 |
| 电脑 | Windows 10 x64，系统版本 19045 |
| 无线网卡 | Ralink/MediaTek USB 网卡，VID 148F / PID 760B，驱动 5.1.22.0 |
| 传统 Hosted Network 热点 | EXE 已完成 Recipe Lab 安装、安装后校验和临时包清理 |
| 上述网卡的 Windows 移动热点 | 手机可上网，相机商店连接失败；工具优先选择可用的传统热点 |
| Windows 11、其他网卡、其他机型／固件 | 尚未实机验证 |
| 其他 PMCA APK | 已实现通用封装与选择入口，尚未逐个实机测试 |

这是小范围实测的实验版，请不要描述为“所有 Sony 相机通用”。工具检查 APK 的系统版本要求；最终兼容性仍取决于应用、机型和固件。

## 常见问题

**无法开启热点**：确认无线网卡已插入、驱动已安装，并关闭其他正在使用的电脑热点。工具不会接管其他应用正在使用的热点或网络共享。

**相机找不到可连接的接入点**：重新选择工具显示的 Wi-Fi，检查数字密码、优先连接及自动 IP 设置。保存后可将相机关机 5 秒再开机。部分网卡的移动热点模式与旧相机不兼容。

**GitHub 下载失败**：可以自行从作者的 release 下载 APK，再使用“选择本地 APK”。下载使用 Windows HTTPS，未关闭证书校验。

**安装完仍在等待**：原生安装器会暂停浏览器，请按第 6 步重新打开商店，让工具读取安装结果并清理临时包。

**意外退出或中途拔掉网卡**：当前版本只有正常退出及异常处理路径的自动清理，尚无跨进程崩溃恢复。安装过程中不要强制结束程序或拔掉网卡；若有残留热点／共享，需要在 Windows 中结束该共享后重试。

本机设置和错误记录保存在 `%LOCALAPPDATA%\SonyPmcaWifiInstaller`。日志与凭据不应上传到仓库。

## 从源码运行／构建

使用 Windows x64、Python 3.12。开发机需要以管理员身份运行安装程序。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/fetch_vendor.py
.\.venv\Scripts\python.exe main.py
```

打包及生成发布文件：

```powershell
.\.venv\Scripts\python.exe build.py
.\.venv\Scripts\python.exe scripts/pack_release.py
```

产物在 `dist/` 和 `releases/`。GitHub Actions 可手动构建；推送版本标签会生成草稿 release，由维护者检查后发布。打包器下载固定版本的官方 WinDivert 并校验归档 SHA-256，运行时使用未修改的签名驱动。

## 原理与来源

相机商店先请求固定的 HTTP 入口。工具只在自己创建的热点范围内解析该商店域名，从入口重定向到安装页面，使用已在这台相机上验证的旧浏览器接口传输 SPK，并调用相机原生安装器。校验通过后删除本次临时 SPK；正常结束时移除自己的防火墙规则、停止转发并关闭热点。

页面提供固定的安装流程，不提供任意命令或任意文件读写接口。工具不修改相机固件，也不设置全网 DNS。

- [Sony-PMCA-RE：应用安装协议](https://github.com/ma1co/Sony-PMCA-RE/blob/master/docs/AppInstallation.md)
- [Sony-PMCA-RE：SPK 格式实现](https://github.com/ma1co/Sony-PMCA-RE/tree/master/pmca/spk)
- [OpenMemories AppStore：原生安装器调用](https://github.com/ma1co/OpenMemories-AppStore)
- [Recipe Lab](https://github.com/voxivoid/recipe-lab-sony-pmca)
- [WinDivert](https://reqrypt.org/windivert-doc.html)

本项目原始代码采用 MIT；SPK 常量保留 ma1co 的 MIT 声明。各依赖和第三方应用分别适用其许可证，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。本项目与 Sony 无隶属关系。
