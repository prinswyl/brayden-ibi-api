"""
Worker self-service endpoints.

All routes operate on the authenticated worker's own profile.
No worker_id path param — identity is derived from the JWT.

  GET    /api/v1/workers/me
  PATCH  /api/v1/workers/me
  POST   /api/v1/workers/me/agreement
  GET    /api/v1/workers/me/scr
  GET    /api/v1/workers/me/references
  POST   /api/v1/workers/me/references
  GET    /api/v1/workers/me/safeguarding
  POST   /api/v1/workers/me/safeguarding/kcsie-read
  POST   /api/v1/workers/me/safeguarding/policy-signed
  GET    /api/v1/workers/me/safeguarding/quiz
  POST   /api/v1/workers/me/safeguarding/quiz-submit
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.models.scr import WorkerAgreement, WorkerReference
from app.models.worker import WorkerProfile
from app.repositories.worker import WorkerRepository
from app.schemas.safeguarding import (
    KCSIEReadRequest,
    PolicySignRequest,
    QuizResultResponse,
    QuizSubmitRequest,
    SafeguardingInductionStatus,
)
from app.schemas.scr import SCRStatusSummary
from app.schemas.worker_self import (
    SignAgreementRequest,
    WorkerMeResponse,
    WorkerReferenceRequest,
    WorkerReferenceResponse,
    WorkerSelfUpdateRequest,
    WorkerSchoolPreferenceResponse,
    WorkerSchoolPreferencesUpsert,
)
from app.services.safeguarding import SafeguardingService
from app.services.scr import SCRService
from app.services.trust_settings import TrustSettingsService

router = APIRouter(prefix="/workers/me", tags=["Worker Self-Service"])


async def _get_worker_profile(current_user: CurrentUser, db: AsyncSession) -> WorkerProfile:
    repo = WorkerRepository(db)
    worker = await repo.get_by_user_id(current_user.user_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker profile not found. Contact HR to set up your account.")
    return worker


@router.get("", response_model=WorkerMeResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.user import UserRepository
    worker = await _get_worker_profile(current_user, db)
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id_or_404(current_user.user_id)

    scr_svc = SCRService(db)
    scr = await scr_svc.get_by_worker(worker.id)

    # Check agreement
    agreement_result = await db.execute(
        select(WorkerAgreement).where(WorkerAgreement.worker_id == worker.id).limit(1)
    )
    agreement_signed = agreement_result.scalar_one_or_none() is not None

    # Check safeguarding
    saf_svc = SafeguardingService(db)
    induction = await saf_svc.get_induction(worker.id)
    safeguarding_complete = induction is not None and induction.completed_at is not None

    return WorkerMeResponse(
        user_id=user.id,
        worker_id=worker.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        preferred_name=worker.preferred_name,
        phone=user.phone,
        date_of_birth=worker.date_of_birth,
        ni_number=worker.ni_number,
        home_address=worker.home_address,
        home_city=worker.home_city,
        home_county=worker.home_county,
        home_postcode=worker.home_postcode,
        teacher_reference_number=worker.teacher_reference_number,
        emergency_contact_name=worker.emergency_contact_name,
        emergency_contact_phone=worker.emergency_contact_phone,
        gender=worker.gender,
        ethnicity=worker.ethnicity,
        disability_declared=worker.disability_declared,
        overseas_checks_required=worker.overseas_checks_required,
        overseas_checks_details=worker.overseas_checks_details,
        rtw_doc_type=worker.rtw_doc_type,
        rtw_doc_number=worker.rtw_doc_number,
        rtw_passport_number=worker.rtw_passport_number,
        rtw_passport_issue_date=worker.rtw_passport_issue_date,
        rtw_passport_expiry_date=worker.rtw_passport_expiry_date,
        onboarding_status=worker.onboarding_status.value,
        scr_status=scr.scr_status if scr else None,
        agreement_signed=agreement_signed,
        safeguarding_complete=safeguarding_complete,
    )


@router.patch("", response_model=WorkerMeResponse)
async def update_me(
    body: WorkerSelfUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    repo = WorkerRepository(db)

    update_fields = body.model_dump(exclude_none=True)
    # phone, first_name, last_name are on User, not WorkerProfile — update separately
    phone = update_fields.pop("phone", None)
    first_name = update_fields.pop("first_name", None)
    last_name = update_fields.pop("last_name", None)
    if update_fields:
        await repo.update(worker, **update_fields)
    if phone is not None or first_name is not None or last_name is not None:
        from app.repositories.user import UserRepository
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id_or_404(current_user.user_id)
        user_updates: dict = {}
        if phone is not None:
            user_updates["phone"] = phone
        if first_name is not None:
            user_updates["first_name"] = first_name
        if last_name is not None:
            user_updates["last_name"] = last_name
        await user_repo.update(user, **user_updates)

    await db.commit()
    return await get_me(current_user=current_user, db=db)


@router.get("/trust-settings", response_model=TrustSettingsResponse)
async def get_worker_trust_settings(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the trust's public-facing configuration needed during worker onboarding."""
    svc = TrustSettingsService(db)
    settings = await svc.get(current_user.trust_id)
    if not settings:
        from app.models.scr import TrustSettings as TrustSettingsModel
        return TrustSettingsResponse.model_validate(TrustSettingsModel(
            trust_id=current_user.trust_id,
            casual_worker_agreement_version="1.0",
        ))
    return TrustSettingsResponse.model_validate(settings)


@router.post("/agreement", status_code=201)
async def sign_agreement(
    body: SignAgreementRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)

    # Idempotent — if already signed the current version, return existing
    existing = await db.execute(
        select(WorkerAgreement)
        .where(
            WorkerAgreement.worker_id == worker.id,
            WorkerAgreement.agreement_version == body.agreement_version,
        )
        .limit(1)
    )
    if existing.scalar_one_or_none():
        return {"message": "Agreement already signed for this version."}

    agreement = WorkerAgreement(
        worker_id=worker.id,
        trust_id=worker.trust_id,
        agreement_version=body.agreement_version,
        signed_at=datetime.now(UTC),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        created_at=datetime.now(UTC),
    )
    db.add(agreement)
    await db.commit()
    return {"message": "Agreement signed successfully.", "signed_at": agreement.signed_at}


@router.get("/scr", response_model=SCRStatusSummary)
async def get_my_scr(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    scr_svc = SCRService(db)
    scr = await scr_svc.get_by_worker(worker.id)
    if not scr:
        raise HTTPException(status_code=404, detail="SCR record not yet created.")
    return SCRStatusSummary.model_validate(scr)


@router.get("/references", response_model=list[WorkerReferenceResponse])
async def get_my_references(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    result = await db.execute(
        select(WorkerReference)
        .where(WorkerReference.worker_id == worker.id)
        .order_by(WorkerReference.reference_number)
    )
    return [WorkerReferenceResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/references", response_model=WorkerReferenceResponse, status_code=201)
async def submit_reference(
    body: WorkerReferenceRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.worker_consent_given:
        raise HTTPException(status_code=422, detail="Consent to contact referee is required.")

    worker = await _get_worker_profile(current_user, db)

    # Replace existing reference with same number if present
    existing = await db.execute(
        select(WorkerReference).where(
            WorkerReference.worker_id == worker.id,
            WorkerReference.reference_number == body.reference_number,
        )
    )
    ref = existing.scalar_one_or_none()
    now = datetime.now(UTC)

    if ref:
        for field, value in body.model_dump().items():
            setattr(ref, field, value)
        ref.worker_consent_given_at = now
    else:
        ref = WorkerReference(
            worker_id=worker.id,
            trust_id=worker.trust_id,
            worker_consent_given_at=now,
            **body.model_dump(),
        )
        db.add(ref)

    await db.commit()
    await db.refresh(ref)
    return WorkerReferenceResponse.model_validate(ref)


# ── Safeguarding routes ───────────────────────────────────────────────────────

@router.get("/safeguarding", response_model=SafeguardingInductionStatus)
async def get_safeguarding_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    saf_svc = SafeguardingService(db)
    induction = await saf_svc.get_induction(worker.id)
    if not induction:
        # Return empty state
        from app.models.scr import WorkerSafeguardingInduction
        induction = WorkerSafeguardingInduction(worker_id=worker.id, trust_id=worker.trust_id)
    return SafeguardingInductionStatus.from_orm_with_gates(induction)


@router.post("/safeguarding/kcsie-read", response_model=SafeguardingInductionStatus)
async def record_kcsie_read(
    body: KCSIEReadRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    saf_svc = SafeguardingService(db)
    induction = await saf_svc.record_kcsie_read(
        worker.id, worker.trust_id,
        scroll_depth_pct=body.scroll_depth_pct,
        time_spent_seconds=body.time_spent_seconds,
    )
    await db.commit()
    return SafeguardingInductionStatus.from_orm_with_gates(induction)


@router.post("/safeguarding/policy-signed", response_model=SafeguardingInductionStatus)
async def record_policy_signed(
    body: PolicySignRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    saf_svc = SafeguardingService(db)
    induction = await saf_svc.record_policy_signed(
        worker.id, worker.trust_id, policy_version=body.policy_version
    )
    await db.commit()
    return SafeguardingInductionStatus.from_orm_with_gates(induction)


@router.get("/safeguarding/quiz", response_model=list)
async def get_quiz_questions(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    saf_svc = SafeguardingService(db)
    induction = await saf_svc.get_induction(worker.id)
    if induction and induction.quiz_passed:
        raise HTTPException(status_code=409, detail="Quiz already passed.")
    questions = await saf_svc.get_quiz_questions()
    from app.schemas.safeguarding import QuizQuestionResponse
    return [QuizQuestionResponse.model_validate(q) for q in questions]


@router.post("/safeguarding/quiz-submit", response_model=QuizResultResponse)
async def submit_quiz(
    body: QuizSubmitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await _get_worker_profile(current_user, db)
    saf_svc = SafeguardingService(db)
    induction, attempt = await saf_svc.submit_quiz(
        worker.id, worker.trust_id, answers=body.answers
    )
    await db.commit()

    # Fetch questions for explanations (always reveal after attempt)
    from sqlalchemy import select as sa_select
    from uuid import UUID as _UUID
    from app.models.scr import SafeguardingQuizQuestion
    q_ids = [_UUID(qid) for qid in body.answers.keys()]
    q_result = await db.execute(
        sa_select(SafeguardingQuizQuestion).where(SafeguardingQuizQuestion.id.in_(q_ids))
    )
    questions = {str(q.id): q for q in q_result.scalars().all()}

    return QuizResultResponse(
        score=attempt.score,
        total_questions=attempt.total_questions,
        passed=attempt.passed,
        correct_answers={qid: q.correct_option for qid, q in questions.items()},
        explanations={qid: (q.explanation or "") for qid, q in questions.items()},
    )


# ── School preferences ────────────────────────────────────────────────────────

@router.get(
    "/school-preferences",
    response_model=list[WorkerSchoolPreferenceResponse],
    summary="Get worker's ranked school preferences",
)
async def get_school_preferences(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkerSchoolPreferenceResponse]:
    from sqlalchemy import select as sa_select2
    from app.models.worker import WorkerSchoolPreference
    from app.models.school import School

    worker = await _get_worker_profile(current_user, db)
    result = await db.execute(
        sa_select2(WorkerSchoolPreference, School)
        .join(School, School.id == WorkerSchoolPreference.school_id)
        .where(WorkerSchoolPreference.worker_id == worker.id)
        .order_by(WorkerSchoolPreference.rank)
    )
    return [
        WorkerSchoolPreferenceResponse(
            rank=pref.rank,
            school_id=pref.school_id,
            school_name=school.name,
            school_city=school.city,
            school_postcode=school.postcode,
        )
        for pref, school in result.all()
    ]


@router.put(
    "/school-preferences",
    response_model=list[WorkerSchoolPreferenceResponse],
    summary="Set worker's ranked school preferences (replaces all existing)",
)
async def set_school_preferences(
    body: WorkerSchoolPreferencesUpsert,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkerSchoolPreferenceResponse]:
    from sqlalchemy import select as sa_select3, delete as sa_delete
    from app.models.worker import WorkerSchoolPreference
    from app.models.school import School

    worker = await _get_worker_profile(current_user, db)

    # Validate all referenced schools belong to the worker's trust
    school_ids = [p.school_id for p in body.preferences]
    schools_result = await db.execute(
        sa_select3(School).where(
            School.id.in_(school_ids),
            School.trust_id == worker.trust_id,
            School.deleted_at.is_(None),
        )
    )
    schools_map = {s.id: s for s in schools_result.scalars().all()}
    missing = [str(sid) for sid in school_ids if sid not in schools_map]
    if missing:
        raise HTTPException(status_code=422, detail=f"Schools not found in trust: {missing}")

    # Replace all preferences atomically
    await db.execute(
        sa_delete(WorkerSchoolPreference).where(WorkerSchoolPreference.worker_id == worker.id)
    )
    for item in body.preferences:
        db.add(WorkerSchoolPreference(
            worker_id=worker.id,
            trust_id=worker.trust_id,
            school_id=item.school_id,
            rank=item.rank,
        ))
    await db.commit()

    return [
        WorkerSchoolPreferenceResponse(
            rank=item.rank,
            school_id=item.school_id,
            school_name=schools_map[item.school_id].name,
            school_city=schools_map[item.school_id].city,
            school_postcode=schools_map[item.school_id].postcode,
        )
        for item in sorted(body.preferences, key=lambda x: x.rank)
    ]
