"""Milestone 7: an ad-blocking list stored as a trie of reversed labels.

A rule like "ads.example.com" blocks that name and every name under it
(x.ads.example.com), but not its parent (example.com) and not a name
that only happens to end in the same letters (badads.example.com).
"""
import time

from tinyresolver.blocklist import DomainTrie


def test_exact_match_and_subdomains_are_blocked():
    t = DomainTrie()
    t.add("ads.example.com")
    assert t.is_blocked("ads.example.com")
    assert t.is_blocked("x.ads.example.com")
    assert t.is_blocked("a.b.c.ads.example.com")


def test_parents_and_lookalikes_are_not_blocked():
    t = DomainTrie()
    t.add("ads.example.com")
    assert not t.is_blocked("example.com")
    assert not t.is_blocked("com")
    assert not t.is_blocked("badads.example.com")
    assert not t.is_blocked("ads.example.org")
    assert not t.is_blocked("")


def test_case_and_trailing_dot_do_not_matter():
    t = DomainTrie()
    t.add("Tracker.NET.")
    assert t.is_blocked("tracker.net")
    assert t.is_blocked("pixel.TRACKER.net.")


def test_len_counts_rules_and_add_reports_new_rules():
    t = DomainTrie()
    assert t.add("a.com") is True
    assert t.add("b.com") is True
    assert t.add("A.com.") is False        # same rule again
    assert len(t) == 2


def test_labels_are_shared_like_a_trie():
    t = DomainTrie()
    t.add("a.example.com")
    t.add("b.example.com")
    # nodes: com -> example -> {a, b}. The root itself is not counted.
    assert t.node_count() == 4


def test_remove_prunes_empty_branches():
    t = DomainTrie()
    t.add("a.b.com")
    t.add("x.b.com")
    assert t.node_count() == 4             # com, b, a, x
    assert t.remove("a.b.com") is True
    assert t.node_count() == 3
    assert not t.is_blocked("a.b.com")
    assert t.is_blocked("x.b.com")
    assert t.remove("x.b.com") is True
    assert t.node_count() == 0
    assert len(t) == 0


def test_remove_missing_rule_returns_false():
    t = DomainTrie()
    t.add("a.b.com")
    assert t.remove("b.com") is False      # b.com is a path in the trie, not a rule
    assert t.remove("zzz.com") is False
    assert t.is_blocked("a.b.com")
    assert len(t) == 1


def test_overlapping_rules():
    t = DomainTrie()
    t.add("b.com")
    t.add("a.b.com")
    assert t.is_blocked("x.b.com")
    t.remove("b.com")
    assert not t.is_blocked("x.b.com")
    assert t.is_blocked("a.b.com")
    assert t.is_blocked("deep.a.b.com")


def test_from_lines_reads_plain_and_hosts_file_formats():
    lines = [
        "# a comment line",
        "",
        "ads.example.com",
        "0.0.0.0 tracker.net",
        "127.0.0.1   pixel.io   # inline comment",
        "   spaced.org   ",
    ]
    t = DomainTrie.from_lines(lines)
    assert len(t) == 4
    for name in ("ads.example.com", "tracker.net", "pixel.io", "spaced.org"):
        assert t.is_blocked(name)
    assert not t.is_blocked("0.0.0.0")


def test_big_list_is_fast():
    t = DomainTrie()
    for i in range(200_000):
        t.add(f"host{i}.zone{i % 500}.com")
    assert len(t) == 200_000

    start = time.perf_counter()
    hits = sum(t.is_blocked(f"cdn.host{i}.zone{i % 500}.com") for i in range(0, 200_000, 2))
    misses = sum(t.is_blocked(f"host{i}.zone{i % 500}.org") for i in range(100_000))
    elapsed = time.perf_counter() - start

    assert hits == 100_000
    assert misses == 0
    assert elapsed < 3, f"200k lookups took {elapsed:.2f}s"
