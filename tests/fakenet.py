"""A pretend internet for the resolver tests. You never edit this file.

FakeNet is a stand-in for network_query(server, name, qtype). Each "server"
is a function that answers questions the way a real DNS server would.
The map of the pretend internet:

    root (10.0.0.1)
     ├── com.  ->  a.gtld (10.1.0.1)
     │     ├── example.com.    ->  ns1.example.com (10.2.0.1, glue given)
     │     ├── glueless.com.   ->  ns.provider.net (NO glue: you must look it up)
     │     ├── trap.com.       ->  ns.trap.com (10.8.0.1), which only ever refers to itself
     │     └── anything else   ->  NXDOMAIN
     ├── org.  ->  org server (10.3.0.1), answers target.example.org directly
     └── net.  ->  net server (10.4.0.1)
           └── provider.net.  ->  ns.provider.net (10.5.0.1, glue given)

    10.6.0.1 is where ns.provider.net lives, and it serves glueless.com.
"""
from tinyresolver.wire import Header, Message, Record, RecordType

ROOT = "10.0.0.1"
COM = "10.1.0.1"
EXAMPLE = "10.2.0.1"
ORG = "10.3.0.1"
NET = "10.4.0.1"
PROVIDER = "10.5.0.1"
GLUELESS = "10.6.0.1"
TRAP = "10.8.0.1"


def A(name, ip, ttl=300):
    return Record(name, RecordType.A, 1, ttl, ip)


def NS(zone, host, ttl=86400):
    return Record(zone, RecordType.NS, 1, ttl, host)


def CNAME(name, target, ttl=300):
    return Record(name, RecordType.CNAME, 1, ttl, target)


def SOA(zone):
    return Record(zone, RecordType.SOA, 1, 3600, b"\x00" * 22)


def msg(answers=(), authorities=(), additionals=(), rcode=0, aa=False):
    flags = 0x8000 | (0x0400 if aa else 0) | rcode
    return Message(
        header=Header(id=1, flags=flags, qdcount=1, ancount=len(answers),
                      nscount=len(authorities), arcount=len(additionals)),
        questions=[],
        answers=list(answers),
        authorities=list(authorities),
        additionals=list(additionals),
    )


def referral(zone, hosts_and_ips):
    """hosts_and_ips: list of (ns_host, glue_ip_or_None)."""
    return msg(
        authorities=[NS(zone, host) for host, _ in hosts_and_ips],
        additionals=[A(host, ip, 86400) for host, ip in hosts_and_ips if ip],
    )


def nxdomain(zone):
    return msg(authorities=[SOA(zone)], rcode=3, aa=True)


def under(name, zone):
    return name == zone or name.endswith("." + zone)


def root_server(name, qtype):
    if under(name, "com"):
        return referral("com", [("a.gtld-servers.net", COM)])
    if under(name, "org"):
        return referral("org", [("a0.org-servers.net", ORG)])
    if under(name, "net"):
        return referral("net", [("a.gtld-servers.net", NET)])
    return nxdomain("")


def com_server(name, qtype):
    if under(name, "example.com"):
        return referral("example.com", [("ns1.example.com", EXAMPLE)])
    if under(name, "glueless.com"):
        return referral("glueless.com", [("ns.provider.net", None)])
    if under(name, "trap.com"):
        return referral("trap.com", [("ns.trap.com", TRAP)])
    return nxdomain("com")


def example_server(name, qtype):
    zone = "example.com"
    if name == "example.com" and qtype == RecordType.A:
        return msg(answers=[A("example.com", "93.184.215.14", 3600)], aa=True)
    if name == "www.example.com" and qtype == RecordType.A:
        return msg(answers=[CNAME("www.example.com", "example.com"),
                            A("example.com", "93.184.215.14", 3600)], aa=True)
    if name == "alias.example.com":
        return msg(answers=[CNAME("alias.example.com", "target.example.org")], aa=True)
    if name == "loop1.example.com":
        return msg(answers=[CNAME("loop1.example.com", "loop2.example.com")], aa=True)
    if name == "loop2.example.com":
        return msg(answers=[CNAME("loop2.example.com", "loop1.example.com")], aa=True)
    if name in ("example.com", "nodata.example.com"):
        return msg(authorities=[SOA(zone)], aa=True)     # name exists, no records of this type
    return nxdomain(zone)


def org_server(name, qtype):
    if name == "target.example.org" and qtype == RecordType.A:
        return msg(answers=[A("target.example.org", "10.9.9.9")], aa=True)
    return nxdomain("org")


def net_server(name, qtype):
    if under(name, "provider.net"):
        return referral("provider.net", [("ns.provider.net", PROVIDER)])
    return nxdomain("net")


def provider_server(name, qtype):
    if name == "ns.provider.net" and qtype == RecordType.A:
        return msg(answers=[A("ns.provider.net", GLUELESS)], aa=True)
    return nxdomain("provider.net")


def glueless_server(name, qtype):
    if name == "glueless.com" and qtype == RecordType.A:
        return msg(answers=[A("glueless.com", "10.7.7.7")], aa=True)
    if name == "glueless.com":
        return msg(authorities=[SOA("glueless.com")], aa=True)
    return nxdomain("glueless.com")


def trap_server(name, qtype):
    return referral("trap.com", [("ns.trap.com", TRAP)])


def servfail_server(name, qtype):
    return msg(rcode=2)


class FakeNet:
    """Call it like network_query: fake(server, name, qtype) -> Message."""

    def __init__(self):
        self.servers = {
            ROOT: root_server, COM: com_server, EXAMPLE: example_server, ORG: org_server,
            NET: net_server, PROVIDER: provider_server, GLUELESS: glueless_server,
            TRAP: trap_server, "10.0.0.66": servfail_server,
        }
        self.down = set()
        self.calls = []

    def __call__(self, server, name, qtype):
        name = name.rstrip(".").lower()
        self.calls.append((server, name, int(qtype)))
        if server in self.down or server not in self.servers:
            raise TimeoutError(f"{server} did not answer")
        return self.servers[server](name, int(qtype))

    @property
    def servers_asked(self):
        return [server for server, _, _ in self.calls]
