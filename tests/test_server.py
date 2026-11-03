import http.client

from pmca_wifi.package import AppPackage
from pmca_wifi.server import InstallerServer
from pmca_wifi.windows import HotspotAdapter


def server():
    app = AppPackage("Test", "com.example.test", "1", 10, "a" * 64, "b" * 32, b"checked-package")
    return InstallerServer(HotspotAdapter("127.0.0.1", 8, 1), app, port=0)


def test_head_redirect_origin_session_and_camera_gating():
    service = server()
    service.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", service.http.server_port)
        conn.request("HEAD", "/portal/noauth/blank.htm")
        reply = conn.getresponse()
        assert reply.status == 302 and reply.getheader("Location").startswith("/s/")
        assert reply.read() == b""
        conn = http.client.HTTPConnection("127.0.0.1", service.http.server_port)
        conn.request("GET", service.prefix + "/")
        assert conn.getresponse().status == 403
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", service.http.server_port)
        conn.request("GET", service.prefix + "/", headers={"User-Agent": "sccamera Build/S"})
        reply = conn.getresponse()
        assert reply.status == 200 and b"window.CFG" in reply.read()
        conn.close()
    finally:
        service.close()


def test_does_not_report_success_for_launch_or_existing_package_path():
    service = server()
    assert service.report("verified", {"md5": "b" * 32, "cleaned": True})  # valid checked existing version
    service = server()
    assert service.report("downloading", {})
    assert service.report("prepared", {})
    assert service.report("opening", {})
    assert service.phase == "installing"
    assert not service.report("verified", {"path": "package:/data/app/existing.apk"})
    assert not service.report("verified", {"md5": "a" * 32, "cleaned": True})
    assert not service.report("verified", {"md5": "b" * 32, "cleaned": False})
    assert service.phase == "installing"
    assert service.report("verified", {"md5": "b" * 32, "cleaned": True})
    assert service.phase == "done"
    assert not service.report("exec", {"command": "anything"})
