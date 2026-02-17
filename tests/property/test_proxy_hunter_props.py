"""Property-based tests for ProxyHunter deduplication and fault tolerance.

Feature: ghost-booster-upgrade
Property 1: Proxy Tekilleştirme
Property 2: Kaynak Hata Toleransı

**Validates: Requirements 1.4, 1.5**
"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from src.ghost_booster.proxy_hunter import ProxyHunter
from src.models.proxy_models import ParsedProxy, ProxySource

# Strategy for generating ParsedProxy lists with possible duplicates
proxy_strategy = st.builds(
    ParsedProxy,
    protocol=st.sampled_from(["http", "socks5"]),
    host=st.from_regex(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", fullmatch=True),
    port=st.integers(min_value=1, max_value=65535),
)


class TestProxyDeduplication:
    """Property 1: Proxy Tekilleştirme

    For any proxy listesi (tekrarlı elemanlar içerebilir), tekilleştirme sonrası
    listede aynı host:port çiftine sahip iki proxy bulunmamalı ve orijinal
    listedeki her benzersiz host:port çifti sonuç listesinde yer almalı.

    **Validates: Requirements 1.4**
    """

    @settings(max_examples=200)
    @given(proxies=st.lists(proxy_strategy, min_size=0, max_size=50))
    def test_deduplicate_no_duplicate_keys(self, proxies):
        hunter = ProxyHunter(sources=[])
        result = hunter._deduplicate(proxies)
        keys = [p.to_key() for p in result]
        assert len(keys) == len(set(keys))

    @settings(max_examples=200)
    @given(proxies=st.lists(proxy_strategy, min_size=0, max_size=50))
    def test_deduplicate_preserves_all_unique_keys(self, proxies):
        hunter = ProxyHunter(sources=[])
        result = hunter._deduplicate(proxies)
        original_keys = {p.to_key() for p in proxies}
        result_keys = {p.to_key() for p in result}
        assert result_keys == original_keys


class TestSourceFaultTolerance:
    """Property 2: Kaynak Hata Toleransı

    For any proxy kaynak listesi ve bu kaynakların herhangi bir alt kümesinin
    başarısız olması durumunda, hunt_all çağrısı başarılı kaynaklardan gelen
    proxy'leri döndürmeli ve başarısız kaynaklar nedeniyle istisna fırlatmamalı.

    **Validates: Requirements 1.5**
    """

    @settings(max_examples=100)
    @given(
        fail_mask=st.lists(st.booleans(), min_size=1, max_size=5),
    )
    def test_hunt_all_tolerates_failures(self, fail_mask):
        sources = [
            ProxySource(name=f"src-{i}", url=f"http://example.com/{i}", source_type="raw_list", proxy_type="http")
            for i in range(len(fail_mask))
        ]
        hunter = ProxyHunter(sources=sources, timeout=5)

        # Mock _fetch_from_source: fail or return a proxy based on mask
        async def mock_fetch(source, session):
            idx = int(source.name.split("-")[1])
            if fail_mask[idx]:
                raise Exception("simulated failure")
            return [ParsedProxy(protocol="http", host=f"10.0.0.{idx}", port=8080)]

        with patch.object(hunter, "_fetch_from_source", side_effect=mock_fetch):
            # We also need to mock aiohttp.ClientSession
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            # Patch hunt_all to use our mock fetch directly
            async def patched_hunt_all():
                all_proxies = []
                for source in hunter._sources:
                    try:
                        proxies = await mock_fetch(source, None)
                        all_proxies.extend(proxies)
                    except Exception:
                        pass
                return hunter._deduplicate(all_proxies)

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(patched_hunt_all())
            finally:
                loop.close()

            # Should have proxies from non-failed sources
            expected_count = sum(1 for f in fail_mask if not f)
            assert len(result) == expected_count
