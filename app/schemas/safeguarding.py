"""Pydantic schemas for the safeguarding induction domain."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class QuizQuestionResponse(BaseModel):
    """Quiz question sent to worker — correct_option is deliberately excluded."""
    id: UUID
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str

    model_config = {"from_attributes": True}


class QuizSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(..., description="Map of question_id (str) to chosen option ('a','b','c','d')")


class QuizResultResponse(BaseModel):
    score: int
    total_questions: int
    passed: bool
    correct_answers: dict[str, str]  # question_id → correct option (revealed after attempt)
    explanations: dict[str, str]     # question_id → explanation text


class SafeguardingInductionStatus(BaseModel):
    worker_id: UUID
    kcsie_read_at: datetime | None
    kcsie_scroll_depth_pct: int | None
    policy_signed_at: datetime | None
    policy_version_signed: str | None
    quiz_passed: bool
    quiz_passed_at: datetime | None
    quiz_attempts: int
    quiz_last_score: int | None
    completed_at: datetime | None

    gate_1_complete: bool
    gate_2_complete: bool
    gate_3_complete: bool
    all_complete: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_gates(cls, induction) -> "SafeguardingInductionStatus":
        return cls(
            worker_id=induction.worker_id,
            kcsie_read_at=induction.kcsie_read_at,
            kcsie_scroll_depth_pct=induction.kcsie_scroll_depth_pct,
            policy_signed_at=induction.policy_signed_at,
            policy_version_signed=induction.policy_version_signed,
            quiz_passed=induction.quiz_passed,
            quiz_passed_at=induction.quiz_passed_at,
            quiz_attempts=induction.quiz_attempts,
            quiz_last_score=induction.quiz_last_score,
            completed_at=induction.completed_at,
            gate_1_complete=induction.kcsie_read_at is not None,
            gate_2_complete=induction.policy_signed_at is not None,
            gate_3_complete=induction.quiz_passed,
            all_complete=induction.completed_at is not None,
        )


class KCSIEReadRequest(BaseModel):
    scroll_depth_pct: int = Field(..., ge=0, le=100)
    time_spent_seconds: int = Field(..., ge=0)


class PolicySignRequest(BaseModel):
    policy_version: str
