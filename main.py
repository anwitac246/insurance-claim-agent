"""
SecureWheel Insurance AI — LangGraph Orchestrator (Agent 1)
-----------------------------------------------------------
This is the central controller for the multi-agent claims pipeline.

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │                   LangGraph StateGraph                  │
  │                                                         │
  │  intake → document_agent → route ──────────────────┐   │
  │                │                                    │   │
  │                ▼                                    ▼   │
  │         [INTERRUPT: HITL]              policy_agent → fraud_agent  │
  │         human_supplement                    │                      │
  │                │                            ▼                      │
  │                └──────────────────→ decision_agent → done          │
  └─────────────────────────────────────────────────────────┘

Key features:
  - MemorySaver checkpointer: state persists across HITL pauses
  - Interrupt pattern: graph pauses when docs are incomplete
  - Idempotency: re-runs with same files skip re-extraction
  - Error budget: escalates to human after 2 LLM failures
  - Observability: full reasoning trace printed at end

Usage:
  # Non-interactive (programmatic)
  from main import run_claim
  result = run_claim(claim_type="OWN_DAMAGE", files=[...])

  # Interactive CLI
  python main.py
"""

from __future__ import annotations

import os
import sys
import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from state import ClaimState, ClaimStatus, RawFile

log = logging.getLogger("orchestrator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)

from langgraph.types import interrupt

def node_intake(state: ClaimState) -> ClaimState:
    """
    Node 1: Claim intake.
    Validates that at least one file was submitted and sets initial status.
    This is a fast, synchronous check — no LLM calls.
    """
    log.info(f"[Intake] claim_id={state.claim_id} | files={len(state.raw_files)}")

    if not state.raw_files:
        log.warning("[Intake] No files submitted — escalating immediately")
        state.status = ClaimStatus.ESCALATED_HUMAN
        state.missing_fields = ["At least one document must be uploaded"]
        return state

    if not state.claim_type:
        state.claim_type = "OWN_DAMAGE"   # sensible default
        log.info("[Intake] claim_type not set — defaulting to OWN_DAMAGE")

    state.status = ClaimStatus.INITIATED
    state.touch()
    return state

def node_document_agent(state: ClaimState) -> ClaimState:
    """
    Node 2: Document Verification Agent.
    Parses files, queries Pinecone, extracts fields, validates, scores DCS.
    """
    from agents.document_agent import DocumentVerificationAgent
    agent = DocumentVerificationAgent()
    return agent.run(state)


def node_hitl_interrupt(state: ClaimState) -> ClaimState:
    """
    Node 3: Human-in-the-Loop interrupt point.

    Uses LangGraph's `interrupt()` to PAUSE the graph here and
    surface a structured message to the caller. When the human
    provides additional files/info, the graph is RESUMED with
    the supplemented state.

    The interrupt payload is a structured dict that the front-end
    or CLI can render for the user.
    """
    missing_docs = [
        {
            "doc_code": m.doc_code,
            "doc_name": m.doc_name,
            "reason": m.reason_required,
            "tier": m.tier,
        }
        for m in state.missing_documents
    ]

    hard_errors = [
        {
            "rule": e.rule,
            "field": e.field,
            "message": e.message,
        }
        for e in state.validation_errors
        if e.severity == "HARD"
    ]

    interrupt_payload = {
        "claim_id": state.claim_id,
        "message": (
            "Your claim submission is INCOMPLETE. "
            "Please provide the missing documents listed below "
            "and resubmit to continue processing."
        ),
        "missing_documents": missing_docs,
        "validation_errors": hard_errors,
        "document_completeness_score": (
            state.document_agent_output.document_completeness_score
            if state.document_agent_output else 0.0
        ),
        "instructions": (
            "Upload the missing files and call resume_claim(claim_id, thread_id, files=[...]) "
            "or use the CLI to provide additional documents."
        ),
    }

    log.info(
        f"[HITL] Interrupting graph — claim_id={state.claim_id} | "
        f"missing={[m['doc_code'] for m in missing_docs]}"
    )

    human_input = interrupt(interrupt_payload)

    # When resumed, human_input contains what the human provided.
    # We store it in state for the document agent's next run.
    if isinstance(human_input, dict):
        state.human_supplement.update(human_input)
        # If new files were provided, append them
        new_files = human_input.get("new_files", [])
        for f in new_files:
            if isinstance(f, dict):
                state.raw_files.append(RawFile(**f))

    state.touch()
    return state


# ─────────────────────────────────────────────────────────────
# NODE: POLICY AGENT (stub — to be implemented in Phase 2)
# ─────────────────────────────────────────────────────────────
def node_policy_agent(state: ClaimState) -> ClaimState:
    """
    Node 4: Policy & Coverage Eligibility Agent (Phase 2 stub).
    Checks exclusions, coverage type, and add-ons against the claim.
    """
    from state import PolicyAgentOutput, PolicyCheckResult, AgentTrace
    import time

    log.info(f"[PolicyAgent] Running — claim_id={state.claim_id}")
    t = time.monotonic()

    # Stub: basic policy validity check using extracted data
    checks = []
    docs = state.document_agent_output.extracted if state.document_agent_output else None

    if docs and docs.policy_schedule and docs.claim_form:
        ps = docs.policy_schedule
        cf = docs.claim_form

        # Check 1: Policy not expired
        expired = (
            ps.policy_end_date and cf.accident_date
            and ps.policy_end_date < cf.accident_date
        )
        checks.append(PolicyCheckResult(
            check_id="RULE-M-002",
            check_name="Policy Validity at Date of Accident",
            result="FAIL" if expired else "PASS",
            details=(
                f"Policy end: {ps.policy_end_date}, "
                f"Accident: {cf.accident_date}"
            ),
        ))

        # Check 2: Coverage type vs claim type
        coverage_mismatch = (
            ps.coverage_type == "TP_ONLY"
            and state.claim_type == "OWN_DAMAGE"
        )
        checks.append(PolicyCheckResult(
            check_id="RULE-COV-001",
            check_name="Coverage Type vs Claim Type",
            result="FAIL" if coverage_mismatch else "PASS",
            details=(
                f"Coverage: {ps.coverage_type}, "
                f"Claim type: {state.claim_type}"
            ),
        ))

    eligible = all(c.result == "PASS" for c in checks)
    state.policy_agent_output = PolicyAgentOutput(
        coverage_eligible=eligible,
        policy_checks=checks,
        confidence_score=0.85 if checks else 0.5,
    )
    state.status = ClaimStatus.FRAUD_CHECKING
    elapsed = int((time.monotonic() - t) * 1000)
    state.add_trace(AgentTrace(
        agent_name="PolicyAgent",
        execution_time_ms=elapsed,
        status="SUCCESS",
        confidence=0.85,
    ))
    return state


# ─────────────────────────────────────────────────────────────
# NODE: FRAUD AGENT (stub — to be implemented in Phase 2)
# ─────────────────────────────────────────────────────────────
def node_fraud_agent(state: ClaimState) -> ClaimState:
    """
    Node 5: Fraud Detection Agent (Phase 2 stub).
    Computes FRS from red flag indicators per POL-004.
    """
    from state import FraudAgentOutput, AgentTrace
    import time

    log.info(f"[FraudAgent] Running — claim_id={state.claim_id}")
    t = time.monotonic()

    frs = 0.0
    triggered = []

    docs = state.document_agent_output.extracted if state.document_agent_output else None

    # RF-B-001: Photo manipulation
    if docs and docs.photos and docs.photos.ai_manipulation_score > 0.7:
        frs += 0.55
        triggered.append({
            "flag_id": "RF-B-001",
            "description": "AI detects image manipulation in submitted photos",
            "weight": 0.55,
            "evidence": f"manipulation_score={docs.photos.ai_manipulation_score:.2f}",
        })

    # RF-B-002: EXIF metadata missing
    if docs and docs.photos and docs.photos.image_count > 0:
        if docs.photos.exif_date_consistent is None:
            frs += 0.30
            triggered.append({
                "flag_id": "RF-B-002",
                "description": "EXIF metadata missing from submitted photos",
                "weight": 0.30,
                "evidence": "exif_date_consistent=null",
            })

    frs = min(frs, 1.0)
    risk_level = (
        "CRITICAL" if frs > 0.75
        else "HIGH" if frs > 0.55
        else "MEDIUM" if frs > 0.30
        else "LOW"
    )

    state.fraud_agent_output = FraudAgentOutput(
        fraud_risk_score=round(frs, 3),
        risk_level=risk_level,
        triggered_flags=triggered,
        fraud_type="NONE" if frs < 0.31 else "SOFT" if frs < 0.56 else "HARD",
        recommendation=(
            "PROCEED" if frs <= 0.30
            else "HOLD" if frs <= 0.75
            else "REJECT_SIU"
        ),
        siu_alert_generated=frs > 0.75,
        agent_confidence=0.80,
        reasoning_trace=f"FRS={frs:.3f} | Flags={len(triggered)} | Level={risk_level}",
    )

    state.status = ClaimStatus.DECIDING
    elapsed = int((time.monotonic() - t) * 1000)
    state.add_trace(AgentTrace(
        agent_name="FraudAgent",
        execution_time_ms=elapsed,
        status="SUCCESS",
        confidence=0.80,
    ))
    return state

def node_decision_agent(state: ClaimState) -> ClaimState:
    """
    Node 6: Decision Agent (Phase 2 stub).
    Computes final payout and assigns terminal state.
    """
    from state import DecisionAgentOutput, PayoutBreakdown, SettlementMode, AgentTrace
    import time

    log.info(f"[DecisionAgent] Running — claim_id={state.claim_id}")
    t = time.monotonic()

    frs = state.fraud_agent_output.fraud_risk_score if state.fraud_agent_output else 0.0
    policy_ok = (
        state.policy_agent_output.coverage_eligible
        if state.policy_agent_output else True
    )

    # Hard rejections
    if frs > 0.75:
        state_code, state_label = "D-006", "REJECTED_FRAUD"
        state.status = ClaimStatus.REJECTED
    elif not policy_ok:
        state_code, state_label = "D-008", "REJECTED_COVERAGE_MISMATCH"
        state.status = ClaimStatus.REJECTED
    else:
        # Compute basic payout (stub — full depreciation logic in Phase 2)
        docs = state.document_agent_output.extracted if state.document_agent_output else None
        gross = 0.0
        if docs and docs.repair_estimate:
            gross = docs.repair_estimate.grand_total_estimate or 0.0

        idv = 0.0
        if docs and docs.policy_schedule:
            idv = docs.policy_schedule.idv or 0.0

        # Cap at IDV (RULE-M-004)
        approved = min(gross, idv) if idv > 0 else gross
        # Compulsory deductible stub (₹1,000 for private car)
        deductible = 1000.0
        final_amount = max(0.0, approved - deductible)

        payout = PayoutBreakdown(
            gross_repair_cost=gross,
            deductible_compulsory=deductible,
            idv_cap_applied=(gross > idv > 0),
            final_approved_amount=final_amount,
            settlement_mode=(
                SettlementMode.CASHLESS
                if (docs and docs.repair_estimate and docs.repair_estimate.is_empaneled)
                else SettlementMode.REIMBURSEMENT
            ),
        )

        if frs > 0.30:
            state_code, state_label = "D-002", "APPROVED_PARTIAL"
            state.status = ClaimStatus.APPROVED_PARTIAL
        else:
            state_code, state_label = "D-001", "APPROVED"
            state.status = ClaimStatus.APPROVED

        # Confidence = inverse of FRS, modulated by DCS
        dcs = (
            state.document_agent_output.document_completeness_score
            if state.document_agent_output else 100.0
        )
        acs = round((1.0 - frs) * 0.6 + (dcs / 100.0) * 0.4, 3)

        state.decision_agent_output = DecisionAgentOutput(
            state_code=state_code,
            state_label=state_label,
            agent_confidence_score=acs,
            human_review_required=acs < 0.70 or gross > 500000,
            ncb_reset=(state_code in {"D-001", "D-002"}),
            siu_referral=frs > 0.75,
            settlement_sla_days=7 if payout.settlement_mode == SettlementMode.CASHLESS else 15,
            payout=payout,
            decision_narrative=_generate_narrative(state, state_label, payout),
        )

    elapsed = int((time.monotonic() - t) * 1000)
    state.add_trace(AgentTrace(
        agent_name="DecisionAgent",
        execution_time_ms=elapsed,
        status="SUCCESS",
        confidence=state.decision_agent_output.agent_confidence_score if state.decision_agent_output else 0.0,
    ))
    return state


def _generate_narrative(state: ClaimState, label: str, payout: "PayoutBreakdown") -> str:
    """Generate a human-readable decision narrative (per POL-006 Section 5.2)."""
    docs = state.document_agent_output.extracted if state.document_agent_output else None
    name = state.claimant_name or "Claimant"
    reg = state.vehicle_registration or "N/A"
    frs = state.fraud_agent_output.fraud_risk_score if state.fraud_agent_output else 0.0

    if label == "APPROVED":
        return (
            f"Claim {state.claim_id} has been APPROVED for "
            f"₹{payout.final_approved_amount:,.0f}. "
            f"Claimant {name} (vehicle {reg}) submitted all required documents. "
            f"Fraud risk score is LOW ({frs:.2f}). "
            f"Gross repair cost ₹{payout.gross_repair_cost:,.0f} minus "
            f"compulsory deductible ₹{payout.deductible_compulsory:,.0f}. "
            f"Settlement via {payout.settlement_mode.value} within "
            f"{state.decision_agent_output.settlement_sla_days} business days."
        )
    elif label == "APPROVED_PARTIAL":
        return (
            f"Claim {state.claim_id} has been APPROVED (PARTIAL) for "
            f"₹{payout.final_approved_amount:,.0f}. "
            f"Fraud risk score MEDIUM ({frs:.2f}) — enhanced scrutiny applied. "
            f"Payout reduced; NCB will be reset at next renewal."
        )
    else:
        return (
            f"Claim {state.claim_id} has been {label}. "
            f"Fraud risk score: {frs:.2f}. "
            f"Please contact SecureWheel for further assistance."
        )


def route_after_intake(state: ClaimState) -> str:
    if state.status == ClaimStatus.ESCALATED_HUMAN:
        return "done"
    return "document_agent"


def route_after_docs(state: ClaimState) -> str:
    """Route after Document Agent completes."""
    if state.error_budget_exhausted:
        return "done"   # Error budget gone → terminal escalation
    if state.status == ClaimStatus.DOCUMENTS_COMPLETE:
        return "policy_agent"
    # INCOMPLETE or INVALID → pause for HITL
    return "hitl_interrupt"


def route_after_hitl(state: ClaimState) -> str:
    """After human provides supplement, re-run document agent."""
    return "document_agent"


def route_after_policy(state: ClaimState) -> str:
    return "fraud_agent"


def route_after_fraud(state: ClaimState) -> str:
    return "decision_agent"

def build_graph() -> tuple[Any, MemorySaver]:
    """
    Construct and compile the LangGraph StateGraph.

    Returns (compiled_graph, checkpointer) so callers can
    use the checkpointer for HITL resume operations.
    """
    checkpointer = MemorySaver()

    builder = StateGraph(ClaimState)

    # Register nodes
    builder.add_node("intake",          node_intake)
    builder.add_node("document_agent",  node_document_agent)
    builder.add_node("hitl_interrupt",  node_hitl_interrupt)
    builder.add_node("policy_agent",    node_policy_agent)
    builder.add_node("fraud_agent",     node_fraud_agent)
    builder.add_node("decision_agent",  node_decision_agent)

    # Entry point
    builder.set_entry_point("intake")

    # Edges
    builder.add_conditional_edges("intake", route_after_intake, {
        "document_agent": "document_agent",
        "done": END,
    })
    builder.add_conditional_edges("document_agent", route_after_docs, {
        "policy_agent":    "policy_agent",
        "hitl_interrupt":  "hitl_interrupt",
        "done":            END,
    })
    builder.add_conditional_edges("hitl_interrupt", route_after_hitl, {
        "document_agent": "document_agent",
    })
    builder.add_conditional_edges("policy_agent", route_after_policy, {
        "fraud_agent": "fraud_agent",
    })
    builder.add_conditional_edges("fraud_agent", route_after_fraud, {
        "decision_agent": "decision_agent",
    })
    builder.add_edge("decision_agent", END)

    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_interrupt"],  # pause BEFORE the HITL node
    )

    log.info("[Orchestrator] Graph compiled successfully")
    return graph, checkpointer


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────
def run_claim(
    claim_type: str,
    files: list[dict],
    claimant_name: str = "",
    policy_number: str = "",
    vehicle_registration: str = "",
    claim_id: str | None = None,
) -> dict:
    """
    Convenience wrapper to start a new claim.

    Args:
        claim_type: "OWN_DAMAGE" | "THIRD_PARTY" | "THEFT" | "FIRE"
        files: list of dicts with keys: filename, file_path, doc_type_hint, size_bytes
        claimant_name: Full name of policyholder
        policy_number: Policy number string
        vehicle_registration: e.g. "MH02AB1234"
        claim_id: Optional; auto-generated if not provided

    Returns:
        dict with keys: claim_id, thread_id, status, output, interrupted
    """
    graph, checkpointer = build_graph()

    initial_state = ClaimState(
        claim_type=claim_type,
        claimant_name=claimant_name,
        policy_number=policy_number,
        vehicle_registration=vehicle_registration,
        raw_files=[RawFile(**f) for f in files],
    )
    if claim_id:
        initial_state.claim_id = claim_id

    thread_config = {"configurable": {"thread_id": initial_state.thread_id}}

    log.info(
        f"[Orchestrator] Starting claim {initial_state.claim_id} "
        f"| thread={initial_state.thread_id}"
    )

    result_state = None
    interrupted = False

    try:
        # Stream events for observability
        for event in graph.stream(
            initial_state,
            config=thread_config,
            stream_mode="values",
        ):
            result_state = event

    except Exception as exc:
        # LangGraph raises an interrupt signal as an exception in some versions
        if "interrupt" in str(exc).lower() or "GraphInterrupt" in type(exc).__name__:
            interrupted = True
            # Retrieve the persisted state from the checkpointer
            snapshot = graph.get_state(thread_config)
            result_state = snapshot.values if snapshot else initial_state
        else:
            log.error(f"[Orchestrator] Unexpected error: {exc}")
            raise

    return _format_result(result_state, initial_state.thread_id, interrupted)


def resume_claim(
    thread_id: str,
    human_input: dict,
    new_files: list[dict] | None = None,
) -> dict:
    """
    Resume a paused (HITL interrupted) claim with human supplement.

    Args:
        thread_id: The thread_id from the original run_claim() result
        human_input: Dict with any supplementary information
        new_files: Optional list of new file dicts to append

    Returns:
        Same dict format as run_claim()
    """
    graph, _ = build_graph()
    thread_config = {"configurable": {"thread_id": thread_id}}

    if new_files:
        human_input["new_files"] = new_files

    log.info(f"[Orchestrator] Resuming claim | thread={thread_id}")

    result_state = None
    interrupted = False

    try:
        for event in graph.stream(
            # Passing the human response to the interrupt
            {"human_supplement": human_input},
            config=thread_config,
            stream_mode="values",
        ):
            result_state = event
    except Exception as exc:
        if "interrupt" in str(exc).lower() or "GraphInterrupt" in type(exc).__name__:
            interrupted = True
            snapshot = graph.get_state(thread_config)
            result_state = snapshot.values if snapshot else {}
        else:
            log.error(f"[Orchestrator] Resume error: {exc}")
            raise

    return _format_result(result_state, thread_id, interrupted)


def _format_result(state: ClaimState | dict | None, thread_id: str, interrupted: bool) -> dict:
    """Format the final state into a clean API response dict."""
    if state is None:
        return {"error": "No state returned from graph", "thread_id": thread_id}

    if isinstance(state, dict):
        return {
            "claim_id": state.get("claim_id", "UNKNOWN"),
            "thread_id": thread_id,
            "status": state.get("status", "UNKNOWN"),
            "interrupted": interrupted,
            "output": state,
        }

    doc_output = state.document_agent_output
    decision_output = state.decision_agent_output

    return {
        "claim_id": state.claim_id,
        "thread_id": state.thread_id,
        "status": state.status.value,
        "interrupted": interrupted,
        "interrupted_reason": (
            {
                "missing_documents": [
                    {"doc_code": m.doc_code, "doc_name": m.doc_name}
                    for m in state.missing_documents
                ],
                "dcs": doc_output.document_completeness_score if doc_output else 0,
            }
            if interrupted else None
        ),
        "document_completeness_score": (
            doc_output.document_completeness_score if doc_output else None
        ),
        "document_agent_confidence": (
            doc_output.confidence_score if doc_output else None
        ),
        "fraud_risk_score": (
            state.fraud_agent_output.fraud_risk_score
            if state.fraud_agent_output else None
        ),
        "decision": (
            {
                "state_code": decision_output.state_code,
                "state_label": decision_output.state_label,
                "final_approved_amount": decision_output.payout.final_approved_amount,
                "settlement_mode": decision_output.payout.settlement_mode.value,
                "sla_days": decision_output.settlement_sla_days,
                "human_review_required": decision_output.human_review_required,
                "narrative": decision_output.decision_narrative,
            }
            if decision_output else None
        ),
        "agent_traces": [
            {
                "agent": t.agent_name,
                "status": t.status,
                "confidence": t.confidence,
                "elapsed_ms": t.execution_time_ms,
            }
            for t in state.agent_traces
        ],
        "error_budget_exhausted": state.error_budget_exhausted,
    }


# ─────────────────────────────────────────────────────────────
# INTERACTIVE CLI
# ─────────────────────────────────────────────────────────────
def _cli() -> None:
    """
    Interactive command-line interface for testing the pipeline.
    Demonstrates the HITL interrupt/resume loop.
    """
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.json import JSON

    console = Console()

    console.print(Panel.fit(
        "[bold cyan]SecureWheel Insurance AI[/bold cyan]\n"
        "[dim]Multi-Agent Claims Processing Pipeline[/dim]",
        border_style="cyan",
    ))

    # ── Gather claim info ─────────────────────────────────────
    console.print("\n[bold]Enter claim details:[/bold]")
    claim_type = console.input(
        "[yellow]Claim type (OWN_DAMAGE/THIRD_PARTY/THEFT/FIRE) [OWN_DAMAGE]: [/yellow]"
    ).strip().upper() or "OWN_DAMAGE"

    claimant_name = console.input("[yellow]Claimant name: [/yellow]").strip()
    policy_number = console.input("[yellow]Policy number: [/yellow]").strip()
    vehicle_reg   = console.input("[yellow]Vehicle registration: [/yellow]").strip()

    # ── Gather files ──────────────────────────────────────────
    console.print("\n[bold]Upload documents[/bold] (enter file paths; blank to finish):")
    files = []
    while True:
        filepath = console.input("[green]  File path (or press Enter to continue): [/green]").strip()
        if not filepath:
            break
        p = Path(filepath)
        if not p.exists():
            console.print(f"  [red]File not found: {filepath}[/red]")
            continue
        hint = console.input(f"  [dim]  Document type hint for {p.name} (RC/DL/Policy/Claim/FIR/etc.): [/dim]").strip()
        files.append({
            "filename": p.name,
            "file_path": str(p),
            "doc_type_hint": hint,
            "size_bytes": p.stat().st_size,
        })
        console.print(f"  [green]✓ Added: {p.name}[/green]")

    if not files:
        console.print("[yellow]No files provided — using mock data for demo[/yellow]")
        files = [{
            "filename": "demo_rc.pdf",
            "file_path": "/tmp/demo_rc.pdf",
            "doc_type_hint": "RC",
            "size_bytes": 0,
        }]
        # Create dummy file for demo
        Path("/tmp/demo_rc.pdf").touch()

    # ── Run the claim ─────────────────────────────────────────
    console.print("\n[bold cyan]Processing claim...[/bold cyan]")

    result = run_claim(
        claim_type=claim_type,
        files=files,
        claimant_name=claimant_name,
        policy_number=policy_number,
        vehicle_registration=vehicle_reg,
    )

    _print_result(console, result)

    # ── HITL Resume Loop ──────────────────────────────────────
    while result.get("interrupted"):
        console.print(Panel(
            "[bold yellow]⚠ Claim processing paused — additional documents required[/bold yellow]\n\n"
            + "\n".join(
                f"  • [cyan]{m['doc_code']}[/cyan] — {m['doc_name']}"
                for m in (result.get("interrupted_reason") or {}).get("missing_documents", [])
            ),
            border_style="yellow",
        ))

        console.print("\n[bold]Provide additional documents (or press Enter to skip):[/bold]")
        new_files = []
        while True:
            filepath = console.input("[green]  New file path (or Enter to submit): [/green]").strip()
            if not filepath:
                break
            p = Path(filepath)
            if p.exists():
                hint = console.input(f"  [dim]  Doc type hint for {p.name}: [/dim]").strip()
                new_files.append({
                    "filename": p.name,
                    "file_path": str(p),
                    "doc_type_hint": hint,
                    "size_bytes": p.stat().st_size,
                })
                console.print(f"  [green]✓ Added: {p.name}[/green]")

        console.print("\n[bold cyan]Resuming claim processing...[/bold cyan]")
        result = resume_claim(
            thread_id=result["thread_id"],
            human_input={"resumed": True},
            new_files=new_files or None,
        )
        _print_result(console, result)

    console.print("\n[bold green]✓ Claim processing complete[/bold green]")


def _print_result(console: Any, result: dict) -> None:
    """Pretty-print the claim result to the console."""
    from rich.table import Table
    from rich.panel import Panel

    status_color = {
        "APPROVED": "green",
        "APPROVED_PARTIAL": "yellow",
        "REJECTED": "red",
        "ESCALATED_HUMAN": "magenta",
        "DOCUMENTS_PENDING": "yellow",
        "DOCUMENTS_COMPLETE": "cyan",
    }.get(result.get("status", ""), "white")

    console.print(Panel(
        f"[bold]Claim ID:[/bold]  {result['claim_id']}\n"
        f"[bold]Status:[/bold]    [{status_color}]{result['status']}[/{status_color}]\n"
        f"[bold]DCS:[/bold]       {result.get('document_completeness_score', 'N/A')}%\n"
        f"[bold]Doc Conf:[/bold]  {result.get('document_agent_confidence', 'N/A')}\n"
        f"[bold]FRS:[/bold]       {result.get('fraud_risk_score', 'N/A')}\n"
        f"[bold]Interrupted:[/bold] {result['interrupted']}",
        title="[bold cyan]Claim Status[/bold cyan]",
        border_style="cyan",
    ))

    decision = result.get("decision")
    if decision:
        console.print(Panel(
            f"[bold]Decision:[/bold]       {decision['state_label']}\n"
            f"[bold]Amount:[/bold]         ₹{decision['final_approved_amount']:,.0f}\n"
            f"[bold]Mode:[/bold]           {decision['settlement_mode']}\n"
            f"[bold]SLA:[/bold]            {decision['sla_days']} business days\n"
            f"[bold]Human Review:[/bold]   {decision['human_review_required']}\n\n"
            f"[italic]{decision['narrative']}[/italic]",
            title="[bold green]Decision[/bold green]",
            border_style="green",
        ))

    # Agent trace table
    traces = result.get("agent_traces", [])
    if traces:
        table = Table(title="Agent Execution Traces", style="dim")
        table.add_column("Agent", style="cyan")
        table.add_column("Status")
        table.add_column("Confidence", justify="right")
        table.add_column("Elapsed (ms)", justify="right")
        for t in traces:
            color = "green" if t["status"] == "SUCCESS" else "yellow"
            table.add_row(
                t["agent"],
                f"[{color}]{t['status']}[/{color}]",
                f"{t['confidence']:.2f}",
                str(t["elapsed_ms"]),
            )
        console.print(table)

if __name__ == "__main__":
    _cli()