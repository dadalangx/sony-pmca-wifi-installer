"""HTTPS through Windows WinHTTP, using Windows TLS and certificate validation."""
import ctypes as C
from urllib.parse import urlsplit


def https_get(url, max_size, progress=lambda *args: None):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Only HTTPS downloads are supported")
    api = C.WinDLL("winhttp", use_last_error=True)
    handle = C.c_void_p
    signatures = {
        "WinHttpOpen": ([C.c_wchar_p, C.c_uint32, C.c_wchar_p, C.c_wchar_p, C.c_uint32], handle),
        "WinHttpConnect": ([handle, C.c_wchar_p, C.c_uint16, C.c_uint32], handle),
        "WinHttpOpenRequest": ([handle, C.c_wchar_p, C.c_wchar_p, C.c_wchar_p, C.c_wchar_p, C.c_void_p, C.c_uint32], handle),
        "WinHttpSetTimeouts": ([handle, C.c_int, C.c_int, C.c_int, C.c_int], C.c_int),
        "WinHttpSendRequest": ([handle, C.c_wchar_p, C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32, C.c_size_t], C.c_int),
        "WinHttpReceiveResponse": ([handle, C.c_void_p], C.c_int),
        "WinHttpQueryHeaders": ([handle, C.c_uint32, C.c_wchar_p, C.c_void_p, C.POINTER(C.c_uint32), C.c_void_p], C.c_int),
        "WinHttpReadData": ([handle, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32)], C.c_int),
        "WinHttpCloseHandle": ([handle], C.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result
    handles = []
    def checked(value):
        if not value:
            raise C.WinError(C.get_last_error())
        return value
    try:
        session = checked(api.WinHttpOpen("SonyPmcaWifiInstaller/0.1", 4, None, None, 0))
        handles.append(session)
        checked(api.WinHttpSetTimeouts(session, 10000, 10000, 10000, 30000))
        connection = checked(api.WinHttpConnect(session, parts.hostname, parts.port or 443, 0))
        handles.append(connection)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        request = checked(api.WinHttpOpenRequest(connection, "GET", path, None, None, None, 0x00800000))
        handles.append(request)
        checked(api.WinHttpSendRequest(request, None, 0, None, 0, 0, 0))
        checked(api.WinHttpReceiveResponse(request, None))
        status, size = C.c_uint32(), C.c_uint32(4)
        checked(api.WinHttpQueryHeaders(request, 19 | 0x20000000, None, C.byref(status), C.byref(size), None))
        if status.value != 200:
            raise RuntimeError(f"GitHub 下载失败（HTTP {status.value}）。可改为选择本地 APK。")
        total, size = C.c_uint32(), C.c_uint32(4)
        if not api.WinHttpQueryHeaders(request, 5 | 0x20000000, None, C.byref(total), C.byref(size), None):
            total.value = 0
        if total.value > max_size:
            raise ValueError("下载的应用包过大。")
        buffer, count, result = C.create_string_buffer(65536), C.c_uint32(), bytearray()
        while True:
            checked(api.WinHttpReadData(request, buffer, len(buffer), C.byref(count)))
            if not count.value:
                break
            result.extend(buffer.raw[:count.value])
            if len(result) > max_size:
                raise ValueError("下载的应用包过大。")
            progress(len(result), total.value)
        return bytes(result)
    finally:
        for item in reversed(handles):
            api.WinHttpCloseHandle(item)
