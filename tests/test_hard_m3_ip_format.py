"""Hard mode for Milestone 3: format IP addresses without the ipaddress module.

The tests use ipaddress themselves, as the answer key. Your wire.py must not.
Run with:  pytest tests/test_hard_m3_ip_format.py -v
"""
import inspect
import ipaddress
import random

import pytest

import tinyresolver.wire as wire
from tinyresolver.wire import format_ipv4, format_ipv6


# =====================================================================
# 2. Formatting IP addresses yourself
#
# format_ipv4(raw: bytes) -> str   4 bytes  -> "93.184.215.14"
# format_ipv6(raw: bytes) -> str   16 bytes -> the short form (RFC 5952):
#   - 8 groups of 16 bits, written in lower-case hex with no leading zeros
#   - the LONGEST run of two or more all-zero groups becomes "::"
#   - if two runs tie, the FIRST one is shortened
#   - a single zero group is written as "0", never "::"
# Any other length raises ValueError.
# =====================================================================

def test_wire_does_not_import_ipaddress():
    src = inspect.getsource(wire)
    assert "ipaddress" not in src, "hard mode: format addresses yourself"


@pytest.mark.parametrize(
    "raw, text",
    [
        (bytes([93, 184, 215, 14]), "93.184.215.14"),
        (bytes([0, 0, 0, 0]), "0.0.0.0"),
        (bytes([255, 255, 255, 255]), "255.255.255.255"),
        (bytes([10, 0, 0, 1]), "10.0.0.1"),
    ],
)
def test_format_ipv4(raw, text):
    assert format_ipv4(raw) == text


def v6(text):
    return ipaddress.IPv6Address(text).packed


@pytest.mark.parametrize(
    "groups, expected",
    [
        ("0:0:0:0:0:0:0:0", "::"),
        ("0:0:0:0:0:0:0:1", "::1"),
        ("1:0:0:0:0:0:0:0", "1::"),
        ("2001:db8:0:0:0:0:0:1", "2001:db8::1"),
        ("2001:503:a83e:0:0:0:2:30", "2001:503:a83e::2:30"),
        ("2001:db8:0:1:1:1:1:1", "2001:db8:0:1:1:1:1:1"),      # one zero group: no ::
        ("2001:0:0:1:0:0:0:1", "2001:0:0:1::1"),               # longest run wins
        ("2001:db8:0:0:1:0:0:1", "2001:db8::1:0:0:1"),         # tie: first run wins
        ("2001:0db8:00a0:0000:0000:0abc:0000:0001", "2001:db8:a0::abc:0:1"),
        ("fe80:0:0:0:abcd:ef01:2345:6789", "fe80::abcd:ef01:2345:6789"),
        ("ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"),
    ],
)
def test_format_ipv6_cases(groups, expected):
    assert format_ipv6(v6(groups)) == expected


def test_format_ipv6_matches_the_standard_library_on_random_addresses():
    rng = random.Random(42)
    for _ in range(3_000):
        groups = [0 if rng.random() < 0.45 else rng.randrange(1, 0x10000) for _ in range(8)]
        if groups[:5] == [0] * 5 and groups[5] == 0xFFFF:
            continue   # IPv4-mapped addresses have their own notation; not part of this exercise
        raw = b"".join(g.to_bytes(2, "big") for g in groups)
        assert format_ipv6(raw) == str(ipaddress.IPv6Address(raw)), groups


@pytest.mark.parametrize("bad", [b"", b"\x00" * 3, b"\x00" * 5])
def test_format_ipv4_rejects_wrong_length(bad):
    with pytest.raises(ValueError):
        format_ipv4(bad)


@pytest.mark.parametrize("bad", [b"", b"\x00" * 15, b"\x00" * 17])
def test_format_ipv6_rejects_wrong_length(bad):
    with pytest.raises(ValueError):
        format_ipv6(bad)
