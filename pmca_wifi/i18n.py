"""UI text and deferred errors, so switching languages also updates status text."""
import ctypes

LANGUAGES = {"en": "English", "zh-CN": "简体中文"}

# Keep English and Chinese together to make missing translations easy to spot.
MESSAGES = {
    "window": ("Sony Camera App Installer · {version} experimental", "Sony 相机应用安装助手 · {version} 实验版"),
    "title": ("Install camera apps over Wi-Fi", "通过 Wi-Fi，为相机安装应用"),
    "detail": ("Supported Sony PMCA cameras · No USB · No special router", "支持的 Sony PMCA 相机 · 无需 USB · 无需特殊路由器"),
    "steps": ("Choose app → Connect camera → Confirm install → Finish", "选择应用 → 连接相机 → 确认安装 → 完成"),
    "app_label": ("App to install", "安装应用"),
    "choose": ("Choose local APK…", "选择本地 APK…"),
    "recipe": ("Recipe Lab 1.11.1 (original release)", "Recipe Lab 1.11.1（作者原版）"),
    "wifi_label": ("Connect your camera to this Wi-Fi", "相机要连接的 Wi-Fi"),
    "password": ("Password: {password}  (8 digits)", "密码：{password}  （8 位数字）"),
    "instructions": (
        "1. Select Start installation and wait until the hotspot is ready.\n"
        "2. Camera: MENU → Wireless → Access Point Set. Select the Wi-Fi above.\n"
        "3. Open PlayMemories Camera Apps, select Install app and confirm.",
        "① 点击开始，等待热点就绪\n② 相机 MENU → 无线 → 访问点手动设置，选择上面的 Wi-Fi\n"
        "③ 打开 PlayMemories 商店，选择 Install app 并确认安装"),
    "start": ("Start installation", "开始安装"),
    "stop": ("Finish and close hotspot", "结束并关闭热点"),
    "badge": ("Experimental · Tested on A7R II", "实验版 · 已实测 A7R II"),
    "file_title": ("Choose a Sony PMCA-compatible app", "选择 Sony PMCA 兼容应用"),
    "file_type": ("Android app (APK)", "安卓应用 APK"),
    "idle": ("Choose Recipe Lab or open a compatible local APK.", "选择 Recipe Lab，或打开兼容的本地 APK。"),
    "admin": ("Close this window and run the tool as administrator.", "请关闭窗口，以管理员身份重新运行工具。"),
    "preparing": ("Preparing the app and verifying the package…", "正在准备应用并校验安装包…"),
    "network": ("Package verified. Starting the computer's hotspot…", "应用已校验，正在开启电脑热点…"),
    "hotspot": ("Hotspot ready. Connect the camera to the Wi-Fi above, then open PlayMemories Camera Apps.", "热点已就绪。请让相机连接上面的 Wi-Fi，然后打开 PlayMemories 商店。"),
    "ready": ("Camera connected. Select Install app on the camera.", "相机已连接。请在相机选择 Install app。"),
    "downloading": ("Sending the app to the camera. Keep the camera page open…", "正在向相机传输应用，请保持相机页面打开…"),
    "prepared": ("The package on the camera passed verification.", "相机上的安装包校验通过。"),
    "opening": ("Confirm installation on the camera. When it finishes, reopen PlayMemories Camera Apps to verify the result.", "请在相机确认安装。安装结束后，再打开一次 PlayMemories 商店完成核对。"),
    "complete_title": ("Your app is ready", "应用已就绪"),
    "verified": ("Installation verified; the temporary package was removed. Exit the camera store, then select Finish and close hotspot.", "安装已核对，临时安装包已清理。请退出相机商店，再点击结束并关闭热点。"),
    "already_installed": ("This version is already installed. Transfer and file checks passed. Exit the camera store, then select Finish and close hotspot.", "相机已有相同版本，无线传输和文件校验通过。请退出相机商店，再点击结束并关闭热点。"),
    "incomplete": ("Not completed: {message}", "未完成：{message}"),
    "camera_error": ("Check the camera message, then retry or end the connection.", "请查看相机提示，重试或结束连接。"),
    "cleanup": ("Ending the connection and closing the hotspot. Please wait…", "正在结束连接并关闭热点，请稍候…"),
    "stopped": ("Connection ended and hotspot closed. You can close this window.", "连接已结束，热点已关闭，可以关闭此窗口。"),
    "timeout": ("The 40-minute connection limit was reached. Please start again.", "等待超过 40 分钟，已结束本次连接，请重新开始。"),
    "save_language": ("Could not save the language preference: {detail}", "无法保存语言偏好：{detail}"),
    "windows_network": ("Windows network operation failed. {detail}", "Windows 网络操作失败。{detail}"),
    "adapter_missing": ("The computer's hotspot connection was not found. Please try again shortly.", "尚未找到电脑热点的连接，请稍后重试。"),
    "adapter_address": ("The computer's hotspot address is not supported.", "电脑热点的地址不受支持。"),
    "firewall_admin": ("Run the tool as administrator to allow the camera to connect.", "请以管理员身份运行工具，以便允许相机连接。"),
    "legacy_start": ("Windows could not operate this adapter's hotspot. {detail}", "Windows 无法操作此网卡的热点。{detail}"),
    "legacy_active": ("A Hosted Network hotspot is already in use. Close it before trying again.", "电脑的传统热点正在使用中，请先关闭它再重试。"),
    "address_pending": ("The hotspot started, but Windows has not assigned it an address.", "热点已启动，但 Windows 尚未分配连接地址。"),
    "sharing_read": ("Could not read Windows Internet Connection Sharing settings.", "无法读取 Windows 网络共享设置。"),
    "sharing_active": ("Another Internet Connection Sharing session is active. End it before trying again.", "电脑已有其他网络共享连接。请先结束该共享，再重试。"),
    "hotspot_read": ("Could not read the existing hotspot settings (Windows error {code}).", "读取现有热点配置失败（Windows 错误 {code}）。"),
    "internet_required": ("Connect the computer to the internet, then try again.", "请先让电脑连接网络，再重试。"),
    "legacy_adapter": ("The Hosted Network adapter is not ready yet.", "传统热点的网卡尚未就绪。"),
    "cleanup_failed": ("Hotspot cleanup was not completed: {errors}", "热点清理未完成：{errors}"),
    "hotspot_capability": ("Windows cannot create a hotspot with this adapter ({code}).", "Windows 无法使用此网卡开启热点（{code}）。"),
    "mobile_active": ("The computer's mobile hotspot is already in use. Close it before trying again.", "电脑热点正在使用中，请先关闭它再重试。"),
    "mobile_start": ("Could not start the hotspot ({code}): {detail}", "热点启动失败（{code}）：{detail}"),
    "mobile_stop": ("Could not stop the hotspot ({code}). Close it in Windows Settings.", "热点未能关闭（{code}），请在 Windows 设置中关闭热点。"),
    "download_http": ("GitHub download failed (HTTP {code}). You can choose a local APK instead.", "GitHub 下载失败（HTTP {code}）。可改为选择本地 APK。"),
    "download_size": ("The downloaded package is too large.", "下载的应用包过大。"),
    "apk_size": ("The APK is empty or exceeds the 16 MB limit.", "应用包为空或超过 16 MB。"),
    "apk_contents": ("The APK contents exceed the supported limits.", "APK 内容超出支持范围。"),
    "apk_invalid": ("This is not a valid APK package. {detail}", "这不是有效的 APK 应用包。{detail}"),
    "apk_sdk": ("Could not read the APK's Android version requirement.", "APK 的系统版本要求无法读取。"),
    "recipe_checksum": ("Recipe Lab checksum verification failed. Please try again.", "Recipe Lab 校验失败，请重试。"),
}


def system_language():
    try:
        # The primary language ID covers Chinese regional variants.
        return "zh-CN" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3ff == 4 else "en"
    except (AttributeError, OSError):
        return "en"


def text(key, language="en", **params):
    template = MESSAGES[key][1 if language == "zh-CN" else 0]
    return template.format(**{name: error_text(value, language) for name, value in params.items()})


class LocalizedMessage:
    def __init__(self, key, **params):
        self.key, self.params = key, params
        super().__init__(key)

    def render(self, language):
        return text(self.key, language, **self.params)

    def __str__(self):
        return self.render("en")


class UserError(LocalizedMessage, RuntimeError):
    pass


class PackageError(LocalizedMessage, ValueError):
    pass


def error_text(value, language):
    if isinstance(value, LocalizedMessage):
        return value.render(language)
    if isinstance(value, (list, tuple)):
        return "; ".join(error_text(item, language) for item in value)
    return str(value)
