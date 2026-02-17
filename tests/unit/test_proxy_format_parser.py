"""Unit tests for ProxyFormatParser.

Tanınmayan format kenar durumları, boş satırlar, eksik port, özel karakterler.
Validates: Requirements 2.5
"""

import pytest

from src.ghost_booster.proxy_format_parser import ProxyFormatParser


@pytest.fixture
def parser():
    return ProxyFormatParser()


class TestParse:
    def test_ip_port(self, parser):
        p = parser.parse("1.2.3.4:8080")
        assert p is not None
        assert p.protocol == "http"
        assert p.host == "1.2.3.4"
        assert p.port == 8080

    def test_ip_port_user_pass(self, parser):
        p = parser.parse("1.2.3.4:8080:user:pass")
        assert p is not None
        assert p.username == "user"
        assert p.password == "pass"

    def test_protocol_url(self, parser):
        p = parser.parse("socks5://10.0.0.1:1080")
        assert p is not None
        assert p.protocol == "socks5"
        assert p.host == "10.0.0.1"
        assert p.port == 1080

    def test_protocol_url_with_auth(self, parser):
        p = parser.parse("http://admin:secret@5.5.5.5:3128")
        assert p is not None
        assert p.username == "admin"
        assert p.password == "secret"

    def test_empty_string(self, parser):
        assert parser.parse("") is None

    def test_whitespace_only(self, parser):
        assert parser.parse("   ") is None

    def test_unrecognized_format_two_colons(self, parser):
        assert parser.parse("1.2.3.4:8080:extra") is None

    def test_unrecognized_protocol(self, parser):
        assert parser.parse("ftp://1.2.3.4:21") is None

    def test_missing_port(self, parser):
        assert parser.parse("http://1.2.3.4") is None

    def test_non_numeric_port(self, parser):
        assert parser.parse("1.2.3.4:abc") is None

    def test_port_out_of_range_high(self, parser):
        assert parser.parse("1.2.3.4:70000") is None

    def test_port_zero(self, parser):
        assert parser.parse("1.2.3.4:0") is None


class TestFormat:
    def test_format_without_auth(self, parser):
        from src.models.proxy_models import ParsedProxy
        p = ParsedProxy(protocol="http", host="1.2.3.4", port=8080)
        assert parser.format(p) == "http://1.2.3.4:8080"

    def test_format_with_auth(self, parser):
        from src.models.proxy_models import ParsedProxy
        p = ParsedProxy(protocol="socks5", host="10.0.0.1", port=1080, username="u", password="p")
        assert parser.format(p) == "socks5://u:p@10.0.0.1:1080"


class TestParseMany:
    def test_mixed_valid_invalid(self, parser):
        text = "1.2.3.4:8080\nbadline\nsocks5://5.5.5.5:1080\n\n"
        results = parser.parse_many(text)
        assert len(results) == 2

    def test_empty_text(self, parser):
        assert parser.parse_many("") == []
