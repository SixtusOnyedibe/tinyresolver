"""Milestone 5: the iterative resolver. This is the main algorithm of the project.

Open tests/fakenet.py first and read the map at the top. Every test here
resolves names against that pretend internet, never the real one.
"""
import os

import pytest

from tests.fakenet import COM, EXAMPLE, ROOT, FakeNet
from tinyresolver.errors import NXDomainError, ResolutionError
from tinyresolver.resolver import ROOT_SERVERS, Resolver, network_query
from tinyresolver.wire import RecordType


def make(**kwargs):
    fake = FakeNet()
    kwargs.setdefault("root_servers", [ROOT])
    return fake, Resolver(query_fn=fake, **kwargs)


def datas(records, rtype=RecordType.A):
    return [r.data for r in records if r.rtype == rtype]


def test_defaults():
    r = Resolver()
    assert r.query_fn is network_query
    assert r.cache is None
    assert r.max_queries == 40
    assert len(ROOT_SERVERS) >= 3
    assert r.root_servers == ROOT_SERVERS


def test_follows_referrals_from_root_down():
    fake, r = make()
    result = r.resolve("example.com", RecordType.A)
    assert datas(result) == ["93.184.215.14"]
    assert fake.servers_asked == [ROOT, COM, EXAMPLE]


def test_qtype_defaults_to_a():
    fake, r = make()
    assert datas(r.resolve("example.com")) == ["93.184.215.14"]


def test_name_is_case_and_dot_insensitive():
    fake, r = make()
    assert datas(r.resolve("Example.COM.")) == ["93.184.215.14"]


def test_cname_answered_in_the_same_response():
    fake, r = make()
    result = r.resolve("www.example.com")
    assert [x.rtype for x in result] == [RecordType.CNAME, RecordType.A]
    assert result[0].data == "example.com"
    assert result[-1].data == "93.184.215.14"
    assert len(fake.calls) == 3, "the A record was already in the answer, no need to ask again"


def test_cname_into_another_zone_restarts_from_root():
    fake, r = make()
    result = r.resolve("alias.example.com")
    assert result[0].rtype == RecordType.CNAME
    assert result[0].data == "target.example.org"
    assert datas(result) == ["10.9.9.9"]
    assert fake.servers_asked.count(ROOT) == 2


def test_asking_for_cname_itself_does_not_follow_it():
    fake, r = make()
    result = r.resolve("alias.example.com", RecordType.CNAME)
    assert [(x.rtype, x.data) for x in result] == [(RecordType.CNAME, "target.example.org")]


def test_glueless_referral_looks_up_the_nameserver_first():
    fake, r = make()
    result = r.resolve("glueless.com")
    assert datas(result) == ["10.7.7.7"]
    assert ("10.5.0.1", "ns.provider.net", 1) in fake.calls
    assert fake.calls[-1] == ("10.6.0.1", "glueless.com", 1)


def test_nxdomain_raises():
    fake, r = make()
    with pytest.raises(NXDomainError):
        r.resolve("does-not-exist.com")


def test_nodata_returns_empty_list():
    fake, r = make()
    assert r.resolve("nodata.example.com", RecordType.AAAA) == []


def test_cname_loop_raises_resolution_error():
    fake, r = make()
    with pytest.raises(ResolutionError):
        r.resolve("loop1.example.com")
    assert len(fake.calls) <= r.max_queries


def test_referral_loop_is_stopped_by_query_budget():
    fake, r = make(max_queries=15)
    with pytest.raises(ResolutionError):
        r.resolve("www.trap.com")
    assert len(fake.calls) <= 15


def test_budget_includes_nested_nameserver_lookups():
    # glueless.com needs 6 queries in total, 3 of them to find ns.provider.net
    fake, r = make(max_queries=5)
    with pytest.raises(ResolutionError):
        r.resolve("glueless.com")
    assert len(fake.calls) <= 5


def test_budget_resets_for_each_resolve_call():
    fake, r = make(max_queries=6)
    r.resolve("glueless.com")
    r.resolve("glueless.com")      # would fail if the counter carried over
    assert len(fake.calls) == 12


def test_timeout_moves_on_to_next_server():
    fake, r = make(root_servers=["10.0.0.9", ROOT])
    fake.down.add("10.0.0.9")
    assert datas(r.resolve("example.com")) == ["93.184.215.14"]
    assert fake.servers_asked[:2] == ["10.0.0.9", ROOT]


def test_servfail_moves_on_to_next_server():
    fake, r = make(root_servers=["10.0.0.66", ROOT])
    assert datas(r.resolve("example.com")) == ["93.184.215.14"]


def test_all_servers_down_raises_resolution_error():
    fake, r = make(root_servers=["10.0.0.8", "10.0.0.9"])
    with pytest.raises(ResolutionError):
        r.resolve("example.com")
    assert fake.servers_asked == ["10.0.0.8", "10.0.0.9"]


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("TINYRESOLVER_LIVE") != "1", reason="set TINYRESOLVER_LIVE=1 to run")
def test_live_resolution_from_the_real_root():
    result = Resolver().resolve("example.com")
    assert datas(result), "expected at least one A record"
