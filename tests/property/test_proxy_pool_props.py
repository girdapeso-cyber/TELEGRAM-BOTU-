"""Property-based tests for ProxyPool critical threshold and acquire semantics.

Feature: ghost-booster-upgrade
Property 5: Proxy Havuzu Kritik Eşik
Property 6: Proxy Havuzu Acquire Semantiği

**Validates: Requirements 4.1, 4.2, 4.4**
"""

from hypothesis import given, settings, strategies as st

from src.ghost_booster.proxy_pool import ProxyPool
from src.models.proxy_models import ParsedProxy

proxy_st = st.builds(
    ParsedProxy,
    protocol=st.just("http"),
    host=st.from_regex(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", fullmatch=True),
    port=st.integers(min_value=1, max_value=65535),
)


class TestProxyPoolCriticalThreshold:
    """Property 5: Proxy Havuzu Kritik Eşik

    For any proxy havuzu, havuzdaki proxy sayısı yapılandırılmış kritik eşiğin
    altındaysa is_critical() True döndürmeli, eşik veya üzerindeyse False döndürmeli.

    **Validates: Requirements 4.1**
    """

    @settings(max_examples=200)
    @given(
        proxies=st.lists(proxy_st, min_size=0, max_size=50),
        threshold=st.integers(min_value=0, max_value=30),
    )
    def test_critical_threshold(self, proxies, threshold):
        pool = ProxyPool(critical_threshold=threshold)
        pool.load(proxies)
        if pool.size() < threshold:
            assert pool.is_critical() is True
        else:
            assert pool.is_critical() is False


class TestProxyPoolAcquireSemantics:
    """Property 6: Proxy Havuzu Acquire Semantiği

    For any boş olmayan proxy havuzu, acquire() çağrısı havuz boyutunu 1 azaltmalı
    ve döndürülen proxy artık havuzda bulunmamalı.

    **Validates: Requirements 4.2, 4.4**
    """

    @settings(max_examples=200)
    @given(proxies=st.lists(proxy_st, min_size=1, max_size=30))
    def test_acquire_decrements_size(self, proxies):
        pool = ProxyPool()
        pool.load(proxies)
        initial_size = pool.size()
        acquired = pool.acquire()
        assert acquired is not None
        assert pool.size() == initial_size - 1

    @settings(max_examples=200)
    @given(proxies=st.lists(proxy_st, min_size=1, max_size=30))
    def test_acquire_returns_first_proxy(self, proxies):
        pool = ProxyPool()
        pool.load(proxies)
        acquired = pool.acquire()
        # Should return the first proxy (fastest, from deque left)
        assert acquired is not None
        assert acquired.to_key() == proxies[0].to_key()

    def test_acquire_empty_returns_none(self):
        pool = ProxyPool()
        assert pool.acquire() is None

    @settings(max_examples=100)
    @given(proxies=st.lists(proxy_st, min_size=1, max_size=20))
    def test_acquire_all_empties_pool(self, proxies):
        pool = ProxyPool()
        pool.load(proxies)
        for _ in range(len(proxies)):
            assert pool.acquire() is not None
        assert pool.is_empty() is True
        assert pool.acquire() is None
