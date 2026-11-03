import socket
import struct

from pmca_wifi.dns import sony_dns_response, redirect_packet
from pmca_wifi.windows import HotspotAdapter


def query(host="www.playmemoriescameraapps.com", qtype=1):
    name = b"".join(bytes([len(x)]) + x.encode() for x in host.split(".")) + b"\0"
    return struct.pack("!6H", 321, 0x0100, 1, 0, 0, 0) + name + struct.pack("!HH", qtype, 1)


def packet(payload, source="192.168.137.2", target="192.168.137.1"):
    udp = struct.pack("!4H", 54321, 53, 8 + len(payload), 0) + payload
    return struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64, 17, 0,
                       socket.inet_aton(source), socket.inet_aton(target)) + udp


def test_only_sony_query_is_redirected():
    response = sony_dns_response(query(), "192.168.137.1")
    assert response[-4:] == socket.inet_aton("192.168.137.1")
    assert struct.unpack_from("!6H", response) == (321, 0x8180, 1, 1, 0, 0)
    assert sony_dns_response(query("example.org"), "192.168.137.1") is None


def test_aaaa_has_no_unreachable_external_answer():
    response = sony_dns_response(query(qtype=28), "192.168.137.1")
    assert struct.unpack_from("!6H", response)[3] == 0


def test_bad_queries_do_not_crash_or_intercept():
    for bad in (b"", query()[:15], query()[:-1], query()[:12] + b"\xc0\x0c\0\x01\0\x01"):
        assert sony_dns_response(bad, "192.168.137.1") is None


def test_packet_scope_and_reply_addresses():
    adapter = HotspotAdapter("192.168.137.1", 24, 11)
    response = redirect_packet(packet(query()), adapter)
    assert response[12:20] == socket.inet_aton(adapter.ip) + socket.inet_aton("192.168.137.2")
    assert struct.unpack_from("!HH", response, 20) == (53, 54321)
    assert redirect_packet(packet(query(), source="198.51.100.10"), adapter) is None
    assert redirect_packet(packet(query(), target="198.51.100.1"), adapter) is None
    assert redirect_packet(packet(query())[:-1], adapter) is None
    fragmented = bytearray(packet(query()))
    fragmented[6] = 0x20
    assert redirect_packet(bytes(fragmented), adapter) is None
