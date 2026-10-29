"""Real-shaped DNS packets for the tests. You never edit this file.

Each blob is exactly what a DNS server would send back over UDP.
The comment above each one is what `dig` would show for it, so you
can compare your parser's output by eye.
"""

# Response from 8.8.8.8 to "example.com A"
#   id=0x1a2b  flags=0x8180 (QR, RD, RA)  rcode=0
#   QUESTION   example.com.  IN  A
#   ANSWER     example.com.  3600  IN  A  93.184.215.14
#   The answer's name is a compression pointer (c0 0c) back to the question.
EXAMPLE_A = bytes.fromhex(
    "1a2b81800001000100000000076578616d706c6503636f6d0000010001c00c00"
    "01000100000e1000045db8d70e"
)

# Response to "www.python.org A" from a recursive resolver
#   id=0xbeef  flags=0x8180
#   ANSWER  www.python.org.                   3600  IN  CNAME  dualstack.python.map.fastly.net.
#           dualstack.python.map.fastly.net.    30  IN  A      151.101.64.223
#           dualstack.python.map.fastly.net.    30  IN  A      151.101.0.223
#   The CNAME's RDATA is a name; the two A records point back into it.
CNAME_CHAIN = bytes.fromhex(
    "beef818000010003000000000377777706707974686f6e036f72670000010001"
    "c00c0005000100000e100021096475616c737461636b06707974686f6e036d61"
    "7006666173746c79036e657400c02c000100010000001e0004976540dfc02c00"
    "0100010000001e0004976500df"
)

# Referral from a root server (198.41.0.4) for "example.com A"
#   id=0x0042  flags=0x8000 (QR only: not authoritative, no recursion)
#   ANSWER      (empty)
#   AUTHORITY   com.  172800  IN  NS  b.gtld-servers.net.
#               com.  172800  IN  NS  a.gtld-servers.net.
#   ADDITIONAL  a.gtld-servers.net.  172800  IN  A     192.5.6.30
#               b.gtld-servers.net.  172800  IN  A     192.33.14.30
#               a.gtld-servers.net.  172800  IN  AAAA  2001:503:a83e::2:30
#   "Glue" = the additional A records that tell you where the NS servers are.
ROOT_REFERRAL = bytes.fromhex(
    "004280000001000000020003076578616d706c6503636f6d0000010001c01400"
    "0200010002a300001401620c67746c642d73657276657273036e657400c01400"
    "0200010002a30000040161c02bc049000100010002a3000004c005061ec02900"
    "0100010002a3000004c0210e1ec049001c00010002a300001020010503a83e00"
    "000000000000020030"
)

# NXDOMAIN for "nope.example.com A"
#   id=0x7777  flags=0x8183  rcode=3 (name does not exist)
#   AUTHORITY  example.com.  3600  IN  SOA  ns.icann.org. noc.dns.icann.org. 2024081457 7200 3600 1209600 3600
NXDOMAIN = bytes.fromhex(
    "777781830001000000010000046e6f7065076578616d706c6503636f6d000001"
    "0001c0110006000100000e10002c026e73056963616e6e036f726700036e6f63"
    "03646e73c03178a5083100001c2000000e100012750000000e10"
)
