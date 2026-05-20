"""Unit tests for the booking state machine transition graph."""

import pytest

from app.services.booking import _TRANSITIONS, _assert_transition
from app.shared.enums import BookingStatus
from app.shared.exceptions import WorkflowError


def test_requested_can_go_to_offered():
    _assert_transition(BookingStatus.requested, BookingStatus.offered)


def test_requested_can_be_cancelled():
    _assert_transition(BookingStatus.requested, BookingStatus.cancelled)


def test_offered_can_be_accepted():
    _assert_transition(BookingStatus.offered, BookingStatus.accepted)


def test_offered_can_expire():
    _assert_transition(BookingStatus.offered, BookingStatus.expired)


def test_offered_can_be_cancelled():
    _assert_transition(BookingStatus.offered, BookingStatus.cancelled)


def test_accepted_can_be_confirmed():
    _assert_transition(BookingStatus.accepted, BookingStatus.confirmed)


def test_accepted_can_be_cancelled():
    _assert_transition(BookingStatus.accepted, BookingStatus.cancelled)


def test_confirmed_can_check_in():
    _assert_transition(BookingStatus.confirmed, BookingStatus.checked_in)


def test_confirmed_can_be_cancelled():
    _assert_transition(BookingStatus.confirmed, BookingStatus.cancelled)


def test_confirmed_can_be_no_show():
    _assert_transition(BookingStatus.confirmed, BookingStatus.no_show)


def test_checked_in_can_complete():
    _assert_transition(BookingStatus.checked_in, BookingStatus.completed)


def test_checked_in_can_be_no_show():
    _assert_transition(BookingStatus.checked_in, BookingStatus.no_show)


def test_completed_is_terminal():
    assert _TRANSITIONS[BookingStatus.completed] == set()


def test_cancelled_is_terminal():
    assert _TRANSITIONS[BookingStatus.cancelled] == set()


def test_expired_is_terminal():
    assert _TRANSITIONS[BookingStatus.expired] == set()


def test_no_show_is_terminal():
    assert _TRANSITIONS[BookingStatus.no_show] == set()


def test_cannot_skip_from_requested_to_confirmed():
    with pytest.raises(WorkflowError):
        _assert_transition(BookingStatus.requested, BookingStatus.confirmed)


def test_cannot_skip_from_requested_to_checked_in():
    with pytest.raises(WorkflowError):
        _assert_transition(BookingStatus.requested, BookingStatus.checked_in)


def test_cannot_go_backwards_from_confirmed():
    with pytest.raises(WorkflowError):
        _assert_transition(BookingStatus.confirmed, BookingStatus.requested)


def test_cannot_reopen_completed():
    with pytest.raises(WorkflowError):
        _assert_transition(BookingStatus.completed, BookingStatus.confirmed)


def test_cannot_reopen_cancelled():
    with pytest.raises(WorkflowError):
        _assert_transition(BookingStatus.cancelled, BookingStatus.requested)


def test_all_statuses_in_transition_table():
    """Every BookingStatus must appear as a key in _TRANSITIONS."""
    for status in BookingStatus:
        assert status in _TRANSITIONS, f"{status} missing from _TRANSITIONS"
