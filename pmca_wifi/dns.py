"""Redirect only Sony store DNS queries arriving on the dedicated hotspot."""
import ctypes as C
import ipaddress
import socket
import struct
import threading
from pathlib import Path

SONY_HOSTS = frozenset({"www.playmemoriescameraapps.com", "playmemoriescameraapps.com"})


def sony_dns_response(query, local_ip):
    """Return an A response / AAAA NODATA; None leaves other queries untouched."""
    if len(query) < 17:
        return None
    ident, flags, questions, _, _, _ = struct.unpack_from("!6H", query)
    if flags & 0xF800 or questions != 1:
        return None
    pos, labels = 12, []
    try:
        while True:
            length = query[pos]
            pos += 1
            if not length:
                break
            if length > 63 or pos + length > len(query) or len(labels) > 10:
                return None
            labels.append(query[pos:pos + length].decode("ascii").lower())
            pos += length
        qtype, qclass = struct.unpack_from("!HH", query, pos)
    except (IndexError, UnicodeError, struct.error):
        return None
    if ".".join(labels) not in SONY_HOSTS or qclass != 1:
        return None
    question = query[12:pos + 4]
    answer = b""
    if qtype == 1:
        answer = struct.pack("!HHHIH", 0xC00C, 1, 1, 0, 4) + socket.inet_aton(local_ip)
    return struct.pack("!6H", ident, 0x8080 | (flags & 0x0100), 1, int(bool(answer)), 0, 0) + question + answer


def redirect_packet(packet, adapter):
    """Construct a reply only for an unfragmented IPv4 UDP Sony query in scope."""
    if len(packet) < 28 or packet[0] >> 4 != 4 or packet[9] != 17:
        return None
    hlen = (packet[0] & 15) * 4
    total = struct.unpack_from("!H", packet, 2)[0]
    if hlen < 20 or total < hlen + 8 or total > len(packet):
        return None
    if struct.unpack_from("!H", packet, 6)[0] & 0x3FFF:
        return None
    source = ipaddress.ip_address(packet[12:16])
    if source not in adapter.network or str(source) == adapter.ip or packet[16:20] != socket.inet_aton(adapter.ip):
        return None
    sport, dport, ulen, _ = struct.unpack_from("!4H", packet, hlen)
    if dport != 53 or ulen < 8 or hlen + ulen != total:
        return None
    answer = sony_dns_response(packet[hlen + 8:total], adapter.ip)
    if answer is None:
        return None
    udp = struct.pack("!4H", 53, sport, 8 + len(answer), 0) + answer
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64, 17, 0,
                         packet[16:20], packet[12:16])
    return header + udp


class Address(C.Structure):
    _fields_ = [("timestamp", C.c_int64), ("flags", C.c_uint32),
                ("reserved", C.c_uint32), ("data", C.c_uint8 * 64)]


class DnsRedirect:
    def __init__(self, adapter, vendor_path, on_event=lambda *args: None):
        self.adapter = adapter
        self.on_event = on_event
        path = Path(vendor_path) / "x64" / "WinDivert.dll"
        self.dll = C.WinDLL(str(path.resolve()), use_last_error=True)
        signatures = {
            "WinDivertOpen": ([C.c_char_p, C.c_int, C.c_int16, C.c_uint64], C.c_void_p),
            "WinDivertRecv": ([C.c_void_p, C.c_void_p, C.c_uint, C.POINTER(C.c_uint), C.POINTER(Address)], C.c_bool),
            "WinDivertSend": ([C.c_void_p, C.c_void_p, C.c_uint, C.POINTER(C.c_uint), C.POINTER(Address)], C.c_bool),
            "WinDivertHelperCalcChecksums": ([C.c_void_p, C.c_uint, C.POINTER(Address), C.c_uint64], C.c_bool),
            "WinDivertShutdown": ([C.c_void_p, C.c_int], C.c_bool),
            "WinDivertClose": ([C.c_void_p], C.c_bool),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes, fn.restype = args, result
        self.handle = None
        self.thread = None
        self.stopping = threading.Event()

    def start(self):
        a = self.adapter
        network = a.network
        filter_ = (f"inbound and ifIdx == {a.index} and ip and udp.DstPort == 53 "
                   f"and ip.DstAddr == {a.ip} and ip.SrcAddr >= {network.network_address} "
                   f"and ip.SrcAddr <= {network.broadcast_address}")
        self.handle = self.dll.WinDivertOpen(filter_.encode("ascii"), 0, 0, 0)
        if self.handle in (None, C.c_void_p(-1).value):
            self.handle = None
            raise C.WinError(C.get_last_error())
        self.thread = threading.Thread(target=self._loop, name="sony-dns", daemon=True)
        self.thread.start()

    def _send(self, packet, address):
        buf = C.create_string_buffer(packet)
        if not self.dll.WinDivertHelperCalcChecksums(buf, len(packet), C.byref(address), 0):
            raise RuntimeError("DNS checksum calculation failed")
        if not self.dll.WinDivertSend(self.handle, buf, len(packet), None, C.byref(address)):
            raise C.WinError(C.get_last_error())

    def _loop(self):
        buf, length, address = C.create_string_buffer(65535), C.c_uint(), Address()
        try:
            while not self.stopping.is_set():
                if not self.dll.WinDivertRecv(self.handle, buf, len(buf), C.byref(length), C.byref(address)):
                    if self.stopping.is_set():
                        break
                    raise C.WinError(C.get_last_error())
                packet = buf.raw[:length.value]
                reply = redirect_packet(packet, self.adapter)
                if reply is None:
                    self._send(packet, address)
                else:
                    address.flags |= 1 << 17  # Outbound injection back to the camera.
                    self._send(reply, address)
                    self.on_event("dns", {"camera": socket.inet_ntoa(packet[12:16])})
        except Exception as error:
            self.on_event("error", {"message": str(error)})
        finally:
            # Closing this handle releases its filters even after worker failure.
            if self.handle:
                self.dll.WinDivertClose(self.handle)
                self.handle = None

    def close(self):
        self.stopping.set()
        if self.handle:
            self.dll.WinDivertShutdown(self.handle, 1)  # WINDIVERT_SHUTDOWN_RECV.
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                if self.handle:
                    self.dll.WinDivertClose(self.handle)
                    self.handle = None
                self.thread.join(timeout=2)
                if self.thread.is_alive():
                    raise RuntimeError("DNS forwarding did not stop in time")
