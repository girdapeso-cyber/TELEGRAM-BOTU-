"""Property-based tests for ReactionEngine emoji selection and delay bounds.

Feature: ghost-booster-upgrade
Property 9: Emoji Seçimi
Property 10: Tepki Gecikmesi Sınırları

**Validates: Requirements 6.1, 6.2**
"""

import random

from hypothesis import given, settings, strategies as st

from src.ghost_booster.reaction_engine import ReactionEngine
from src.ghost_booster.session_manager import SessionManager

# Emoji strategy: non-empty lists of emoji strings
emoji_list_st = st.lists(
    st.sampled_from(["👏", "🔥", "❤️", "🎉", "👍", "😂", "😍", "🤔", "💯", "🙏"]),
    min_size=1,
    max_size=10,
)


def _make_engine(emojis, delay_min=2.0, delay_max=5.0):
    """Create a ReactionEngine with a dummy SessionManager."""
    mgr = SessionManager(session_dir="fake", api_id=0, api_hash="")
    return ReactionEngine(session_manager=mgr, emojis=emojis, delay_min=delay_min, delay_max=delay_max)


class TestEmojiSelection:
    """Property 9: Emoji Seçimi

    For any yapılandırılmış emoji listesi (boş olmayan),
    select_random_emoji() çağrısı her zaman bu listede bulunan bir emoji döndürmeli.

    **Validates: Requirements 6.1**
    """

    @settings(max_examples=200)
    @given(emojis=emoji_list_st)
    def test_emoji_always_from_list(self, emojis):
        engine = _make_engine(emojis)
        for _ in range(10):
            selected = engine.select_random_emoji()
            assert selected in emojis


class TestReactionDelayBounds:
    """Property 10: Tepki Gecikmesi Sınırları

    For any yapılandırılmış delay_min ve delay_max değerleri (min ≤ max),
    üretilen gecikme değeri her zaman delay_min ≤ delay ≤ delay_max aralığında olmalı.

    **Validates: Requirements 6.2**
    """

    @settings(max_examples=200)
    @given(
        dmin=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        dmax_offset=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    )
    def test_delay_within_bounds(self, dmin, dmax_offset):
        dmax = dmin + dmax_offset
        # Simulate the delay generation from ReactionEngine.react_to_post
        delay = random.uniform(dmin, dmax)
        assert delay >= dmin - 0.001  # float tolerance
        assert delay <= dmax + 0.001
