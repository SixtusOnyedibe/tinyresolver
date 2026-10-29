"""Milestone 4: a command-line tool, `python -m tinyresolver example.com`.

The resolver is faked here, so these tests never touch the network.
"""
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import tinyresolver.cli as cli
from tinyresolver.cli import format_record, main
from tinyresolver.errors import NXDomainError, ResolutionError
from tinyresolver.wire import Record, RecordType

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FakeResolver:
    def __init__(self, result=None, error=None):
        self.result = result or []
        self.error = error
        self.asked = []

    def resolve(self, name, qtype=RecordType.A):
        self.asked.append((name, qtype))
        if self.error:
            raise self.error
        return self.result


# ---------- format_record ----------

@pytest.mark.parametrize(
    "record, line",
    [
        (Record("example.com", 1, 1, 300, "93.184.215.14"),
         "example.com.\t300\tIN\tA\t93.184.215.14"),
        (Record("www.python.org", 5, 1, 3600, "dualstack.python.map.fastly.net"),
         "www.python.org.\t3600\tIN\tCNAME\tdualstack.python.map.fastly.net."),
        (Record("com", 2, 1, 172800, "a.gtld-servers.net"),
         "com.\t172800\tIN\tNS\ta.gtld-servers.net."),
        (Record("a.io", 28, 1, 60, "2001:db8::1"),
         "a.io.\t60\tIN\tAAAA\t2001:db8::1"),
        (Record("x.com", 99, 1, 5, b"\x01\x02"),
         "x.com.\t5\tIN\tTYPE99\t\\# 2 0102"),
        (Record("x.com", 6, 1, 5, b"\xab"),
         "x.com.\t5\tIN\tSOA\t\\# 1 ab"),
    ],
)
def test_format_record(record, line):
    assert format_record(record) == line


# ---------- main ----------

def test_main_prints_records_and_returns_0(capsys):
    fake = FakeResolver(result=[Record("example.com", 1, 1, 300, "93.184.215.14")])
    assert main(["example.com"], resolver=fake) == 0
    out = capsys.readouterr().out
    assert "example.com.\t300\tIN\tA\t93.184.215.14" in out
    assert fake.asked == [("example.com", RecordType.A)]


def test_main_passes_the_type_flag():
    fake = FakeResolver(result=[])
    main(["example.com", "-t", "AAAA"], resolver=fake)
    main(["example.com", "--type", "NS"], resolver=fake)
    assert fake.asked == [("example.com", 28), ("example.com", 2)]


def test_main_empty_result(capsys):
    assert main(["example.com"], resolver=FakeResolver(result=[])) == 0
    assert ";; no records" in capsys.readouterr().out


def test_main_nxdomain_returns_1(capsys):
    assert main(["nope.example"], resolver=FakeResolver(error=NXDomainError("nope.example"))) == 1
    assert "NXDOMAIN" in capsys.readouterr().err


def test_main_other_dns_errors_return_2(capsys):
    assert main(["loop.example"], resolver=FakeResolver(error=ResolutionError("gave up"))) == 2
    assert capsys.readouterr().err.strip() != ""


def test_main_rejects_unknown_type():
    with pytest.raises(SystemExit) as exc:
        main(["example.com", "-t", "BOGUS"], resolver=FakeResolver())
    assert exc.value.code == 2


# ---------- __main__.py and the __name__ guard ----------

def test_python_dash_m_help_works():
    result = subprocess.run(
        [sys.executable, "-m", "tinyresolver", "--help"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()


def test_importing_dunder_main_does_not_run_the_cli(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("main() ran during import: add the if __name__ == '__main__' guard")

    monkeypatch.setattr(cli, "main", boom)
    sys.modules.pop("tinyresolver.__main__", None)
    importlib.import_module("tinyresolver.__main__")
