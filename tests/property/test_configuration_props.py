"""Property-based tests for Configuration validation and proxy source parsing.

Feature: ghost-booster-upgrade
Property 15: Virgülle Ayrılmış Proxy Kaynakları Ayrıştırma
Property 16: Yapılandırma Doğrulama

Validates: Requirements 7.3, 7.5
"""

import pytest
from hypothesis import given, settings, strategies as st

from src.models.config import Configuration
from config import _parse_proxy_sources


class TestConfigurationValidationProperty:
    """Property 16: Yapılandırma Doğrulama

    For any negatif veya sıfır değerli sayısal parametre (minimum limitlerin altında),
    Configuration oluşturulurken ValueError fırlatılmalı.

    **Validates: Requirements 7.5**
    """

    @settings(max_examples=100)
    @given(val=st.integers(max_value=0))
    def test_invalid_max_threads_raises(self, val):
        with pytest.raises(ValueError):
            Configuration(telegram_bot_token="tok", max_threads=val)

    @settings(max_examples=100)
    @given(val=st.integers(max_value=0))
    def test_invalid_request_timeout_raises(self, val):
        with pytest.raises(ValueError):
            Configuration(telegram_bot_token="tok", request_timeout=val)

    @settings(max_examples=100)
    @given(val=st.integers(max_value=0))
    def test_invalid_async_concurrency_limit_raises(self, val):
        with pytest.raises(ValueError):
            Configuration(telegram_bot_token="tok", async_concurrency_limit=val)

    @settings(max_examples=100)
    @given(val=st.floats(max_value=0, allow_nan=False, allow_infinity=False))
    def test_invalid_health_check_timeout_raises(self, val):
        with pytest.raises(ValueError):
            Configuration(telegram_bot_token="tok", health_check_timeout=val)

    @settings(max_examples=100)
    @given(val=st.integers(max_value=0))
    def test_invalid_health_check_concurrency_raises(self, val):
        with pytest.raises(ValueError):
            Configuration(telegram_bot_token="tok", health_check_concurrency=val)

    @settings(max_examples=100)
    @given(val=st.integers(max_value=0))
    def test_invalid_batch_size_raises(self, val):
        with pytest.raises(ValueError):
            Configuration(telegram_bot_token="tok", batch_size=val)

    @settings(max_examples=100)
    @given(val=st.integers(max_value=0))
    def test_invalid_session_daily_limit_raises(self, val):
        with pytest.raises(ValueError):
            Configuration(telegram_bot_token="tok", session_daily_limit=val)

    @settings(max_examples=100)
    @given(
        jmin=st.integers(min_value=0, max_value=1000),
        jmax_offset=st.integers(min_value=-1000, max_value=-1),
    )
    def test_jitter_max_less_than_min_raises(self, jmin, jmax_offset):
        jmax = jmin + jmax_offset
        if jmax < jmin:
            with pytest.raises(ValueError):
                Configuration(telegram_bot_token="tok", jitter_min_ms=jmin, jitter_max_ms=jmax)


class TestProxySourcesParsingProperty:
    """Property 15: Virgülle Ayrılmış Proxy Kaynakları Ayrıştırma

    For any URL listesi, bu URL'lerin virgülle birleştirilip tekrar
    ayrıştırılması orijinal listeyi üretmeli.

    **Validates: Requirements 7.3**
    """

    @settings(max_examples=200)
    @given(
        urls=st.lists(
            st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,4}(/[a-z0-9]+)*", fullmatch=True),
            min_size=0,
            max_size=10,
        )
    )
    def test_round_trip_proxy_sources(self, urls):
        joined = ",".join(urls)
        parsed = _parse_proxy_sources(joined)
        # Filter empty strings from original (same as _parse_proxy_sources does)
        expected = [u.strip() for u in urls if u.strip()]
        assert parsed == expected
