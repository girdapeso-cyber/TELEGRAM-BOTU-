"""Property-based tests for SessionManager.

Feature: ghost-booster-upgrade
Property 11: Oturum Round-Robin
Property 12: Cooldown Oturum Atlama
Property 13: Oturum Proxy Benzersizliği
Property 14: Günlük Limit Uygulaması

**Validates: Requirements 6.4, 6.5, 6.6, 6.9, 6.10**
"""

import asyncio
import time
from datetime import date

import pytest
from hypothesis import given, settings, strategies as st

from src.ghost_booster.session_manager import SessionManager
from src.models.proxy_models import ParsedProxy, SessionInfo


def _make_manager_with_sessions(n: int, daily_limit: int = 50) -> SessionManager:
    """Create a SessionManager with n pre-loaded sessions (no disk/Telethon)."""
    mgr = SessionManager(session_dir="fake", api_id=0, api_hash="", daily_limit=daily_limit)
    today = date.today().isoformat()
    mgr._sessions = [
        SessionInfo(
            session_path=f"session_{i}",
            daily_limit=daily_limit,
            last_reset_date=today,
        )
        for i in range(n)
    ]
    mgr._rr_index = 0
    return mgr


class TestSessionRoundRobin:
    """Property 11: Oturum Round-Robin

    For any N aktif oturum içeren SessionManager, ardışık N adet
    get_next_session() çağrısı her oturumu tam olarak bir kez döndürmeli.

    **Validates: Requirements 6.4**
    """

    @settings(max_examples=100)
    @given(n=st.integers(min_value=1, max_value=20))
    @pytest.mark.asyncio
    async def test_round_robin_covers_all(self, n):
        mgr = _make_manager_with_sessions(n)
        seen = []
        for _ in range(n):
            s = await mgr.get_next_session()
            assert s is not None
            seen.append(s.session_path)
        # Each session exactly once
        assert len(seen) == n
        assert len(set(seen)) == n


class TestCooldownSkipping:
    """Property 12: Cooldown Oturum Atlama

    For any oturum listesi ve bu oturumların bir alt kümesinin cooldown'da
    olması durumunda, get_next_session() cooldown'daki oturumları atlayıp
    yalnızca aktif oturumları döndürmeli.

    **Validates: Requirements 6.5, 6.10**
    """

    @settings(max_examples=100)
    @given(
        n=st.integers(min_value=2, max_value=10),
        cooldown_indices=st.frozensets(st.integers(min_value=0, max_value=9), max_size=5),
    )
    @pytest.mark.asyncio
    async def test_cooldown_sessions_skipped(self, n, cooldown_indices):
        mgr = _make_manager_with_sessions(n)
        # Put some sessions in cooldown
        valid_indices = {i for i in cooldown_indices if i < n}
        for i in valid_indices:
            mgr._sessions[i].cooldown_until = time.time() + 3600

        active_count = n - len(valid_indices)
        if active_count == 0:
            result = await mgr.get_next_session()
            assert result is None
        else:
            for _ in range(active_count):
                s = await mgr.get_next_session()
                assert s is not None
                assert s.cooldown_until <= time.time()


class TestSessionProxyUniqueness:
    """Property 13: Oturum Proxy Benzersizliği

    For any aktif oturum kümesi ve yeterli sayıda proxy, her oturuma
    atanan proxy benzersiz olmalı.

    **Validates: Requirements 6.6**
    """

    @settings(max_examples=100)
    @given(n=st.integers(min_value=1, max_value=10))
    @pytest.mark.asyncio
    async def test_unique_proxy_per_session(self, n):
        mgr = _make_manager_with_sessions(n)
        proxies = [
            ParsedProxy(protocol="http", host=f"10.0.0.{i}", port=8080)
            for i in range(n)
        ]
        for i, session in enumerate(mgr._sessions):
            await mgr.assign_proxy(session, proxies[i])

        assigned = [s.assigned_proxy for s in mgr._sessions]
        assert len(set(assigned)) == n


class TestDailyLimitEnforcement:
    """Property 14: Günlük Limit Uygulaması

    For any oturum, günlük tepki sayısı günlük limite ulaştığında,
    get_next_session() o oturumu atlayıp döndürmemeli.

    **Validates: Requirements 6.9**
    """

    @settings(max_examples=100)
    @given(limit=st.integers(min_value=1, max_value=20))
    @pytest.mark.asyncio
    async def test_daily_limit_blocks_session(self, limit):
        mgr = _make_manager_with_sessions(1, daily_limit=limit)
        session = mgr._sessions[0]
        session.daily_reaction_count = limit  # At limit

        result = await mgr.get_next_session()
        assert result is None  # Should be skipped

    @settings(max_examples=100)
    @given(limit=st.integers(min_value=2, max_value=20))
    @pytest.mark.asyncio
    async def test_under_limit_returns_session(self, limit):
        mgr = _make_manager_with_sessions(1, daily_limit=limit)
        session = mgr._sessions[0]
        session.daily_reaction_count = limit - 1  # Under limit

        result = await mgr.get_next_session()
        assert result is not None
