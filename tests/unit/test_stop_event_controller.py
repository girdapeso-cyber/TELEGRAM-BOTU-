"""Unit tests for StopEventController.

Gereksinimler: 2.1 (stop signal ile döngü durdurma), 2.2 (thread sonlandırma)
"""

import threading
import time

import pytest

from src.services.stop_event_controller import StopEventController


class TestStopEventControllerBasic:
    """Basic functionality tests."""

    def test_initial_state_is_stopped(self):
        """No event created yet means is_stopped returns True."""
        controller = StopEventController()
        assert controller.is_stopped() is True

    def test_create_new_event_returns_event(self):
        controller = StopEventController()
        event = controller.create_new_event()
        assert isinstance(event, threading.Event)

    def test_new_event_is_not_set(self):
        controller = StopEventController()
        event = controller.create_new_event()
        assert not event.is_set()

    def test_is_stopped_false_after_create(self):
        controller = StopEventController()
        controller.create_new_event()
        assert controller.is_stopped() is False

    def test_signal_stop_sets_event(self):
        controller = StopEventController()
        event = controller.create_new_event()
        controller.signal_stop()
        assert event.is_set()
        assert controller.is_stopped() is True

    def test_signal_stop_without_event_does_nothing(self):
        controller = StopEventController()
        controller.signal_stop()  # should not raise
        assert controller.is_stopped() is True


class TestStopEventControllerEventReplacement:
    """Tests for event replacement behavior (Requirement 2.1)."""

    def test_create_new_event_stops_old_event(self):
        """Creating a new event should set the old one (Req 2.1)."""
        controller = StopEventController()
        old_event = controller.create_new_event()
        new_event = controller.create_new_event()
        assert old_event.is_set(), "Old event should be set when new event is created"
        assert not new_event.is_set(), "New event should not be set"

    def test_multiple_replacements(self):
        controller = StopEventController()
        events = [controller.create_new_event() for _ in range(5)]
        # All events except the last should be set
        for e in events[:-1]:
            assert e.is_set()
        assert not events[-1].is_set()

    def test_is_stopped_reflects_current_event(self):
        controller = StopEventController()
        controller.create_new_event()
        assert controller.is_stopped() is False
        controller.signal_stop()
        assert controller.is_stopped() is True
        controller.create_new_event()
        assert controller.is_stopped() is False


class TestStopEventControllerThreadSafety:
    """Thread-safety tests (Requirement 2.2)."""

    def test_concurrent_signal_stop(self):
        """Multiple threads calling signal_stop should not raise."""
        controller = StopEventController()
        controller.create_new_event()
        errors = []

        def stop_worker():
            try:
                controller.signal_stop()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=stop_worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert controller.is_stopped() is True

    def test_concurrent_create_and_stop(self):
        """Concurrent create_new_event and signal_stop should not raise."""
        controller = StopEventController()
        errors = []

        def create_worker():
            try:
                for _ in range(50):
                    controller.create_new_event()
            except Exception as e:
                errors.append(e)

        def stop_worker():
            try:
                for _ in range(50):
                    controller.signal_stop()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=create_worker)
        t2 = threading.Thread(target=stop_worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert len(errors) == 0

    def test_thread_observes_stop_signal(self):
        """A worker thread should observe the stop signal set from main thread."""
        controller = StopEventController()
        event = controller.create_new_event()
        observed = threading.Event()

        def worker():
            while not event.is_set():
                time.sleep(0.01)
            observed.set()

        t = threading.Thread(target=worker)
        t.start()
        time.sleep(0.05)
        controller.signal_stop()
        t.join(timeout=5)
        assert observed.is_set(), "Worker thread should have observed the stop signal"
