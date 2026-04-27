"""
agents/policy_agent.py
======================
SecureWheel Insurance AI — Policy Validation Agent (Agent 3)
------------------------------------------------------------
Receives structured ExtractedDocuments from the Document Agent,
queries Pinecone for relevant policy clauses, and determines
coverage eligibility, liability cap, and deductible.

Stack:
  - LLM: langchain-groq (llama-3.3-70b-versatile)
  - Vector DB: Pinecone (index: insurance-policies)
  - Output: Pydantic PolicyValidationResult
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any

from groq import Groq
from pinecone import Pinecone
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from state import (
    ClaimState, ClaimStatus, AgentTrace,
    PolicyAgentOutput, PolicyCheckResult,
    ExtractedDocuments,
)

load_dotenv()

log = logging.getLogger("policy_agent")

GROQ_MODEL       = "llama-3.3-70b-versatile"
PINECONE_INDEX   = "insurance-policies"
PINECONE_TOP_K   = 10

# Namespaces to query for policy validation
POLICY_NAMESPACES = ["policy_rules", "settlement_rules", "vehicle_rules"]

# Absolute exclusion causes from POL-001 Section 4.1
ABSOLUTE_EXCLUSIONS = {
    "drunk_driving", "dui", "alcohol", "narcotics", "racing",
    "intentional", "willful", "nuclear", "biological", "chemical",
}


# ─────────────────────────────────────────────────────────────
# OUTPUT SCHEMA
# ─────────────────────────────────────────────────────────────

class PolicyValidationResult(BaseModel):
    is_covered: bool
    coverage_reasoning: str
    deductible_applied: float
    max_reimbursement: float
    policy_clauses_cited: list[str] = Field(default_factory=list)
    exclusions_triggered: list[str] = Field(default_factory=list)
    add_ons_applied: list[str] = Field(default_factory=list)
    settlement_mode_recommended: str = "REIMBURSEMENT"
    total_loss_flag: bool = False
    confidence: float = 0.0


# ─────────────────────────────────────────────────────────────
# PINECONE RETRIEVAL
# ─────────────────────────────────────────────────────────────

def retrieve_policy_clauses(
    query: str,
    pc_index: Any,
    embed_fn: Any,
    namespaces: list[str] = POLICY_NAMESPACES,
    top_k: int = PINECONE_TOP_K,
) -> str:
    """
    Query Pinecone across multiple policy namespaces and return
    concatenated clause text ranked by relevance.
    """
    all_chunks: list[tuple[float, str, str]] = []  # (score, section, text)

    vector = embed_fn(query)

    for ns in namespaces:
        try:
            result = pc_index.query(
                vector=vector,
                top_k=top_k,
                namespace=ns,
                include_metadata=True,
            )
            for match in result.matches:
                meta = match.metadata or {}
                text = meta.get("text", "")
                section = meta.get("section_title", ns)
                all_chunks.append((match.score, section, text))
        except Exception as exc:
            log.warning(f"[PolicyAgent] Pinecone query failed for ns={ns}: {exc}")

    all_chunks.sort(key=lambda x: x[0], reverse=True)
    top_chunks = all_chunks[:top_k]

    if not top_chunks:
        return "No relevant policy clauses retrieved."

    parts = []
    for score, section, text in top_chunks:
        if text:
            parts.append(f"[{section} | score={score:.3f}]\n{text}")

    return "\n\n---\n\n".join(parts)


# ─────────────────────────────────────────────────────────────
# COMPULSORY DEDUCTIBLE LOOKUP (POL-003 Section 4.1)
# ─────────────────────────────────────────────────────────────

def _compulsory_deductible(docs: ExtractedDocuments) -> float:
    rc = docs.rc
    vehicle_class = (rc.vehicle_class or "").upper() if rc else ""

    if "TWO" in vehicle_class or "MCWG" in vehicle_class or "MC" in vehicle_class:
        return 200.0
    if "1500" in vehicle_class:
        return 2000.0
    return 1000.0  # default: private car ≤ 1500cc


# ─────────────────────────────────────────────────────────────
# ABSOLUTE EXCLUSION PRE-CHECK
# ─────────────────────────────────────────────────────────────

def _check_absolute_exclusions(docs: ExtractedDocuments) -> list[str]:
    triggered = []
    cf = docs.claim_form
    if not cf:
        return triggered

    cause = (cf.accident_cause or "").lower()
    for excl in ABSOLUTE_EXCLUSIONS:
        if excl in cause:
            triggered.append(f"E-001/E-004: Absolute exclusion triggered — cause contains '{excl}'")

    return triggered


# ─────────────────────────────────────────────────────────────
# ADD-ON DETECTION
# ─────────────────────────────────────────────────────────────

def _detect_active_addons(docs: ExtractedDocuments) -> list[str]:
    ps = docs.policy_schedule
    if not ps:
        return []
    return list(ps.add_ons or [])


# ─────────────────────────────────────────────────────────────
# LLM VALIDATION CALL
# ─────────────────────────────────────────────────────────────

def _run_llm_validation(
    docs: ExtractedDocuments,
    policy_context: str,
    image_summary: str,
    groq_client: Groq,
    claim_type: str,
) -> PolicyValidationResult:
    ps  = docs.policy_schedule
    cf  = docs.claim_form
    re_ = docs.repair_estimate

    compulsory_ded = _compulsory_deductible(docs)
    voluntary_ded  = (ps.voluntary_deductible or 0.0) if ps else 0.0
    total_deductible = compulsory_ded + voluntary_ded

    gross_estimate = (re_.grand_total_estimate or 0.0) if re_ else 0.0
    idv            = (ps.idv or 0.0) if ps else 0.0
    coverage_type  = (ps.coverage_type or "UNKNOWN") if ps else "UNKNOWN"

    add_ons = _detect_active_addons(docs)
    exclusions = _check_absolute_exclusions(docs)

    system_prompt = f"""You are a motor insurance policy validation AI for SecureWheel Insurance.
Your task is to determine if a claim is covered based on the policy document clauses provided.

POLICY CONTEXT (retrieved from knowledge base):
{policy_context[:4000]}

RULES:
- Output ONLY valid JSON. No explanation, no markdown.
- Be deterministic — same inputs must produce same output (temperature=0).
- Cite specific section IDs or clause titles, not generic statements.
- If absolute exclusion applies, is_covered=false regardless of other factors.
- Cap max_reimbursement at IDV. Never exceed IDV.
- Apply Zero Depreciation (AO-001) only if present in add_ons.
- For total loss: flag total_loss_flag=true if gross estimate > 75% of IDV.
- confidence should reflect how clearly the policy clauses address this claim (0.0–1.0).

JSON schema:
{{
  "is_covered": true,
  "coverage_reasoning": "string (2-4 sentences citing specific clauses)",
  "deductible_applied": 0.0,
  "max_reimbursement": 0.0,
  "policy_clauses_cited": ["Section X: ...", "RULE-M-XXX"],
  "exclusions_triggered": [],
  "add_ons_applied": [],
  "settlement_mode_recommended": "CASHLESS | REIMBURSEMENT | TOTAL_LOSS",
  "total_loss_flag": false,
  "confidence": 0.0
}}"""

    user_prompt = f"""CLAIM DETAILS:
- Claim Type: {claim_type}
- Coverage Type on Policy: {coverage_type}
- Accident Cause: {cf.accident_cause if cf else 'Unknown'}
- Accident Date: {cf.accident_date if cf else 'Unknown'}
- Policy Valid Until: {ps.policy_end_date if ps else 'Unknown'}
- IDV: ₹{idv:,.0f}
- Gross Repair Estimate: ₹{gross_estimate:,.0f}
- Garage Empaneled: {re_.is_empaneled if re_ else False}
- Workshop Code: {re_.workshop_code if re_ else 'N/A'}
- Compulsory Deductible: ₹{compulsory_ded:,.0f}
- Voluntary Deductible: ₹{voluntary_ded:,.0f}
- Active Add-Ons: {add_ons}
- Absolute Exclusions Pre-Detected: {exclusions}
- Third Party Involved: {cf.third_party_involved if cf else False}
- FIR Filed: {cf.fir_reported if cf else False}

DAMAGE PARTS:
{[p for p in (re_.listed_damaged_parts or [])] if re_ else 'None provided'}

IMAGE SUMMARY (AI analysis of uploaded photos):
{image_summary or 'No image summary available.'}

Validate coverage and return JSON only."""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0,
        max_tokens=1200,
        response_format={"type": "json_object"},
    )

    import json
    raw = response.choices[0].message.content
    data = json.loads(raw)
    return PolicyValidationResult(**data)


# ─────────────────────────────────────────────────────────────
# POLICY VALIDATION AGENT
# ─────────────────────────────────────────────────────────────

class PolicyValidationAgent:
    """
    Agent 3: Policy Validation Agent.

    Usage:
        agent = PolicyValidationAgent()
        updated_state = agent.run(state)
    """

    def __init__(self) -> None:
        self.groq     = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.pc_index = Pinecone(
            api_key=os.getenv("PINECONE_API_KEY")
        ).Index(PINECONE_INDEX)
        self._embed_fn = None

    def _get_embed_fn(self):
        if self._embed_fn is None:
            from seed_pinecone import embed_query
            self._embed_fn = embed_query
        return self._embed_fn

    def run(self, state: ClaimState) -> ClaimState:
        t_start = time.monotonic()
        log.info(f"[PolicyAgent] Starting — claim_id={state.claim_id}")

        doc_output = state.document_agent_output
        if not doc_output:
            log.error("[PolicyAgent] No document agent output found — skipping")
            state.status = ClaimStatus.ESCALATED_HUMAN
            return state

        docs = doc_output.extracted
        embed_fn = self._get_embed_fn()

        # Build a focused RAG query from claim context
        cf = docs.claim_form
        ps = docs.policy_schedule
        rag_query = (
            f"{state.claim_type} insurance claim. "
            f"Accident cause: {cf.accident_cause if cf else 'unknown'}. "
            f"Coverage type: {(ps.coverage_type or '') if ps else ''}. "
            f"Third party involved: {cf.third_party_involved if cf else False}. "
            f"What exclusions apply? What is covered? What is the deductible?"
        )

        log.info("[PolicyAgent] Querying Pinecone for policy clauses...")
        policy_context = retrieve_policy_clauses(rag_query, self.pc_index, embed_fn)

        image_summary = doc_output.extracted.photos.damage_type_detected \
            if doc_output.extracted.photos else ""

        log.info("[PolicyAgent] Running LLM validation...")
        try:
            result = _run_llm_validation(
                docs=docs,
                policy_context=policy_context,
                image_summary=image_summary,
                groq_client=self.groq,
                claim_type=state.claim_type,
            )
        except Exception as exc:
            log.error(f"[PolicyAgent] LLM call failed: {exc}")
            result = PolicyValidationResult(
                is_covered=False,
                coverage_reasoning=f"Validation failed due to system error: {exc}",
                deductible_applied=0.0,
                max_reimbursement=0.0,
                confidence=0.0,
            )

        checks = self._build_policy_checks(result, docs, state)

        state.policy_agent_output = PolicyAgentOutput(
            coverage_eligible=result.is_covered,
            active_exclusions=result.exclusions_triggered,
            policy_checks=checks,
            confidence_score=result.confidence,
        )

        # Attach full result to state for Decision Agent
        state.policy_validation_result = result  # type: ignore[attr-defined]

        state.status = (
            ClaimStatus.FRAUD_CHECKING if result.is_covered
            else ClaimStatus.REJECTED
        )

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        state.add_trace(AgentTrace(
            agent_name="PolicyAgent",
            execution_time_ms=elapsed_ms,
            status="SUCCESS" if result.is_covered else "PARTIAL",
            confidence=result.confidence,
            errors=result.exclusions_triggered,
        ))

        log.info(
            f"[PolicyAgent] Done — covered={result.is_covered}, "
            f"max_reimbursement=₹{result.max_reimbursement:,.0f}, "
            f"confidence={result.confidence:.2f}, elapsed={elapsed_ms}ms"
        )
        return state

    def _build_policy_checks(
        self,
        result: PolicyValidationResult,
        docs: ExtractedDocuments,
        state: ClaimState,
    ) -> list[PolicyCheckResult]:
        checks: list[PolicyCheckResult] = []
        ps = docs.policy_schedule
        cf = docs.claim_form

        # Coverage type vs claim type
        coverage_type = (ps.coverage_type or "UNKNOWN") if ps else "UNKNOWN"
        mismatch = coverage_type == "TP_ONLY" and state.claim_type == "OWN_DAMAGE"
        checks.append(PolicyCheckResult(
            check_id="RULE-COV-001",
            check_name="Coverage Type vs Claim Type",
            result="FAIL" if mismatch else "PASS",
            details=f"Coverage={coverage_type}, ClaimType={state.claim_type}",
        ))

        # Policy validity
        expired = (
            ps and cf and
            ps.policy_end_date and cf.accident_date and
            ps.policy_end_date < cf.accident_date
        )
        checks.append(PolicyCheckResult(
            check_id="RULE-M-002",
            check_name="Policy Active at Date of Accident",
            result="FAIL" if expired else "PASS",
            details=f"PolicyEnd={ps.policy_end_date if ps else 'N/A'}, AccidentDate={cf.accident_date if cf else 'N/A'}",
        ))

        # Absolute exclusions
        checks.append(PolicyCheckResult(
            check_id="RULE-EXCL-001",
            check_name="Absolute Exclusion Check (E-001–E-007)",
            result="FAIL" if result.exclusions_triggered else "PASS",
            details="; ".join(result.exclusions_triggered) or "None triggered",
        ))

        # Total loss
        checks.append(PolicyCheckResult(
            check_id="RULE-CTL-001",
            check_name="Constructive Total Loss Check (>75% IDV)",
            result="FLAG" if result.total_loss_flag else "PASS",
            details=f"TotalLoss={result.total_loss_flag}",
        ))

        # LLM coverage decision
        checks.append(PolicyCheckResult(
            check_id="RULE-LLM-001",
            check_name="LLM Coverage Determination",
            result="PASS" if result.is_covered else "FAIL",
            details=result.coverage_reasoning,
        ))

        return checks