"""Unit tests for ProxyInfo, EventInfo, and CycleState dataclasses."""

import threading
import time

import pytest

from src.models.data_models import CycleState, EventInfo, ProxyInfo


class TestProxyInfo:
    """Unit tests for ProxyInfo dataclass."""

    def test_http_proxy_to_dict(self):
        proxy = ProxyInfo(address="1.2.3.4:8080", proxy_type="http")
        result = proxy.to_proxy_dict()
        assert result == {"http": "http://1.2.3.4:8080", "https": "http://1.2.3.4:8080"}

    def test_https_proxy_to_dict(self):
        proxy = ProxyInfo(address="5.6.7.8:3128", proxy_type="https")
        result = proxy.to_proxy_dict()
        assert result == {"http": "http://5.6.7.8:3128", "https": "http://5.6.7.8:3128"}

    def test_socks5_proxy_to_dict(self):
        proxy = ProxyInfo(address="10.0.0.1:1080", proxy_type="socks5")
        result = proxy.to_proxy_dict()
        assert result == {
            "http": "socks5://10.0.0.1:1080",
            "https": "socks5://10.0.0.1:1080",
        }

    def test_proxy_stores_address_and_type(self):
        proxy = ProxyInfo(address="192.168.1.1:9090", proxy_type="http")
        assert proxy.address == "192.168.1.1:9090"
        assert proxy.proxy_type == "http"

    def test_proxy_dict_has_both_keys(self):
        proxy = ProxyInfo(address="1.1.1.1:80", proxy_type="http")
        result = proxy.to_proxy_dict()
        assert "http" in result
        assert "https" in result


class TestEventInfo:
    """Unit tests for EventInfo dataclass."""

    def test_create_event_info(self):
        event = EventInfo(
            channel="KRBZ_VIP_TR",
            message_id="12345",
            url="https://t.me/KRBZ_VIP_TR/12345",
            timestamp=1700000000.0,
        )
        assert event.channel == "KRBZ_VIP_TR"
        assert event.message_id == "12345"
        assert event.url == "https://t.me/KRBZ_VIP_TR/12345"
        assert event.timestamp == 1700000000.0

    def test_event_info_stores_all_fields(self):
        ts = time.time()
        event = EventInfo(
            channel="test_channel",
            message_id="999",
            url="https://t.me/test_channel/999",
            timestamp=ts,
        )
        assert event.channel == "test_channel"
        assert event.message_id == "999"
        assert event.timestamp == ts


class TestCycleState:
    """Unit tests for CycleState dataclass."""

    def _make_event_info(self) -> EventInfo:
        return EventInfo(
            channel="KRBZ_VIP_TR",
            message_id="100",
            url="https://t.me/KRBZ_VIP_TR/100",
            timestamp=1700000000.0,
        )

    def test_create_with_defaults(self):
        event = self._make_event_info()
        state = CycleState(event_info=event)
        assert state.event_info is event
        assert isinstance(state.stop_event, threading.Event)
        assert state.thread_handle is None
        assert state.is_running is False

    def test_stop_event_is_not_set_by_default(self):
        state = CycleState(event_info=self._make_event_info())
        assert not state.stop_event.is_set()

    def test_stop_event_can_be_signaled(self):
        state = CycleState(event_info=self._make_event_info())
        state.stop_event.set()
        assert state.stop_event.is_set()

    def test_is_running_flag(self):
        state = CycleState(event_info=self._make_event_info(), is_running=True)
        assert state.is_running is True

    def test_thread_handle_assignment(self):
        state = CycleState(event_info=self._make_event_info())
        t = threading.Thread(target=lambda: None)
        state.thread_handle = t
        assert state.thread_handle is t

    def test_each_instance_gets_unique_stop_event(self):
        event = self._make_event_info()
        state1 = CycleState(event_info=event)
        state2 = CycleState(event_info=event)
        assert state1.stop_event is not state2.stop_event
