"""
agents/document_validator.py
===========================
Validation utilities for Document Verification Agent.
"""

from __future__ import annotations

from typing import Any, List

from state import ValidationError, ExtractedDocuments, ClaimState


def run_validation_checks(
    docs: ExtractedDocuments,
    state: ClaimState
) -> List[ValidationError]:
    """
    Implement all hard rule checks from POL-001 Section 7.
    Returns list of ValidationError objects.
    """
    errors: List[ValidationError] = []

    ps = docs.policy_schedule
    rc = docs.rc
    dl = docs.dl
    cf = docs.claim_form

    # RULE-M-001: Missing RC or DL → INCOMPLETE (handled by DCS)
    if not rc:
        errors.append(ValidationError(
            doc_code="DOC-001", field="rc",
            rule="RULE-M-001", severity="HARD",
            message="Registration Certificate (RC) is missing."
        ))
    if not dl:
        errors.append(ValidationError(
            doc_code="DOC-002", field="dl",
            rule="RULE-M-001", severity="HARD",
            message="Driver's License (DL) is missing."
        ))

    # RULE-M-002: Policy expiry check
    if ps and cf:
        if ps.policy_end_date and cf.accident_date:
            if ps.policy_end_date < cf.accident_date:
                errors.append(ValidationError(
                    doc_code="DOC-003", field="policy_end_date",
                    rule="RULE-M-002", severity="HARD",
                    message=(
                        f"Policy expired on {ps.policy_end_date} "
                        f"before accident date {cf.accident_date}. AUTO-REJECT."
                    )
                ))

    # RULE-M-003: Engine/Chassis number match
    if rc and ps:
        rc_reg = (rc.registration_number or "").strip().upper()
        ps_reg = (ps.vehicle_registration or "").strip().upper()
        if rc_reg and ps_reg and rc_reg != ps_reg:
            errors.append(ValidationError(
                doc_code="DOC-001", field="registration_number",
                rule="RULE-M-003", severity="HARD",
                message=(
                    f"Registration number mismatch: RC={rc_reg} "
                    f"vs Policy={ps_reg}. FLAG FOR HUMAN REVIEW."
                )
            ))

    # DL validity check (Exclusion E-002)
    if dl and cf:
        if dl.dl_validity_date and cf.accident_date:
            if dl.dl_validity_date < cf.accident_date:
                errors.append(ValidationError(
                    doc_code="DOC-002", field="dl_validity_date",
                    rule="E-002", severity="HARD",
                    message=(
                        f"DL expired on {dl.dl_validity_date} "
                        f"before accident date {cf.accident_date}. AUTO-REJECT."
                    )
                ))

    # Claim form must have signature (DOC-004 rejection trigger)
    if cf and not cf.claimant_signature_present:
        errors.append(ValidationError(
            doc_code="DOC-004", field="claimant_signature_present",
            rule="DOC-004-SIG", severity="SOFT",
            message="Claim form is missing claimant signature. INCOMPLETE status."
        ))

    # Photo manipulation check (fraud indicator RF-B-001)
    if docs.photos and docs.photos.ai_manipulation_score > 0.7:
        errors.append(ValidationError(
            doc_code="DOC-011", field="ai_manipulation_score",
            rule="RF-B-001", severity="HARD",
            message=(
                f"Photo manipulation score {docs.photos.ai_manipulation_score:.2f} "
                f"exceeds 0.7 threshold. FRAUD FLAG."
            )
        ))

    return errors