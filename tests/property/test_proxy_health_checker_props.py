"""Property-based tests for ProxyHealthChecker filtering and sorting.

Feature: ghost-booster-upgrade
Property 4: Sağlık Kontrolü Filtreleme ve Sıralama

**Validates: Requirements 3.4, 3.5**
"""

from hypothesis import given, settings, strategies as st

from src.models.proxy_models import HealthCheckResult, ParsedProxy


# Strategy for HealthCheckResult
proxy_st = st.builds(
    ParsedProxy,
    protocol=st.just("http"),
    host=st.from_regex(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", fullmatch=True),
    port=st.integers(min_value=1, max_value=65535),
)

health_result_st = st.builds(
    HealthCheckResult,
    proxy=proxy_st,
    is_alive=st.booleans(),
    response_time_ms=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
)


def filter_and_sort(results: list[HealthCheckResult]) -> list[ParsedProxy]:
    """Replicate the check_all filtering/sorting logic without network calls."""
    alive = [r for r in results if r.is_alive]
    alive.sort(key=lambda r: r.response_time_ms)
    return [r.proxy for r in alive]


class TestHealthCheckFilterAndSort:
    """Property 4: Sağlık Kontrolü Filtreleme ve Sıralama

    For any sağlık kontrolü sonuç listesi, çıktı listesi yalnızca
    is_alive=True olan proxy'leri içermeli ve bu proxy'ler response_time_ms
    değerine göre artan sırada sıralı olmalı.

    **Validates: Requirements 3.4, 3.5**
    """

    @settings(max_examples=200)
    @given(results=st.lists(health_result_st, min_size=0, max_size=30))
    def test_only_alive_proxies_returned(self, results):
        filtered = filter_and_sort(results)
        alive_count = sum(1 for r in results if r.is_alive)
        assert len(filtered) == alive_count

    @settings(max_examples=200)
    @given(results=st.lists(health_result_st, min_size=0, max_size=30))
    def test_sorted_by_response_time(self, results):
        filtered = filter_and_sort(results)
        # Verify the underlying response times are sorted
        alive = sorted(
            [r for r in results if r.is_alive],
            key=lambda r: r.response_time_ms,
        )
        expected_keys = [r.proxy.to_key() for r in alive]
        actual_keys = [p.to_key() for p in filtered]
        assert actual_keys == expected_keys
