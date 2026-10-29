"""Milestone 3: turning DNS bytes back into Python objects.

The decode_name tests are the algorithm part. Read the comment above each
packet and trace the bytes by hand before you write any code.
"""
import threading

import pytest

from tests.fixtures import CNAME_CHAIN, EXAMPLE_A, NXDOMAIN, ROOT_REFERRAL
from tinyresolver.errors import DNSFormatError
from tinyresolver.wire import (
    FLAG_QR,
    FLAG_RD,
    Header,
    Message,
    Question,
    Record,
    RecordType,
    build_query,
    decode_name,
    parse_message,
)


def finishes_within(seconds, fn):
    """Run fn in a thread. Fail the test if it is still running after `seconds`."""
    outcome = {}

    def target():
        try:
            outcome["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - we want to hand any error back
            outcome["error"] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    assert not t.is_alive(), f"still running after {seconds}s: probably an infinite loop"
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


# ---------- decode_name: plain labels ----------

def test_decode_plain_name():
    data = b"\x07example\x03com\x00"
    assert decode_name(data, 0) == ("example.com", 13)


def test_decode_root_name():
    assert decode_name(b"\x00", 0) == ("", 1)


def test_decode_from_a_middle_offset():
    data = b"JUNK\x03www\x00MORE"
    assert decode_name(data, 4) == ("www", 9)


# ---------- decode_name: compression pointers ----------
#
#   offset: 0         5                    15                21
#           03 c o m 00 | 07 e x a m p l e c0 00 | 03 w w w c0 05 | c0 0f
#
PACKED = b"\x03com\x00" + b"\x07example\xc0\x00" + b"\x03www\xc0\x05" + b"\xc0\x0f"


def test_decode_label_then_pointer():
    # "example" then jump to offset 0 for "com". The name ends 2 bytes after the pointer.
    assert decode_name(PACKED, 5) == ("example.com", 15)


def test_decode_pointer_to_a_name_that_has_a_pointer():
    assert decode_name(PACKED, 15) == ("www.example.com", 21)


def test_decode_name_that_is_only_a_pointer():
    assert decode_name(PACKED, 21) == ("www.example.com", 23)


def test_pointer_to_itself_raises():
    with pytest.raises(DNSFormatError):
        finishes_within(2, lambda: decode_name(b"\xc0\x00", 0))


def test_two_pointers_pointing_at_each_other_raise():
    # offset 0: label "a", then pointer to 4.  offset 4: label "b", then pointer to 0.
    data = b"\x01a\xc0\x04\x01b\xc0\x00"
    with pytest.raises(DNSFormatError):
        finishes_within(2, lambda: decode_name(data, 0))


@pytest.mark.parametrize(
    "data",
    [
        b"\x05ab",          # label says 5 bytes, only 2 left
        b"\x03com",         # never reaches the 0 terminator
        b"\xc0\x50",        # pointer to offset 80, past the end
        b"\xc0",            # pointer cut in half
        b"\x40abc\x00",     # 0x40 and 0x80 label types are reserved
        b"",
    ],
)
def test_malformed_names_raise_format_error(data):
    with pytest.raises(DNSFormatError):
        finishes_within(2, lambda: decode_name(data, 0))


# ---------- parse_message ----------

def test_parse_simple_answer():
    msg = parse_message(EXAMPLE_A)
    assert isinstance(msg, Message)
    assert msg.header == Header(id=0x1A2B, flags=0x8180, qdcount=1, ancount=1, nscount=0, arcount=0)
    assert msg.questions == [Question("example.com", RecordType.A, 1)]
    assert msg.answers == [Record("example.com", RecordType.A, 1, 3600, "93.184.215.14")]
    assert msg.authorities == []
    assert msg.additionals == []


def test_parse_cname_chain():
    msg = parse_message(CNAME_CHAIN)
    cname, *addresses = msg.answers
    assert cname == Record("www.python.org", RecordType.CNAME, 1, 3600, "dualstack.python.map.fastly.net")
    assert len(addresses) == 2
    assert {r.data for r in addresses} == {"151.101.0.223", "151.101.64.223"}
    for r in addresses:
        assert r.name == "dualstack.python.map.fastly.net"
        assert r.rtype == RecordType.A
        assert r.ttl == 30


def test_parse_root_referral():
    msg = parse_message(ROOT_REFERRAL)
    assert msg.header.flags & FLAG_QR
    assert msg.answers == []
    # records come out in the order they sit in the packet
    assert [r.data for r in msg.authorities] == ["b.gtld-servers.net", "a.gtld-servers.net"]
    assert all(r.name == "com" and r.rtype == RecordType.NS for r in msg.authorities)

    glue = {(r.name, r.rtype): r.data for r in msg.additionals}
    assert glue == {
        ("a.gtld-servers.net", RecordType.A): "192.5.6.30",
        ("b.gtld-servers.net", RecordType.A): "192.33.14.30",
        ("a.gtld-servers.net", RecordType.AAAA): "2001:503:a83e::2:30",
    }


def test_parse_nxdomain_keeps_unknown_rdata_as_bytes():
    msg = parse_message(NXDOMAIN)
    assert msg.header.rcode == 3
    assert msg.answers == []
    (soa,) = msg.authorities
    assert soa.name == "example.com"
    assert soa.rtype == RecordType.SOA
    assert soa.ttl == 3600
    assert isinstance(soa.data, bytes)
    assert len(soa.data) == 44     # raw RDATA bytes, exactly as on the wire (compression and all)


def test_parse_your_own_query():
    msg = parse_message(build_query("stage.example", RecordType.AAAA, 7))
    assert msg.header.id == 7
    assert msg.header.flags & FLAG_RD
    assert msg.questions == [Question("stage.example", RecordType.AAAA, 1)]
    assert msg.answers == msg.authorities == msg.additionals == []


def test_message_lists_are_not_shared():
    a = Message(header=Header(id=1))
    b = Message(header=Header(id=2))
    a.answers.append("x")
    assert b.answers == [], "use dataclasses.field(default_factory=list), not = []"


@pytest.mark.parametrize("cut", [3, 11, 20, 30, 40, 44])
def test_truncated_packets_raise_format_error(cut):
    with pytest.raises(DNSFormatError):
        parse_message(EXAMPLE_A[:cut])
