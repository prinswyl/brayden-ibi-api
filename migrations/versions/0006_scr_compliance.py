"""SCR compliance schema — Single Central Record, safeguarding induction, worker agreements, references

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Enum helpers ──────────────────────────────────────────────────────────────

scr_status_enum = postgresql.ENUM(
    "incomplete", "pending_review", "verified_pending_physical", "compliant", "suspended",
    name="scr_status", create_type=False,
)
reference_status_enum = postgresql.ENUM(
    "pending", "requested", "received_unverified", "verified",
    name="reference_status", create_type=False,
)
dbs_application_status_enum = postgresql.ENUM(
    "not_started", "in_flight", "completed",
    name="dbs_application_status", create_type=False,
)
dbs_update_result_enum = postgresql.ENUM(
    "not_checked", "up_to_date", "new_information", "no_result_found",
    name="dbs_update_result", create_type=False,
)
id_verification_method_enum = postgresql.ENUM(
    "not_selected", "third_party_digital", "school_in_person", "school_video_call",
    name="id_verification_method", create_type=False,
)


def upgrade() -> None:
    # ── Create enum types (one op.execute per statement — asyncpg limitation) ─
    op.execute("DO $$ BEGIN CREATE TYPE scr_status AS ENUM ('incomplete','pending_review','verified_pending_physical','compliant','suspended'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE reference_status AS ENUM ('pending','requested','received_unverified','verified'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE dbs_application_status AS ENUM ('not_started','in_flight','completed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE dbs_update_result AS ENUM ('not_checked','up_to_date','new_information','no_result_found'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE id_verification_method AS ENUM ('not_selected','third_party_digital','school_in_person','school_video_call'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # ── trust_settings ────────────────────────────────────────────────────────
    op.create_table(
        "trust_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("trust_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trusts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("dbs_portal_url", sa.Text, nullable=True),
        sa.Column("dbs_portal_pin", sa.Text, nullable=True),
        sa.Column("dbs_portal_name", sa.Text, nullable=True),
        sa.Column("safeguarding_policy_url", sa.Text, nullable=True),
        sa.Column("safeguarding_policy_storage_path", sa.Text, nullable=True),
        sa.Column("code_of_conduct_url", sa.Text, nullable=True),
        sa.Column("code_of_conduct_storage_path", sa.Text, nullable=True),
        sa.Column("child_protection_policy_url", sa.Text, nullable=True),
        sa.Column("child_protection_policy_storage_path", sa.Text, nullable=True),
        sa.Column("dsl_name", sa.Text, nullable=True),
        sa.Column("dsl_email", sa.Text, nullable=True),
        sa.Column("dsl_phone", sa.Text, nullable=True),
        sa.Column("casual_worker_agreement_version", sa.Text, nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # ── scr_records ───────────────────────────────────────────────────────────
    op.create_table(
        "scr_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("trust_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trusts.id"), nullable=False, index=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),

        # Overall SCR status
        sa.Column("scr_status", scr_status_enum, nullable=False, server_default="incomplete"),

        # Identity verification — initial check
        sa.Column("id_verification_method", id_verification_method_enum, nullable=False, server_default="not_selected"),
        sa.Column("initial_id_checked_date", sa.Date, nullable=True),
        sa.Column("initial_id_checked_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("initial_id_notes", sa.Text, nullable=True),

        # Physical ID — KCSIE hard gate (must happen in person, before or on first shift)
        sa.Column("physical_id_confirmed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("physical_id_confirmed_date", sa.Date, nullable=True),
        sa.Column("physical_id_confirmed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("physical_id_confirmed_location", sa.Text, nullable=True),

        # Right to Work
        sa.Column("rtw_checked_date", sa.Date, nullable=True),
        sa.Column("rtw_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rtw_evidence_type", sa.Text, nullable=True),

        # DBS
        sa.Column("dbs_application_status", dbs_application_status_enum, nullable=False, server_default="not_started"),
        sa.Column("dbs_certificate_number", sa.Text, nullable=True),
        sa.Column("dbs_issue_date", sa.Date, nullable=True),
        sa.Column("dbs_checked_date", sa.Date, nullable=True),
        sa.Column("dbs_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dbs_update_service_linked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("dbs_last_update_check_date", sa.Date, nullable=True),
        sa.Column("dbs_last_update_result", dbs_update_result_enum, nullable=False, server_default="not_checked"),
        sa.Column("external_dbs_portal_reference", sa.Text, nullable=True),

        # Barred list
        sa.Column("barred_list_checked_date", sa.Date, nullable=True),
        sa.Column("barred_list_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),

        # TRA prohibition (teachers/management)
        sa.Column("tra_prohibition_checked_date", sa.Date, nullable=True),
        sa.Column("tra_prohibition_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),

        # Qualifications
        sa.Column("qualifications_checked_date", sa.Date, nullable=True),
        sa.Column("qualifications_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),

        # References
        sa.Column("reference_1_status", reference_status_enum, nullable=False, server_default="pending"),
        sa.Column("reference_1_verified_date", sa.Date, nullable=True),
        sa.Column("reference_1_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reference_2_status", reference_status_enum, nullable=False, server_default="pending"),
        sa.Column("reference_2_verified_date", sa.Date, nullable=True),
        sa.Column("reference_2_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),

        # Overseas checks
        sa.Column("overseas_checks_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("overseas_checks_details", sa.Text, nullable=True),
        sa.Column("overseas_checks_verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("overseas_checks_verified_date", sa.Date, nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── worker_agreements ─────────────────────────────────────────────────────
    op.create_table(
        "worker_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("trust_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trusts.id"), nullable=False, index=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agreement_version", sa.Text, nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.Text, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── worker_references ─────────────────────────────────────────────────────
    op.create_table(
        "worker_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("trust_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trusts.id"), nullable=False, index=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reference_number", sa.Integer, nullable=False),  # 1 or 2
        sa.Column("referee_name", sa.Text, nullable=False),
        sa.Column("referee_job_title", sa.Text, nullable=True),
        sa.Column("referee_organisation", sa.Text, nullable=False),
        sa.Column("referee_email", sa.Text, nullable=False),
        sa.Column("referee_phone", sa.Text, nullable=True),
        sa.Column("relationship_to_worker", sa.Text, nullable=False),
        sa.Column("is_current_or_most_recent_employer", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("worker_consent_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("worker_consent_given_at", sa.DateTime(timezone=True), nullable=True),
        # HR audit trail
        sa.Column("status", reference_status_enum, nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reference_document_path", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── worker_safeguarding_inductions ────────────────────────────────────────
    op.create_table(
        "worker_safeguarding_inductions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("trust_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trusts.id"), nullable=False, index=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        # Gate 1 — KCSIE reading
        sa.Column("kcsie_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kcsie_scroll_depth_pct", sa.Integer, nullable=True),  # 0–100
        sa.Column("kcsie_time_spent_seconds", sa.Integer, nullable=True),
        # Gate 2 — Local policy sign
        sa.Column("policy_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version_signed", sa.Text, nullable=True),
        # Gate 3 — Quiz
        sa.Column("quiz_passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("quiz_passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quiz_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("quiz_last_score", sa.Integer, nullable=True),
        # Overall
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── safeguarding_quiz_questions ───────────────────────────────────────────
    op.create_table(
        "safeguarding_quiz_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("option_a", sa.Text, nullable=False),
        sa.Column("option_b", sa.Text, nullable=False),
        sa.Column("option_c", sa.Text, nullable=False),
        sa.Column("option_d", sa.Text, nullable=False),
        sa.Column("correct_option", sa.Text, nullable=False),  # 'a', 'b', 'c', or 'd'
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── safeguarding_quiz_attempts ────────────────────────────────────────────
    op.create_table(
        "safeguarding_quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("total_questions", sa.Integer, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("answers", postgresql.JSONB, nullable=False),  # {question_id: chosen_option}
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Extend worker_profiles (idempotent) ───────────────────────────────────
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS teacher_reference_number TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS overseas_checks_required BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS overseas_checks_details TEXT")

    # ── Extend dbs_checks (idempotent) ────────────────────────────────────────
    op.execute("ALTER TABLE dbs_checks ADD COLUMN IF NOT EXISTS application_status dbs_application_status NOT NULL DEFAULT 'not_started'")
    op.execute("ALTER TABLE dbs_checks ADD COLUMN IF NOT EXISTS external_portal_reference TEXT")
    op.execute("ALTER TABLE dbs_checks ADD COLUMN IF NOT EXISTS last_update_check_date DATE")
    op.execute("ALTER TABLE dbs_checks ADD COLUMN IF NOT EXISTS last_update_result dbs_update_result NOT NULL DEFAULT 'not_checked'")

    # ── Seed safeguarding quiz questions ──────────────────────────────────────
    op.execute("""
    INSERT INTO safeguarding_quiz_questions (question_text, option_a, option_b, option_c, option_d, correct_option, explanation) VALUES

    ('What should you do FIRST if a child makes a disclosure of abuse to you?',
     'Immediately contact the police',
     'Listen carefully, stay calm, and do not promise confidentiality',
     'Tell the child to speak to their parents',
     'Write a detailed report before doing anything else',
     'b',
     'When a child discloses, you must listen without judgment, remain calm, and never promise confidentiality. The DSL should be informed as soon as possible.'),

    ('Who holds primary responsibility for child protection in a school?',
     'Every member of staff equally',
     'The headteacher only',
     'The Designated Safeguarding Lead (DSL)',
     'The local authority',
     'c',
     'The DSL holds day-to-day responsibility for child protection. All staff must know who the DSL is and how to contact them.'),

    ('Under KCSIE, which of the following is NOT one of the four categories of abuse?',
     'Physical abuse',
     'Financial abuse',
     'Emotional abuse',
     'Sexual abuse',
     'b',
     'The four categories under KCSIE are: physical abuse, emotional abuse, sexual abuse, and neglect. Financial abuse is not a KCSIE category.'),

    ('What is ''county lines'' in the context of child safeguarding?',
     'A boundary marker used in school exclusion zones',
     'Criminal networks using children to transport and sell drugs across regions',
     'A type of online grooming conducted across county borders',
     'A legal term for cross-authority care proceedings',
     'b',
     'County lines refers to criminal gangs exploiting children and vulnerable people to move and sell drugs. Staff should be alert to signs of exploitation.'),

    ('A child tells you something that concerns you but asks you to keep it secret. What should you do?',
     'Keep the secret — the child''s trust is paramount',
     'Tell only the child''s parents',
     'Explain you cannot promise confidentiality and share with the DSL',
     'Make an anonymous referral so the child is not identified',
     'c',
     'You must never promise confidentiality to a child. Explain that you may need to share information to keep them safe and report to the DSL.'),

    ('What does FGM stand for, and what is your legal obligation if you suspect it has been carried out on a child under 18?',
     'Female Genital Mutilation — you must report it directly to the police',
     'Female Gender Monitoring — you must update the child''s school record',
     'Female Genital Mutilation — you must inform the headteacher who decides whether to report',
     'Female Gender Management — there is no legal obligation, only guidance',
     'a',
     'FGM is Female Genital Mutilation. Under the Serious Crime Act 2015, regulated professionals (including teachers) have a mandatory duty to report to police if they discover FGM has been carried out on a girl under 18.'),

    ('What is ''peer-on-peer abuse''?',
     'Bullying carried out by teachers against pupils',
     'Harm caused between children of a similar age or stage of development',
     'Online abuse initiated by anonymous adults posing as peers',
     'Any conflict between two children of the same year group',
     'b',
     'Peer-on-peer abuse includes bullying, physical abuse, sexual violence, sexual harassment, and harmful sexual behaviour between children. It should never be dismissed as normal behaviour.'),

    ('What is the ''Prevent'' duty under the Counter-Terrorism and Security Act 2015?',
     'A duty to prevent children from using social media',
     'A requirement to refer any child who misbehaves to the police',
     'A duty to have due regard to the need to prevent people from being drawn into terrorism',
     'A duty to prevent children from accessing the internet on school premises',
     'c',
     'The Prevent duty requires schools to have due regard to preventing radicalisation and extremism. Staff should be alert to signs that a child may be vulnerable to radicalisation.'),

    ('You notice unexplained bruising on a child. What is the correct action?',
     'Ask the child directly how they got the bruises before doing anything else',
     'Call the child''s parents to ask for an explanation',
     'Ignore it — bruises are common in children',
     'Record your observations and report to the DSL without delay',
     'd',
     'Unexplained bruising is a potential indicator of physical abuse. Do not investigate yourself — record what you have observed and report to the DSL who will determine next steps.'),

    ('What is the purpose of the Single Central Record (SCR)?',
     'A register of all school exclusions',
     'A statutory record of all safer recruitment checks completed for staff and volunteers',
     'A log of all safeguarding disclosures made at the school',
     'A database of all children on the child protection register',
     'b',
     'The SCR is a statutory document that records all pre-employment checks carried out for staff, contractors, and volunteers. Ofsted inspectors use it to verify safer recruitment compliance.'),

    ('Under KCSIE, what should you do if you have concerns about the behaviour of a colleague around children?',
     'Speak to the colleague directly and give them a chance to explain',
     'Report your concerns to the DSL or headteacher immediately',
     'Monitor the situation for two weeks before escalating',
     'Raise it informally with another member of staff first',
     'b',
     'Concerns about a colleague''s conduct must be reported immediately to the DSL or headteacher. Do not investigate or confront the colleague yourself. Allegations are dealt with under the school''s low-level concerns or allegations procedures.'),

    ('What does ''contextual safeguarding'' mean?',
     'Safeguarding that only applies within the school building',
     'A framework for understanding that abuse can occur in contexts beyond the family',
     'A system for categorising children by their risk level',
     'A type of safeguarding training delivered in context-specific settings',
     'b',
     'Contextual safeguarding recognises that children can be harmed in their communities, peer groups, and online spaces, not just within the family. Schools should consider these wider contexts when assessing risk.'),

    ('A child is showing signs of self-harm. What is the correct approach?',
     'Ignore it — self-harm is a private matter',
     'Physically restrain the child to prevent further harm',
     'Stay calm, ensure immediate safety, and report to the DSL',
     'Contact the child''s parents before speaking to the DSL',
     'c',
     'If you are concerned a child is self-harming, prioritise their immediate safety, remain calm and non-judgmental, and report to the DSL. Do not investigate alone or contact parents before consulting the DSL.'),

    ('What is ''harmful sexual behaviour'' (HSB) in the context of safeguarding?',
     'Any romantic relationship between two pupils',
     'Sexual behaviours expressed by children and young people that are inappropriate, problematic, or abusive',
     'Sexual content found on a child''s phone',
     'Only behaviours that result in a criminal conviction',
     'b',
     'HSB encompasses a range of sexual behaviours that are outside what is developmentally expected, including harassment, sharing intimate images, and sexual violence between peers.'),

    ('Which of the following best describes your safeguarding responsibility as a supply or cover worker?',
     'You have no safeguarding responsibility — that belongs to permanent staff',
     'You only need to act if you personally witness an incident',
     'You have the same safeguarding responsibilities as any permanent member of staff',
     'You should defer all concerns to the school''s office manager',
     'c',
     'Every adult working in a school has the same safeguarding duty regardless of whether they are permanent, supply, or voluntary. KCSIE applies to all.')
    """)


def downgrade() -> None:
    op.execute("DELETE FROM safeguarding_quiz_questions")
    op.drop_table("safeguarding_quiz_attempts")
    op.drop_table("safeguarding_quiz_questions")
    op.drop_table("worker_safeguarding_inductions")
    op.drop_table("worker_references")
    op.drop_table("worker_agreements")
    op.drop_table("scr_records")
    op.drop_table("trust_settings")

    op.drop_column("dbs_checks", "last_update_result")
    op.drop_column("dbs_checks", "last_update_check_date")
    op.drop_column("dbs_checks", "external_portal_reference")
    op.drop_column("dbs_checks", "application_status")
    op.drop_column("worker_profiles", "overseas_checks_details")
    op.drop_column("worker_profiles", "overseas_checks_required")
    op.drop_column("worker_profiles", "teacher_reference_number")

    op.execute("DROP TYPE IF EXISTS id_verification_method")
    op.execute("DROP TYPE IF EXISTS dbs_update_result")
    op.execute("DROP TYPE IF EXISTS dbs_application_status")
    op.execute("DROP TYPE IF EXISTS reference_status")
    op.execute("DROP TYPE IF EXISTS scr_status")
