"""
state.py
========
SecureWheel Insurance AI — Global Claim State Definition
---------------------------------------------------------
Defines the canonical ClaimState Pydantic model shared across all
LangGraph nodes. Every agent reads from and writes to this state.

Design principles:
  - Immutable history: messages list grows; never overwritten
  - Typed sub-schemas: each agent's output has its own model
  - Status as a strict enum: prevents typos in routing logic
  - Audit-grade: timestamps and confidence scores on every update
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# ─────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────

class ClaimStatus(str, Enum):
    """Terminal and intermediate states for the claim lifecycle."""
    INITIATED           = "INITIATED"           # Claim just received
    DOCUMENTS_PENDING   = "DOCUMENTS_PENDING"   # Awaiting more files from claimant
    DOCUMENTS_COMPLETE  = "DOCUMENTS_COMPLETE"  # Doc agent cleared all docs
    POLICY_CHECKING     = "POLICY_CHECKING"     # Policy agent running
    FRAUD_CHECKING      = "FRAUD_CHECKING"      # Fraud agent running
    DECIDING            = "DECIDING"            # Decision agent running
    APPROVED            = "APPROVED"            # Final: fully approved
    APPROVED_PARTIAL    = "APPROVED_PARTIAL"    # Final: approved with deductions
    REJECTED            = "REJECTED"            # Final: rejected
    ESCALATED_HUMAN     = "ESCALATED_HUMAN"     # Routed to human adjuster
    ERROR               = "ERROR"              # Unrecoverable system error


class DocumentStatus(str, Enum):
    READY      = "READY"        # All required docs present and extracted
    INCOMPLETE = "INCOMPLETE"   # Missing mandatory documents
    INVALID    = "INVALID"      # Documents present but failed validation


class SettlementMode(str, Enum):
    CASHLESS        = "CASHLESS"
    REIMBURSEMENT   = "REIMBURSEMENT"
    TOTAL_LOSS      = "TOTAL_LOSS"
    PENDING         = "PENDING"


# ─────────────────────────────────────────────────────────────
# SUB-SCHEMAS: DOCUMENT AGENT OUTPUT
# ─────────────────────────────────────────────────────────────

class ExtractedRC(BaseModel):
    """Registration Certificate extracted fields (DOC-001)."""
    registration_number: str | None = None
    engine_number: str | None = None
    chassis_number: str | None = None
    owner_name: str | None = None
    vehicle_class: str | None = None
    fuel_type: str | None = None
    rc_expiry_date: str | None = None
    manufacture_year: int | None = None


class ExtractedDL(BaseModel):
    """Driver's License extracted fields (DOC-002)."""
    dl_number: str | None = None
    holder_name: str | None = None
    dob: str | None = None
    vehicle_classes_authorized: list[str] = Field(default_factory=list)
    dl_validity_date: str | None = None
    issue_state: str | None = None


class ExtractedPolicySchedule(BaseModel):
    """Insurance Policy Schedule extracted fields (DOC-003)."""
    policy_number: str | None = None
    policy_start_date: str | None = None
    policy_end_date: str | None = None
    idv: float | None = None
    coverage_type: str | None = None          # "COMPREHENSIVE" | "TP_ONLY" | "OD_ONLY"
    policyholder_name: str | None = None
    vehicle_registration: str | None = None
    premium_paid: float | None = None
    ncb_percentage: float | None = None
    voluntary_deductible: float = 0.0
    add_ons: list[str] = Field(default_factory=list)  # e.g. ["AO-001", "AO-008"]


class ExtractedClaimForm(BaseModel):
    """Claim Form extracted fields (DOC-004)."""
    claim_date: str | None = None
    accident_date: str | None = None
    accident_time: str | None = None
    accident_location: str | None = None
    accident_cause: str | None = None
    estimated_loss: float | None = None
    claimant_signature_present: bool = False
    fir_reported: bool = False
    fir_number: str | None = None
    third_party_involved: bool = False


class ExtractedRepairEstimate(BaseModel):
    """Workshop repair estimate fields (DOC-005)."""
    garage_name: str | None = None
    garage_gst: str | None = None
    workshop_code: str | None = None
    total_parts_cost: float | None = None
    total_labor_cost: float | None = None
    grand_total_estimate: float | None = None
    is_empaneled: bool = False
    listed_damaged_parts: list[dict[str, Any]] = Field(default_factory=list)


class ExtractedFIR(BaseModel):
    """First Information Report fields (DOC-008)."""
    fir_number: str | None = None
    police_station: str | None = None
    fir_date: str | None = None
    fir_time: str | None = None
    fir_jurisdiction_district: str | None = None
    fir_officer_name: str | None = None
    hours_after_accident: float | None = None   # derived: fir_date - accident_date


class ExtractedPhotos(BaseModel):
    """Accident scene photo metadata (DOC-011)."""
    image_count: int = 0
    video_present: bool = False
    exif_date_consistent: bool | None = None
    exif_gps_consistent: bool | None = None
    damage_visible: bool | None = None
    damage_type_detected: str | None = None
    ai_manipulation_score: float = 0.0          # 0 = clean, 1 = manipulated


class ExtractedDocuments(BaseModel):
    """Aggregated output of all document extractions."""
    rc: ExtractedRC | None = None
    dl: ExtractedDL | None = None
    policy_schedule: ExtractedPolicySchedule | None = None
    claim_form: ExtractedClaimForm | None = None
    repair_estimate: ExtractedRepairEstimate | None = None
    fir: ExtractedFIR | None = None
    photos: ExtractedPhotos | None = None
    kyc_verified: bool = False
    puc_valid: bool | None = None


# ─────────────────────────────────────────────────────────────
# SUB-SCHEMAS: VALIDATION & COMPLETENESS
# ─────────────────────────────────────────────────────────────

class ValidationError(BaseModel):
    """A single document validation failure."""
    doc_code: str           # e.g. "DOC-001"
    field: str              # e.g. "engine_number"
    rule: str               # e.g. "RULE-M-003"
    severity: str           # "HARD" (block) | "SOFT" (warn)
    message: str


class MissingDocument(BaseModel):
    """A mandatory document that was not submitted."""
    doc_code: str           # e.g. "DOC-008"
    doc_name: str           # e.g. "First Information Report (FIR)"
    reason_required: str    # why it's needed for this specific claim
    tier: int               # 1–4, from POL-002


class DocumentAgentOutput(BaseModel):
    """Full output contract from Agent 2 (Document Verification Agent)."""
    status: DocumentStatus
    document_completeness_score: float          # 0–100 per POL-002 Section 6
    extracted: ExtractedDocuments
    missing_documents: list[MissingDocument] = Field(default_factory=list)
    validation_errors: list[ValidationError] = Field(default_factory=list)
    required_docs: list[str] = Field(default_factory=list)   # doc codes required
    provided_docs: list[str] = Field(default_factory=list)   # doc codes found
    confidence_score: float = 0.0               # 0–1 SRE metric
    extraction_attempts: int = 1                # for error budget tracking
    processed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    pinecone_policy_context: str = ""           # raw RAG context used


# ─────────────────────────────────────────────────────────────
# SUB-SCHEMAS: FRAUD & POLICY AGENT OUTPUT (stubs for downstream)
# ─────────────────────────────────────────────────────────────

class TriggeredFlag(BaseModel):
    flag_id: str
    description: str
    weight: float
    evidence: str


class FraudAgentOutput(BaseModel):
    fraud_risk_score: float = 0.0
    risk_level: str = "LOW"
    triggered_flags: list[TriggeredFlag] = Field(default_factory=list)
    fraud_type: str = "NONE"
    pinecone_similar_cases: list[str] = Field(default_factory=list)
    hotspot_match: bool = False
    blacklist_match: bool = False
    recommendation: str = "PROCEED"
    siu_alert_generated: bool = False
    agent_confidence: float = 0.0
    reasoning_trace: str = ""


class PolicyCheckResult(BaseModel):
    check_id: str
    check_name: str
    result: str         # "PASS" | "FAIL" | "SKIPPED"
    details: str


class PolicyAgentOutput(BaseModel):
    coverage_eligible: bool = False
    active_exclusions: list[str] = Field(default_factory=list)
    policy_checks: list[PolicyCheckResult] = Field(default_factory=list)
    confidence_score: float = 0.0


# ─────────────────────────────────────────────────────────────
# SUB-SCHEMAS: DECISION AGENT OUTPUT
# ─────────────────────────────────────────────────────────────

class PayoutBreakdown(BaseModel):
    gross_repair_cost: float = 0.0
    depreciation_applied: float = 0.0
    deductible_compulsory: float = 0.0
    deductible_voluntary: float = 0.0
    idv_cap_applied: bool = False
    salvage_value: float = 0.0
    final_approved_amount: float = 0.0
    settlement_mode: SettlementMode = SettlementMode.PENDING


class DecisionAgentOutput(BaseModel):
    state_code: str = ""                # D-001 to D-009
    state_label: str = ""
    agent_confidence_score: float = 0.0
    human_review_required: bool = False
    rejection_reason: str | None = None
    ncb_reset: bool = False
    siu_referral: bool = False
    settlement_sla_days: int = 0
    payout: PayoutBreakdown = Field(default_factory=PayoutBreakdown)
    decision_narrative: str = ""


# ─────────────────────────────────────────────────────────────
# AGENT EXECUTION TRACE (SRE OBSERVABILITY)
# ─────────────────────────────────────────────────────────────

class AgentTrace(BaseModel):
    """Per-agent execution record for the SRE reasoning trace."""
    agent_name: str
    execution_time_ms: int = 0
    status: str = "SUCCESS"     # "SUCCESS" | "PARTIAL" | "FAILED"
    confidence: float = 0.0
    errors: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ─────────────────────────────────────────────────────────────
# RAW FILE INPUT
# ─────────────────────────────────────────────────────────────

class RawFile(BaseModel):
    """A file uploaded by the claimant."""
    filename: str
    file_path: str              # local path after upload
    doc_type_hint: str = ""     # optional user-provided hint (e.g. "RC", "DL")
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    uploaded_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ─────────────────────────────────────────────────────────────
# MASTER CLAIM STATE
# ─────────────────────────────────────────────────────────────

class ClaimState(BaseModel):
    """
    The single source of truth for a claim as it flows through LangGraph.

    LangGraph serializes this at every checkpoint via MemorySaver.
    The `messages` field uses the built-in `add_messages` reducer so that
    LangGraph appends new messages rather than replacing the list.
    """

    # ── Identity ─────────────────────────────────────────────
    claim_id: str = Field(
        default_factory=lambda: f"CLM-{datetime.now().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    )
    thread_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Status ───────────────────────────────────────────────
    status: ClaimStatus = ClaimStatus.INITIATED

    # ── Claimant & Policy Identifiers ────────────────────────
    claimant_name: str = ""
    policy_number: str = ""
    vehicle_registration: str = ""
    claim_type: str = ""        # "OWN_DAMAGE" | "THIRD_PARTY" | "THEFT" | "FIRE"

    # ── Raw Inputs ───────────────────────────────────────────
    raw_files: list[RawFile] = Field(default_factory=list)

    # ── Agent Outputs ────────────────────────────────────────
    document_agent_output: DocumentAgentOutput | None = None
    policy_agent_output: PolicyAgentOutput | None = None
    fraud_agent_output: FraudAgentOutput | None = None
    decision_agent_output: DecisionAgentOutput | None = None

    # ── HITL Interaction ─────────────────────────────────────
    # `messages` is a LangGraph-managed list; add_messages ensures
    # LangGraph appends rather than overwrites during state merges.
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Human-supplied supplementary info during HITL pause
    human_supplement: dict[str, Any] = Field(default_factory=dict)

    # ── Validation & Errors ──────────────────────────────────
    validation_errors: list[ValidationError] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)    # human-readable
    missing_documents: list[MissingDocument] = Field(default_factory=list)

    # ── SRE Observability ────────────────────────────────────
    agent_traces: list[AgentTrace] = Field(default_factory=list)
    extraction_attempt_count: int = 0   # tracks retries for error budget
    error_budget_exhausted: bool = False

    # ── Idempotency ──────────────────────────────────────────
    # SHA-256 hash of raw_files list at intake; re-runs with same
    # files are detected and short-circuited.
    input_hash: str = ""

    class Config:
        # Allow LangGraph to serialize/deserialize with MemorySaver
        arbitrary_types_allowed = True

    def touch(self) -> None:
        """Update the updated_at timestamp. Call after any mutation."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_trace(self, trace: AgentTrace) -> None:
        """Append an agent execution record."""
        self.agent_traces.append(trace)
        self.touch()

    def is_terminal(self) -> bool:
        """True if the claim has reached a final state."""
        return self.status in {
            ClaimStatus.APPROVED,
            ClaimStatus.APPROVED_PARTIAL,
            ClaimStatus.REJECTED,
            ClaimStatus.ESCALATED_HUMAN,
            ClaimStatus.ERROR,
        }