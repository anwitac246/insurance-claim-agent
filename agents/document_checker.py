"""
agents/document_checker.py
==========================
Document checking utilities for Document Verification Agent.
Handles missing document detection and Document Completeness Score computation.
"""

from __future__ import annotations

from typing import Any, List, Set

from state import MissingDocument, ClaimState


# DOC codes that are always Tier-1 (required for ALL claims)
TIER1_DOCS = {"DOC-001", "DOC-002", "DOC-003", "DOC-004"}

# Maps claim_type → additional required doc codes
CLAIM_TYPE_DOC_MAP: dict[str, list[str]] = {
    "OWN_DAMAGE":   ["DOC-005", "DOC-011"],
    "THIRD_PARTY":  ["DOC-008", "DOC-011"],
    "THEFT":        ["DOC-008"],
    "FIRE":         ["DOC-008", "DOC-011"],
    "FLOOD":        ["DOC-009", "DOC-011"],
    "NATURAL":      ["DOC-009", "DOC-011"],
}

# Trigger rules that require FIR (per POL-002 DOC-008)
FIR_REQUIRED_CAUSES = {
    "theft", "fire", "arson", "third_party_injury",
    "third_party_death", "hit_and_run", "major_collision",
}


def determine_required_docs(state: ClaimState) -> Set[str]:
    """
    Combine Tier-1 mandatory docs with claim-type-specific docs.
    Also adds FIR (DOC-008) if accident cause triggers it.
    """
    required = set(TIER1_DOCS)

    # Claim type extras
    extras = CLAIM_TYPE_DOC_MAP.get(state.claim_type.upper(), [])
    required.update(extras)

    # FIR trigger from claim form (if already partially extracted)
    if state.document_agent_output:
        cf = state.document_agent_output.extracted.claim_form
        if cf and cf.accident_cause:
            if cf.accident_cause.lower() in FIR_REQUIRED_CAUSES:
                required.add("DOC-008")

    # KYC for high-value claims (threshold from RULE-M-005)
    # We don't know the estimate yet at this stage, but add it
    # if a repair estimate is being submitted
    if "DOC-005" in required:
        required.add("DOC-010")  # Pre-emptively request KYC

    # Bank details always needed for settlement
    required.add("DOC-007")

    return required


def find_missing_docs(
    required: Set[str],
    provided: List[str],
    state: ClaimState
) -> List[MissingDocument]:
    """
    Identify which required documents are missing from the provided list.
    """
    from state import MissingDocument

    doc_meta = {
        "DOC-001": ("Registration Certificate (RC)", 1),
        "DOC-002": ("Driver's License (DL)", 1),
        "DOC-003": ("Insurance Policy Schedule", 1),
        "DOC-004": ("Signed Claim Form (CF-2026)", 1),
        "DOC-005": ("Repair Estimate / Workshop Invoice", 2),
        "DOC-006": ("Final Repair Bill & Payment Receipt", 2),
        "DOC-007": ("Cancelled Cheque / Bank Details", 2),
        "DOC-008": ("First Information Report (FIR)", 3),
        "DOC-009": ("PUC Certificate", 3),
        "DOC-010": ("KYC Document (Aadhaar / PAN)", 3),
        "DOC-011": ("Accident Scene Photographs (min 4)", 4),
        "DOC-012": ("Dashboard / Odometer Photograph", 4),
    }

    missing = []
    provided_set = set(provided)
    for doc_code in sorted(required - provided_set):
        name, tier = doc_meta.get(doc_code, (doc_code, 2))
        missing.append(MissingDocument(
            doc_code=doc_code,
            doc_name=name,
            reason_required=(
                f"Required for {state.claim_type} claims "
                f"per POL-002 Tier {tier}"
            ),
            tier=tier,
        ))
    return missing


def compute_dcs(required: Set[str], provided: List[str]) -> float:
    """
    Compute Document Completeness Score (DCS) per POL-002 Section 6.
    DCS = (docs_provided / docs_required) × 100
    Tier-1 docs have a veto: if any Tier-1 is missing, DCS is capped at 79.
    """
    if not required:
        return 100.0

    provided_set = set(provided)
    tier1_missing = TIER1_DOCS - provided_set

    score = (len(provided_set & required) / len(required)) * 100.0

    # Cap at 79 if any Tier-1 is missing (per POL-002: Tier-1 must be 100%)
    if tier1_missing:
        score = min(score, 79.0)

    return round(score, 1)