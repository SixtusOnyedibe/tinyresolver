"""Milestone 2: sending bytes over UDP and getting bytes back.

These tests start a tiny fake server on your own machine, so they work offline.
The last test talks to Google's real DNS server, and only runs if you ask:

    TINYRESOLVER_LIVE=1 pytest tests/test_m2_transport.py -v     (macOS/Linux)
    set TINYRESOLVER_LIVE=1 && pytest tests/test_m2_transport.py -v   (Windows cmd)
"""
import os
import socket
import threading
import time

import pytest

from tinyresolver.transport import send_udp
from tinyresolver.wire import build_query


def start_fake_server(reply):
    """Bind a UDP socket on a free local port. Returns (port, socket).

    reply(data) -> bytes | None.  None means "stay silent".
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(5)

    def serve():
        try:
            data, addr = sock.recvfrom(4096)
        except OSError:
            return
        answer = reply(data)
        if answer is not None:
            sock.sendto(answer, addr)

    threading.Thread(target=serve, daemon=True).start()
    return sock.getsockname()[1], sock


def test_send_udp_returns_the_reply():
    port, sock = start_fake_server(lambda data: b"pong:" + data)
    try:
        assert send_udp(b"hello", "127.0.0.1", port=port, timeout=2) == b"pong:hello"
    finally:
        sock.close()


def test_send_udp_sends_the_exact_packet():
    received = []

    def reply(data):
        received.append(data)
        return b"ok"

    packet = build_query("example.com", 1, 0x1A2B)
    port, sock = start_fake_server(reply)
    try:
        send_udp(packet, "127.0.0.1", port=port, timeout=2)
    finally:
        sock.close()
    assert received == [packet]


def test_send_udp_handles_large_replies():
    big = bytes(range(256)) * 12          # 3072 bytes, bigger than the classic 512 limit
    port, sock = start_fake_server(lambda data: big)
    try:
        assert send_udp(b"x", "127.0.0.1", port=port, timeout=2) == big
    finally:
        sock.close()


def test_send_udp_times_out():
    port, sock = start_fake_server(lambda data: None)
    try:
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            send_udp(b"anyone there?", "127.0.0.1", port=port, timeout=0.3)
        assert time.monotonic() - start < 2, "timeout argument was ignored"
    finally:
        sock.close()


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("TINYRESOLVER_LIVE") != "1", reason="set TINYRESOLVER_LIVE=1 to run")
def test_live_google_dns_answers():
    reply = send_udp(build_query("example.com", 1, 0x4242), "8.8.8.8", timeout=3)
    assert reply[:2] == b"\x42\x42", "reply id must match the query id"
    assert reply[2] & 0x80, "QR bit must be set in a response"
