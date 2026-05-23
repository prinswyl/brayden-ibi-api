"""
Safeguarding induction service.

Manages the three-gate KCSIE induction sequence:
  Gate 1 — KCSIE Part 1 & Annex B reading declaration
  Gate 2 — Local school policies digital signature
  Gate 3 — Safeguarding quiz (100% pass required)

Workers must complete all three gates before their onboarding can be submitted.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scr import (
    SafeguardingQuizAttempt,
    SafeguardingQuizQuestion,
    WorkerSafeguardingInduction,
)
from app.shared.exceptions import NotFoundError, WorkflowError

logger = structlog.get_logger(__name__)

QUIZ_QUESTION_COUNT = 10
PASSING_SCORE = QUIZ_QUESTION_COUNT  # 100% required


class SafeguardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Induction record ──────────────────────────────────────────────────────

    async def get_or_create_induction(self, worker_id: UUID, trust_id: UUID) -> WorkerSafeguardingInduction:
        result = await self._session.execute(
            select(WorkerSafeguardingInduction).where(
                WorkerSafeguardingInduction.worker_id == worker_id
            )
        )
        induction = result.scalar_one_or_none()
        if induction:
            return induction
        induction = WorkerSafeguardingInduction(worker_id=worker_id, trust_id=trust_id)
        self._session.add(induction)
        await self._session.flush()
        return induction

    async def get_induction(self, worker_id: UUID) -> WorkerSafeguardingInduction | None:
        result = await self._session.execute(
            select(WorkerSafeguardingInduction).where(
                WorkerSafeguardingInduction.worker_id == worker_id
            )
        )
        return result.scalar_one_or_none()

    # ── Gate 1: KCSIE reading ─────────────────────────────────────────────────

    async def record_kcsie_read(
        self,
        worker_id: UUID,
        trust_id: UUID,
        *,
        scroll_depth_pct: int,
        time_spent_seconds: int,
    ) -> WorkerSafeguardingInduction:
        if scroll_depth_pct < 90:
            raise WorkflowError("KCSIE document must be scrolled to at least 90% before declaration.")
        if time_spent_seconds < 30:
            raise WorkflowError("Minimum reading time not reached.")

        induction = await self.get_or_create_induction(worker_id, trust_id)
        now = datetime.now(UTC)
        induction.kcsie_read_at = now
        induction.kcsie_scroll_depth_pct = scroll_depth_pct
        induction.kcsie_time_spent_seconds = time_spent_seconds
        await self._check_complete(induction)
        return induction

    # ── Gate 2: Policy signature ──────────────────────────────────────────────

    async def record_policy_signed(
        self,
        worker_id: UUID,
        trust_id: UUID,
        *,
        policy_version: str,
    ) -> WorkerSafeguardingInduction:
        induction = await self.get_or_create_induction(worker_id, trust_id)
        if not induction.kcsie_read_at:
            raise WorkflowError("Gate 1 (KCSIE reading) must be completed before signing policies.")
        induction.policy_signed_at = datetime.now(UTC)
        induction.policy_version_signed = policy_version
        await self._check_complete(induction)
        return induction

    # ── Gate 3: Quiz ──────────────────────────────────────────────────────────

    async def get_quiz_questions(self) -> list[SafeguardingQuizQuestion]:
        """Returns a random selection of active questions (without correct_option)."""
        result = await self._session.execute(
            select(SafeguardingQuizQuestion).where(SafeguardingQuizQuestion.is_active == True)
        )
        all_questions = result.scalars().all()
        if len(all_questions) < QUIZ_QUESTION_COUNT:
            raise WorkflowError(f"Not enough quiz questions available (need {QUIZ_QUESTION_COUNT}).")
        return random.sample(list(all_questions), QUIZ_QUESTION_COUNT)

    async def submit_quiz(
        self,
        worker_id: UUID,
        trust_id: UUID,
        *,
        answers: dict[str, str],  # {question_id: chosen_option}
    ) -> tuple[WorkerSafeguardingInduction, SafeguardingQuizAttempt]:
        induction = await self.get_or_create_induction(worker_id, trust_id)
        if not induction.policy_signed_at:
            raise WorkflowError("Gate 2 (policy signature) must be completed before taking the quiz.")
        if induction.quiz_passed:
            raise WorkflowError("Quiz has already been passed.")

        # Fetch questions for the submitted IDs
        question_ids = [UUID(qid) for qid in answers.keys()]
        result = await self._session.execute(
            select(SafeguardingQuizQuestion).where(
                SafeguardingQuizQuestion.id.in_(question_ids)
            )
        )
        questions = {str(q.id): q for q in result.scalars().all()}

        if len(questions) != QUIZ_QUESTION_COUNT:
            raise WorkflowError("Invalid question set submitted.")

        # Score
        score = sum(
            1 for qid, chosen in answers.items()
            if qid in questions and questions[qid].correct_option == chosen
        )
        passed = score == QUIZ_QUESTION_COUNT

        attempt = SafeguardingQuizAttempt(
            worker_id=worker_id,
            score=score,
            total_questions=QUIZ_QUESTION_COUNT,
            passed=passed,
            answers=answers,
            attempted_at=datetime.now(UTC),
        )
        self._session.add(attempt)

        induction.quiz_attempts += 1
        induction.quiz_last_score = score

        if passed:
            induction.quiz_passed = True
            induction.quiz_passed_at = datetime.now(UTC)
            await self._check_complete(induction)

        await self._session.flush()
        return induction, attempt

    def is_complete(self, induction: WorkerSafeguardingInduction) -> bool:
        return (
            induction.kcsie_read_at is not None
            and induction.policy_signed_at is not None
            and induction.quiz_passed
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _check_complete(self, induction: WorkerSafeguardingInduction) -> None:
        if self.is_complete(induction) and not induction.completed_at:
            induction.completed_at = datetime.now(UTC)
            logger.info("safeguarding_induction_completed", worker_id=induction.worker_id)
