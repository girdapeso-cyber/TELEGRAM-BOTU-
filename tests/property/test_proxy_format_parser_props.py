"""Property-based tests for ProxyFormatParser round-trip.

Feature: ghost-booster-upgrade
Property 3: Proxy Format Round-Trip

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.7, 2.8**
"""

from hypothesis import given, settings, strategies as st

from src.ghost_booster.proxy_format_parser import ProxyFormatParser
from src.models.proxy_models import ParsedProxy

# Strategies
protocols = st.sampled_from(["http", "https", "socks5"])
hosts = st.from_regex(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", fullmatch=True)
ports = st.integers(min_value=1, max_value=65535)
# Usernames/passwords: alphanumeric, no special URL chars
credentials = st.from_regex(r"[a-zA-Z0-9]{1,16}", fullmatch=True)

parser = ProxyFormatParser()


class TestProxyFormatRoundTrip:
    """Property 3: Proxy Format Round-Trip

    For any geçerli ParsedProxy nesnesi, parse(format(proxy)) işlemi
    orijinal proxy nesnesine eşit bir sonuç üretmeli.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.7, 2.8**
    """

    @settings(max_examples=200)
    @given(protocol=protocols, host=hosts, port=ports)
    def test_round_trip_without_auth(self, protocol, host, port):
        original = ParsedProxy(protocol=protocol, host=host, port=port)
        formatted = parser.format(original)
        parsed = parser.parse(formatted)
        assert parsed is not None
        assert parsed.protocol == original.protocol
        assert parsed.host == original.host
        assert parsed.port == original.port
        assert parsed.username is None
        assert parsed.password is None

    @settings(max_examples=200)
    @given(protocol=protocols, host=hosts, port=ports, user=credentials, pwd=credentials)
    def test_round_trip_with_auth(self, protocol, host, port, user, pwd):
        original = ParsedProxy(
            protocol=protocol, host=host, port=port, username=user, password=pwd
        )
        formatted = parser.format(original)
        parsed = parser.parse(formatted)
        assert parsed is not None
        assert parsed.protocol == original.protocol
        assert parsed.host == original.host
        assert parsed.port == original.port
        assert parsed.username == original.username
        assert parsed.password == original.password
