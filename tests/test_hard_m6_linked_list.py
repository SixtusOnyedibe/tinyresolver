"""Hard mode for Milestone 6: the cache's usage order as your own doubly linked list.

Run with:  pytest tests/test_hard_m6_linked_list.py -v
"""
import inspect
import random

import tinyresolver.cache as cache_module
from tinyresolver.cache import TTLCache
from tinyresolver.wire import Record


# =====================================================================
# 1. LRU order as a doubly linked list
#
# Shape the tests expect:
#   self._head and self._tail are two sentinel nodes that never hold data.
#   _head.next is the MOST recently used entry, _tail.prev the LEAST.
#   Every real node has .key, .prev and .next. Its key is (name, qtype)
#   after normalising: lower case, no trailing dot, qtype as a plain int.
# =====================================================================

class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def A(name, ttl=300):
    return [Record(name, 1, 1, ttl, "1.1.1.1")]


def keys_newest_first(c):
    keys, node, steps = [], c._head.next, 0
    while node is not c._tail:
        assert node.prev.next is node, "a node's prev and next links disagree"
        keys.append(node.key)
        node = node.next
        steps += 1
        assert steps <= 10_000, "the list never reaches _tail: there is a cycle"
    assert c._tail.prev.next is c._tail
    return keys


def test_cache_source_does_not_use_ready_made_ordering():
    src = inspect.getsource(cache_module)
    for banned in ("OrderedDict", "move_to_end", "lru_cache", "deque"):
        assert banned not in src, f"hard mode: build the order yourself, no {banned}"


def test_empty_cache_has_only_the_two_sentinels():
    c = TTLCache(clock=FakeClock())
    assert c._head.next is c._tail
    assert c._tail.prev is c._head
    assert keys_newest_first(c) == []


def test_put_adds_at_the_front():
    c = TTLCache(clock=FakeClock())
    c.put("a.com", 1, A("a.com"))
    c.put("B.com.", 1, A("b.com"))
    c.put("c.com", 28, A("c.com"))
    assert keys_newest_first(c) == [("c.com", 28), ("b.com", 1), ("a.com", 1)]


def test_get_moves_a_node_to_the_front():
    c = TTLCache(clock=FakeClock())
    for n in ("a.com", "b.com", "c.com"):
        c.put(n, 1, A(n))
    c.get("a.com", 1)
    assert keys_newest_first(c) == [("a.com", 1), ("c.com", 1), ("b.com", 1)]


def test_a_miss_does_not_change_the_order():
    c = TTLCache(clock=FakeClock())
    for n in ("a.com", "b.com"):
        c.put(n, 1, A(n))
    c.get("zzz.com", 1)
    assert keys_newest_first(c) == [("b.com", 1), ("a.com", 1)]


def test_put_existing_key_moves_it_without_duplicating():
    c = TTLCache(clock=FakeClock())
    for n in ("a.com", "b.com", "c.com"):
        c.put(n, 1, A(n))
    c.put("b.com", 1, A("b.com"))
    assert keys_newest_first(c) == [("b.com", 1), ("c.com", 1), ("a.com", 1)]
    assert len(c) == 3


def test_eviction_unlinks_the_tail_node():
    c = TTLCache(capacity=3, clock=FakeClock())
    for n in ("a.com", "b.com", "c.com"):
        c.put(n, 1, A(n))
    c.get("a.com", 1)
    c.put("d.com", 1, A("d.com"))
    assert keys_newest_first(c) == [("d.com", 1), ("a.com", 1), ("c.com", 1)]
    assert len(c) == 3


def test_expired_entry_is_unlinked():
    clock = FakeClock()
    c = TTLCache(clock=clock)
    c.put("short.com", 1, A("short.com", ttl=10))
    c.put("long.com", 1, A("long.com", ttl=300))
    clock.now += 11
    assert c.get("short.com", 1) is None
    assert keys_newest_first(c) == [("long.com", 1)]
    assert len(c) == 1


def test_capacity_one():
    c = TTLCache(capacity=1, clock=FakeClock())
    c.put("a.com", 1, A("a.com"))
    c.put("b.com", 1, A("b.com"))
    assert keys_newest_first(c) == [("b.com", 1)]
    assert c.get("a.com", 1) is None


def test_list_stays_consistent_under_random_use():
    clock = FakeClock()
    c = TTLCache(capacity=50, clock=clock)
    rng = random.Random(7)
    for _ in range(20_000):
        name = f"h{rng.randrange(120)}.com"
        if rng.random() < 0.5:
            c.put(name, 1, A(name, ttl=rng.randrange(1, 60)))
        else:
            c.get(name, 1)
        clock.now += rng.random()
    keys = keys_newest_first(c)
    assert len(keys) == len(set(keys)) == len(c) <= 50
