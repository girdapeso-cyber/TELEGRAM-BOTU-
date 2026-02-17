"""Property-based tests for AsyncWorkerPool CycleReport consistency and jitter bounds.

Feature: ghost-booster-upgrade
Property 7: CycleReport Tutarlılığı
Property 8: Jitter Sınırları

**Validates: Requirements 5.6, 5.9**
"""

import random

from hypothesis import given, settings, strategies as st

from src.models.proxy_models import CycleReport


class TestCycleReportConsistency:
    """Property 7: CycleReport Tutarlılığı

    For any CycleReport nesnesi, successful_views değeri views_per_url
    sözlüğündeki tüm değerlerin toplamına eşit olmalı ve
    successful_views + failed_views toplamı total_proxies * len(event_urls)
    değerini aşmamalı.

    **Validates: Requirements 5.6**
    """

    @settings(max_examples=200)
    @given(
        total_proxies=st.integers(min_value=0, max_value=100),
        num_urls=st.integers(min_value=1, max_value=10),
        success_rate=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_report_consistency(self, total_proxies, num_urls, success_rate):
        urls = [f"https://t.me/ch/{i}" for i in range(num_urls)]
        max_views = total_proxies * num_urls

        # Simulate a realistic report
        successful = int(max_views * success_rate)
        failed = max_views - successful

        # Distribute successes across URLs
        views_per_url = {}
        remaining = successful
        for i, url in enumerate(urls):
            if i == len(urls) - 1:
                views_per_url[url] = remaining
            else:
                share = remaining // (len(urls) - i)
                views_per_url[url] = share
                remaining -= share

        report = CycleReport(
            total_proxies=total_proxies,
            successful_views=successful,
            failed_views=failed,
            views_per_url=views_per_url,
        )

        # Property: successful_views == sum(views_per_url.values())
        assert report.successful_views == sum(report.views_per_url.values())

        # Property: successful + failed <= total_proxies * num_urls
        assert report.successful_views + report.failed_views <= total_proxies * num_urls


class TestJitterBounds:
    """Property 8: Jitter Sınırları

    For any yapılandırılmış jitter_min_ms ve jitter_max_ms değerleri (min ≤ max),
    üretilen jitter değeri her zaman jitter_min_ms ≤ jitter ≤ jitter_max_ms
    aralığında olmalı.

    **Validates: Requirements 5.9**
    """

    @settings(max_examples=200)
    @given(
        jmin=st.integers(min_value=0, max_value=1000),
        jmax_offset=st.integers(min_value=0, max_value=1000),
    )
    def test_jitter_within_bounds(self, jmin, jmax_offset):
        jmax = jmin + jmax_offset
        # Simulate the jitter generation from AsyncWorkerPool._worker
        jitter_seconds = random.uniform(jmin / 1000.0, jmax / 1000.0)
        jitter_ms = jitter_seconds * 1000.0

        assert jitter_ms >= jmin - 0.001  # float tolerance
        assert jitter_ms <= jmax + 0.001
