"""Milestone 6: a TTL cache with least-recently-used eviction.

FakeClock lets the tests move time forward instantly, which is why
TTLCache takes a `clock` argument instead of calling time.monotonic() directly.
"""
import time

from tests.fakenet import ROOT, FakeNet
from tinyresolver.cache import TTLCache
from tinyresolver.resolver import Resolver
from tinyresolver.wire import Record, RecordType


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def A(name, ip, ttl):
    return Record(name, RecordType.A, 1, ttl, ip)


def test_default_clock_is_monotonic():
    c = TTLCache()
    assert c.capacity == 1000
    assert c.clock is time.monotonic


def test_miss_returns_none():
    assert TTLCache().get("example.com", RecordType.A) is None


def test_put_then_get():
    c = TTLCache(clock=FakeClock())
    c.put("example.com", RecordType.A, [A("example.com", "1.2.3.4", 300)])
    assert c.get("example.com", RecordType.A) == [A("example.com", "1.2.3.4", 300)]
    assert len(c) == 1


def test_returned_ttl_counts_down():
    clock = FakeClock()
    c = TTLCache(clock=clock)
    c.put("example.com", RecordType.A, [A("example.com", "1.2.3.4", 300)])
    clock.now += 100.7
    (rec,) = c.get("example.com", RecordType.A)
    assert rec.ttl == 200          # 300 - int(100.7)


def test_get_returns_copies_not_the_stored_objects():
    c = TTLCache(clock=FakeClock())
    original = A("example.com", "1.2.3.4", 300)
    c.put("example.com", RecordType.A, [original])
    got = c.get("example.com", RecordType.A)
    got[0].ttl = 1
    got.clear()
    assert c.get("example.com", RecordType.A) == [A("example.com", "1.2.3.4", 300)]
    assert original.ttl == 300


def test_entry_expires_at_its_ttl():
    clock = FakeClock()
    c = TTLCache(clock=clock)
    c.put("example.com", RecordType.A, [A("example.com", "1.2.3.4", 60)])
    clock.now += 59.9
    assert c.get("example.com", RecordType.A) is not None
    clock.now += 0.1
    assert c.get("example.com", RecordType.A) is None
    assert len(c) == 0, "expired entries are removed when you find them"


def test_lowest_ttl_in_the_list_decides_expiry():
    clock = FakeClock()
    c = TTLCache(clock=clock)
    c.put("x.com", RecordType.A, [A("x.com", "1.1.1.1", 300), A("x.com", "2.2.2.2", 30)])
    clock.now += 31
    assert c.get("x.com", RecordType.A) is None


def test_keys_ignore_case_and_trailing_dot():
    c = TTLCache(clock=FakeClock())
    c.put("Example.COM.", RecordType.A, [A("example.com", "1.2.3.4", 300)])
    assert c.get("example.com", RecordType.A) is not None


def test_type_is_part_of_the_key():
    c = TTLCache(clock=FakeClock())
    c.put("example.com", RecordType.A, [A("example.com", "1.2.3.4", 300)])
    assert c.get("example.com", RecordType.AAAA) is None


def test_empty_lists_and_zero_ttl_are_not_stored():
    c = TTLCache(clock=FakeClock())
    c.put("a.com", RecordType.A, [])
    c.put("b.com", RecordType.A, [A("b.com", "1.1.1.1", 0)])
    assert len(c) == 0


def test_put_replaces_existing_entry():
    c = TTLCache(clock=FakeClock())
    c.put("a.com", RecordType.A, [A("a.com", "1.1.1.1", 300)])
    c.put("A.com", RecordType.A, [A("a.com", "9.9.9.9", 300)])
    assert len(c) == 1
    assert c.get("a.com", RecordType.A)[0].data == "9.9.9.9"


def test_least_recently_used_is_evicted():
    c = TTLCache(capacity=2, clock=FakeClock())
    c.put("a.com", 1, [A("a.com", "1.1.1.1", 300)])
    c.put("b.com", 1, [A("b.com", "2.2.2.2", 300)])
    c.get("a.com", 1)                        # a is now the most recently used
    c.put("c.com", 1, [A("c.com", "3.3.3.3", 300)])
    assert len(c) == 2
    assert c.get("b.com", 1) is None
    assert c.get("a.com", 1) is not None
    assert c.get("c.com", 1) is not None


def test_putting_again_also_counts_as_use():
    c = TTLCache(capacity=2, clock=FakeClock())
    c.put("a.com", 1, [A("a.com", "1.1.1.1", 300)])
    c.put("b.com", 1, [A("b.com", "2.2.2.2", 300)])
    c.put("a.com", 1, [A("a.com", "1.1.1.1", 300)])
    c.put("c.com", 1, [A("c.com", "3.3.3.3", 300)])
    assert c.get("b.com", 1) is None
    assert c.get("a.com", 1) is not None


def test_cache_is_fast_enough():
    # 200k operations on a full cache. A list-based LRU is O(n) per operation
    # and will blow past the limit; a hash map plus O(1) ordering will not.
    c = TTLCache(capacity=1000, clock=FakeClock())
    start = time.perf_counter()
    for i in range(100_000):
        name = f"host{i % 3000}.example.com"
        c.put(name, 1, [A(name, "1.1.1.1", 300)])
        c.get(f"host{(i * 7) % 3000}.example.com", 1)
    elapsed = time.perf_counter() - start
    assert len(c) == 1000
    assert elapsed < 3, f"took {elapsed:.2f}s"


# ---------- plugging the cache into the resolver ----------

def test_resolver_uses_the_cache():
    clock = FakeClock()
    fake = FakeNet()
    r = Resolver(query_fn=fake, root_servers=[ROOT], cache=TTLCache(clock=clock))

    first = r.resolve("example.com")
    calls_after_first = len(fake.calls)
    second = r.resolve("example.com")
    assert len(fake.calls) == calls_after_first, "second lookup should come from the cache"
    assert [x.data for x in second] == [x.data for x in first]

    clock.now += 3601                     # example.com's A record has TTL 3600
    r.resolve("example.com")
    assert len(fake.calls) > calls_after_first


def test_nameserver_lookups_are_cached_too():
    fake = FakeNet()
    r = Resolver(query_fn=fake, root_servers=[ROOT], cache=TTLCache(clock=FakeClock()))
    r.resolve("glueless.com")
    fake.calls.clear()
    # A different record type for the same name is a new question, but the
    # resolver still needs ns.provider.net's address. That should be cached now.
    assert r.resolve("glueless.com", RecordType.TXT) == []
    asked_for_ns = [c for c in fake.calls if c[1] == "ns.provider.net"]
    assert asked_for_ns == [], "ns.provider.net's address should come from the cache"
