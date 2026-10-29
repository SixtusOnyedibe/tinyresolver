"""Milestone 1: turning Python values into DNS bytes.

Run just this file with:  pytest tests/test_m1_encode.py -v
"""
from enum import IntEnum

import pytest

from tinyresolver.errors import DNSError, DNSFormatError, NXDomainError, ResolutionError
from tinyresolver.wire import (
    CLASS_IN,
    FLAG_AA,
    FLAG_QR,
    FLAG_RA,
    FLAG_RD,
    FLAG_TC,
    Header,
    Question,
    RecordType,
    build_query,
    encode_name,
)


# ---------- errors.py ----------

def test_error_classes_share_one_base():
    for cls in (DNSFormatError, NXDomainError, ResolutionError):
        assert issubclass(cls, DNSError)
    assert issubclass(DNSError, Exception)


# ---------- constants ----------

def test_record_type_is_an_int_enum():
    assert issubclass(RecordType, IntEnum)
    assert RecordType.A == 1
    assert RecordType.NS == 2
    assert RecordType.CNAME == 5
    assert RecordType.SOA == 6
    assert RecordType.TXT == 16
    assert RecordType.AAAA == 28


def test_record_type_lookup_by_name_and_value():
    assert RecordType["AAAA"] == 28
    assert RecordType(5).name == "CNAME"


def test_class_and_flag_constants():
    assert CLASS_IN == 1
    assert FLAG_QR == 0x8000
    assert FLAG_AA == 0x0400
    assert FLAG_TC == 0x0200
    assert FLAG_RD == 0x0100
    assert FLAG_RA == 0x0080


# ---------- encode_name ----------

@pytest.mark.parametrize(
    "name, expected",
    [
        ("example.com", b"\x07example\x03com\x00"),
        ("example.com.", b"\x07example\x03com\x00"),
        ("a", b"\x01a\x00"),
        ("www.python.org", b"\x03www\x06python\x03org\x00"),
        ("", b"\x00"),
        (".", b"\x00"),
    ],
)
def test_encode_name(name, expected):
    assert encode_name(name) == expected


def test_encode_name_keeps_case():
    assert encode_name("ExAmple.COM") == b"\x07ExAmple\x03COM\x00"


def test_encode_name_accepts_63_byte_label():
    label = "a" * 63
    assert encode_name(label + ".com") == bytes([63]) + label.encode() + b"\x03com\x00"


@pytest.mark.parametrize(
    "bad",
    [
        "a..b",                       # empty label in the middle
        ".example.com",               # empty first label
        "a" * 64 + ".com",            # label longer than 63 bytes
        ".".join(["a" * 63] * 4),     # 257 bytes once encoded, limit is 255
    ],
)
def test_encode_name_rejects_bad_names(bad):
    with pytest.raises(ValueError):
        encode_name(bad)


# ---------- Header ----------

def test_header_to_bytes():
    h = Header(id=0x1234, flags=0x0100, qdcount=1)
    assert h.to_bytes() == bytes.fromhex("123401000001000000000000")


def test_header_defaults_are_zero():
    h = Header(id=7)
    assert (h.flags, h.qdcount, h.ancount, h.nscount, h.arcount) == (0, 0, 0, 0, 0)
    assert len(h.to_bytes()) == 12


def test_header_round_trip():
    h = Header(id=0xBEEF, flags=0x8180, qdcount=1, ancount=3, nscount=2, arcount=4)
    assert Header.from_bytes(h.to_bytes()) == h


def test_header_from_bytes_ignores_extra_bytes():
    raw = Header(id=1, flags=2, qdcount=3).to_bytes() + b"trailing junk"
    assert Header.from_bytes(raw) == Header(id=1, flags=2, qdcount=3)


def test_header_from_short_bytes_raises_format_error():
    with pytest.raises(DNSFormatError):
        Header.from_bytes(b"\x00" * 11)


def test_header_rcode_is_low_four_bits_of_flags():
    assert Header(id=1, flags=0x8183).rcode == 3
    assert Header(id=1, flags=0x8180).rcode == 0
    assert Header(id=1, flags=0x8182).rcode == 2


# ---------- Question ----------

def test_question_to_bytes():
    q = Question("example.com", RecordType.A)
    assert q.qclass == CLASS_IN
    assert q.to_bytes() == b"\x07example\x03com\x00" + b"\x00\x01\x00\x01"


def test_question_aaaa():
    q = Question("a.io", RecordType.AAAA)
    assert q.to_bytes() == b"\x01a\x02io\x00\x00\x1c\x00\x01"


# ---------- build_query ----------

def test_build_query_matches_real_dig_packet():
    expected = bytes.fromhex(
        "1a2b01000001000000000000"            # header: id, RD flag, 1 question
        "076578616d706c6503636f6d00"          # example.com
        "00010001"                            # type A, class IN
    )
    assert build_query("example.com", RecordType.A, 0x1A2B) == expected


def test_build_query_without_recursion_desired():
    packet = build_query("example.com", RecordType.NS, 0x0001, recursion_desired=False)
    assert packet[2:4] == b"\x00\x00"
    assert packet[-4:] == b"\x00\x02\x00\x01"


def test_build_query_returns_bytes():
    assert isinstance(build_query("x.org", 1, 9), bytes)
