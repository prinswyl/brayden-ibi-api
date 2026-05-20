"""
Unit tests for the onboarding status transition graph.

These tests are pure Python — no DB, no network, no fixtures.
"""

import pytest

from app.services.onboarding import _TRANSITIONS, _assert_transition_valid
from app.shared.enums import OnboardingStatus
from app.shared.exceptions import WorkflowError

ALL_STATUSES = list(OnboardingStatus)


class TestTransitionGraph:
    def test_draft_can_submit(self):
        _assert_transition_valid(OnboardingStatus.draft, OnboardingStatus.submitted)

    def test_submitted_can_start_review(self):
        _assert_transition_valid(OnboardingStatus.submitted, OnboardingStatus.under_review)

    def test_submitted_can_be_sent_back_to_draft(self):
        _assert_transition_valid(OnboardingStatus.submitted, OnboardingStatus.draft)

    def test_under_review_can_be_approved(self):
        _assert_transition_valid(OnboardingStatus.under_review, OnboardingStatus.approved)

    def test_under_review_can_be_rejected(self):
        _assert_transition_valid(OnboardingStatus.under_review, OnboardingStatus.rejected)

    def test_approved_can_be_suspended(self):
        _assert_transition_valid(OnboardingStatus.approved, OnboardingStatus.suspended)

    def test_approved_can_expire(self):
        _assert_transition_valid(OnboardingStatus.approved, OnboardingStatus.expired)

    def test_suspended_can_be_reinstated(self):
        _assert_transition_valid(OnboardingStatus.suspended, OnboardingStatus.approved)

    def test_rejected_can_restart_as_draft(self):
        _assert_transition_valid(OnboardingStatus.rejected, OnboardingStatus.draft)

    def test_expired_can_go_back_to_review(self):
        _assert_transition_valid(OnboardingStatus.expired, OnboardingStatus.under_review)


class TestIllegalTransitions:
    def test_draft_cannot_jump_to_approved(self):
        with pytest.raises(WorkflowError):
            _assert_transition_valid(OnboardingStatus.draft, OnboardingStatus.approved)

    def test_draft_cannot_be_suspended_directly(self):
        with pytest.raises(WorkflowError):
            _assert_transition_valid(OnboardingStatus.draft, OnboardingStatus.suspended)

    def test_approved_cannot_go_to_draft(self):
        with pytest.raises(WorkflowError):
            _assert_transition_valid(OnboardingStatus.approved, OnboardingStatus.draft)

    def test_approved_cannot_go_to_submitted(self):
        with pytest.raises(WorkflowError):
            _assert_transition_valid(OnboardingStatus.approved, OnboardingStatus.submitted)

    def test_expired_cannot_go_to_approved_directly(self):
        with pytest.raises(WorkflowError):
            _assert_transition_valid(OnboardingStatus.expired, OnboardingStatus.approved)


class TestTransitionMapCompleteness:
    def test_all_statuses_have_entries(self):
        """Every status must appear in the transition map — even if the allowed set is empty."""
        for status in ALL_STATUSES:
            assert status in _TRANSITIONS, f"{status} missing from _TRANSITIONS"

    def test_all_target_statuses_are_valid(self):
        """All transition targets are real OnboardingStatus values."""
        for source, targets in _TRANSITIONS.items():
            for target in targets:
                assert isinstance(target, OnboardingStatus)

    def test_no_self_transitions(self):
        """A status cannot transition to itself."""
        for status, targets in _TRANSITIONS.items():
            assert status not in targets, f"{status} has a self-loop"
