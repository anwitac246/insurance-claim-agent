"""
agents/document_agent.py
========================
SecureWheel Insurance AI — Document Verification Agent (Agent 2)
----------------------------------------------------------------
Refactored to be modular with components in separate files.
"""

from __future__ import annotations

import time
from typing import Any

# Import state models
from state import (
    ClaimState, ClaimStatus, DocumentStatus, DocumentAgentOutput,
    AgentTrace
)

# Import our modular components
from .document_parser import parse_file
from .document_extractor import extract_document
from .document_validator import run_validation_checks
from .document_checker import (
    determine_required_docs,
    find_missing_docs,
    compute_dcs
)

# Import for lazy loading
from pinecone import Pinecone
from groq import Groq
from dotenv import load_dotenv
import os
import hashlib
from pathlib import Path
import logging

load_dotenv()

log = logging.getLogger("document_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
GROQ_MODEL          = "llama-3.3-70b-versatile"
PINECONE_INDEX      = "insurance-policies"
DOC_NAMESPACE       = "document_rules"
POLICY_NAMESPACE    = "policy_rules"
MAX_RETRIES         = 2     # error budget per file
PINECONE_TOP_K      = 8     # RAG chunks to retrieve


class DocumentVerificationAgent:
    """
    Agent 2: Document Verification Agent.

    Usage:
        agent = DocumentVerificationAgent()
        output = agent.run(state)   # state is a ClaimState
    """

    def __init__(self) -> None:
        self.groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.pc_index = Pinecone(
            api_key=os.getenv("PINECONE_API_KEY")
        ).Index(PINECONE_INDEX)
        self._embed_query = None    # lazy-load on first use

    # ──────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ──────────────────────────────────────────────────────────
    def run(self, state: ClaimState) -> ClaimState:
        """
        Main execution entry point called by LangGraph.

        Returns the mutated ClaimState. LangGraph merges the
        returned dict/model back into the global state.
        """
        t_start = time.monotonic()
        log.info(f"[DocumentAgent] Starting — claim_id={state.claim_id}")

        # ── Idempotency check ─────────────────────────────────
        current_hash = self._hash_files(state.raw_files)
        if (
            state.input_hash == current_hash
            and state.document_agent_output is not None
            and state.document_agent_output.status != DocumentStatus.INVALID
        ):
            log.info("[DocumentAgent] Idempotency hit — returning cached result")
            state.add_trace(AgentTrace(
                agent_name="DocumentAgent",
                execution_time_ms=0,
                status="SUCCESS",
                confidence=state.document_agent_output.confidence_score,
            ))
            return state

        state.input_hash = current_hash
        state.extraction_attempt_count += 1

        # ── Step 1: Retrieve policy context from Pinecone ─────
        log.info("[DocumentAgent] Querying Pinecone for document requirements...")
        pinecone_context = self._retrieve_policy_context(state.claim_type)

        # ── Step 2: Determine required documents ─────────────
        required_docs = determine_required_docs(state)
        log.info(f"[DocumentAgent] Required docs: {required_docs}")

        # ── Step 3: Parse & extract each uploaded file ────────
        all_extracted: dict[str, Any] = {}
        provided_docs: list[str] = []
        extraction_confidences: list[float] = []

        for raw_file in state.raw_files:
            log.info(f"[DocumentAgent] Processing file: {raw_file.filename}")
            try:
                markdown_text = parse_file(raw_file)
                doc_code, extracted, confidence = extract_document(
                    raw_file, markdown_text, pinecone_context, self.groq, GROQ_MODEL, MAX_RETRIES
                )
                if doc_code:
                    all_extracted[doc_code] = extracted
                    provided_docs.append(doc_code)
                    extraction_confidences.append(confidence)
                    log.info(
                        f"[DocumentAgent] Extracted {doc_code} "
                        f"(confidence={confidence:.2f})"
                    )
            except Exception as exc:
                log.error(f"[DocumentAgent] Failed on {raw_file.filename}: {exc}")
                state.extraction_attempt_count += 1
                if state.extraction_attempt_count > MAX_RETRIES:
                    state.error_budget_exhausted = True

        # ── Step 4: Assemble typed ExtractedDocuments ─────────
        extracted_docs = self._assemble_extracted(all_extracted)

        # ── Step 5: Run validation checks ────────────
        validation_errors = run_validation_checks(extracted_docs, state)

        # ── Step 6: Compute Document Completeness Score ───────
        missing = find_missing_docs(required_docs, provided_docs, state)
        dcs = compute_dcs(required_docs, provided_docs)

        # ── Step 7: Determine status ──────────────────────────
        doc_status = self._determine_doc_status(missing, dcs, validation_errors)

        # ── Step 8: Compute agent confidence ──────────────────
        confidence_score = self._compute_confidence(
            extracted_docs, dcs, validation_errors, extraction_confidences
        )

        # ── Assemble output ───────────────────────────────────
        output = DocumentAgentOutput(
            status=doc_status,
            document_completeness_score=dcs,
            extracted=extracted_docs,
            missing_documents=missing,
            validation_errors=validation_errors,
            required_docs=list(required_docs),
            provided_docs=provided_docs,
            confidence_score=confidence_score,
            extraction_attempts=state.extraction_attempt_count,
            pinecone_policy_context=pinecone_context[:500],  # truncate for storage
        )

        # ── Mutate state ──────────────────────────────────────
        state.document_agent_output = output
        state.validation_errors = validation_errors
        state.missing_documents = missing
        state.missing_fields = [
            f"{m.doc_code}: {m.doc_name}" for m in missing
        ]

        # Update claim-level status
        self._update_claim_status(state, doc_status)

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        state.add_trace(AgentTrace(
            agent_name="DocumentAgent",
            execution_time_ms=elapsed_ms,
            status="SUCCESS" if doc_status == DocumentStatus.READY else "PARTIAL",
            confidence=confidence_score,
            errors=[f"{e.rule}: {e.message}" for e in validation_errors if e.severity == "HARD"],
        ))

        log.info(
            f"[DocumentAgent] Done — status={doc_status.value}, "
            f"DCS={dcs:.1f}%, confidence={confidence_score:.2f}, "
            f"elapsed={elapsed_ms}ms"
        )
        return state

    # ──────────────────────────────────────────────────────────
    # STEP 1: PINECONE RAG
    # ──────────────────────────────────────────────────────────
    def _retrieve_policy_context(self, claim_type: str) -> str:
        """
        Query Pinecone document_rules namespace to get the mandatory
        document checklist for this claim type.
        """
        if self._embed_query is None:
            # Import here to avoid circular imports
            from seed_pinecone import embed_query
            self._embed_query = embed_query

        query = (
            f"Mandatory document requirements checklist for {claim_type} "
            f"insurance claim. What documents are required?"
        )
        vector = self._embed_query(query)

        try:
            result = self.pc_index.query(
                vector=vector,
                top_k=PINECONE_TOP_K,
                namespace=DOC_NAMESPACE,
                include_metadata=True,
            )
            chunks = [
                match.metadata.get("text", "")
                for match in result.matches
                if match.metadata
            ]
            # Fallback: metadata may not include text; use section_title
            if not any(chunks):
                chunks = [
                    f"{match.metadata.get('section_title', '')} "
                    f"[score={match.score:.3f}]"
                    for match in result.matches
                ]
            context = "\n\n---\n\n".join(filter(None, chunks))
            log.info(
                f"[DocumentAgent] Pinecone returned {len(result.matches)} "
                f"chunks for namespace='{DOC_NAMESPACE}'"
            )
            return context or "No policy context retrieved."
        except Exception as exc:
            log.warning(f"[DocumentAgent] Pinecone query failed: {exc}")
            return "Pinecone unavailable — using hardcoded policy rules."

    # ──────────────────────────────────────────────────────────
    # STEP 4: ASSEMBLE TYPED MODEL
    # ──────────────────────────────────────────────────────────
    def _assemble_extracted(self, all_extracted: dict[str, dict]):
        """
        Map raw extraction dicts into the typed Pydantic sub-schemas.
        Unknown keys are silently ignored by Pydantic.
        """
        from state import (
            ExtractedDocuments, ExtractedRC, ExtractedDL,
            ExtractedPolicySchedule, ExtractedClaimForm,
            ExtractedRepairEstimate, ExtractedFIR, ExtractedPhotos
        )

        def _safe(model_cls, data: dict | None):
            if not data:
                return None
            try:
                return model_cls(**{
                    k: v for k, v in data.items()
                    if k in model_cls.model_fields
                })
            except Exception as exc:
                log.warning(f"[DocumentAgent] Assembly warning for {model_cls.__name__}: {exc}")
                return model_cls()

        return ExtractedDocuments(
            rc=_safe(ExtractedRC, all_extracted.get("DOC-001")),
            dl=_safe(ExtractedDL, all_extracted.get("DOC-002")),
            policy_schedule=_safe(ExtractedPolicySchedule, all_extracted.get("DOC-003")),
            claim_form=_safe(ExtractedClaimForm, all_extracted.get("DOC-004")),
            repair_estimate=_safe(ExtractedRepairEstimate, all_extracted.get("DOC-005")),
            fir=_safe(ExtractedFIR, all_extracted.get("DOC-008")),
            photos=_safe(ExtractedPhotos, all_extracted.get("DOC-011")),
            kyc_verified=bool(
                (all_extracted.get("DOC-010") or {}).get("kyc_verified", False)
            ),
            puc_valid=bool(
                (all_extracted.get("DOC-009") or {}).get("puc_valid_until")
            ) or None,
        )

    # ──────────────────────────────────────────────────────────
    # HELPER METHODS
    # ──────────────────────────────────────────────────────────
    def _determine_doc_status(self, missing, dcs: float, validation_errors) -> DocumentStatus:
        """Determine document status based on missing docs, DCS, and validation errors."""
        from state import DocumentStatus

        tier1_missing = [m for m in missing if m.tier == 1]
        hard_errors = [e for e in validation_errors if e.severity == "HARD"]

        if tier1_missing or dcs < 50:
            return DocumentStatus.INCOMPLETE
        elif hard_errors:
            return DocumentStatus.INVALID
        elif dcs < 80:
            return DocumentStatus.INCOMPLETE
        else:
            return DocumentStatus.READY

    def _compute_confidence(self, extracted_docs, dcs: float, validation_errors, extraction_confidences: list[float]) -> float:
        """Compute agent confidence score."""
        avg_extraction_conf = (
            sum(extraction_confidences) / len(extraction_confidences)
            if extraction_confidences else 0.0
        )
        dcs_conf = dcs / 100.0
        error_penalty = 0.1 * len([e for e in validation_errors if e.severity == "HARD"])
        confidence_score = max(0.0, min(1.0,
            (avg_extraction_conf * 0.6) + (dcs_conf * 0.4) - error_penalty
        ))
        return confidence_score

    def _update_claim_status(self, state: ClaimState, doc_status: DocumentStatus) -> None:
        """Update claim-level status based on document status."""
        from state import ClaimStatus

        if doc_status == DocumentStatus.READY:
            state.status = ClaimStatus.DOCUMENTS_COMPLETE
        elif state.error_budget_exhausted:
            state.status = ClaimStatus.ESCALATED_HUMAN
        else:
            state.status = ClaimStatus.DOCUMENTS_PENDING

    # ──────────────────────────────────────────────────────────
    # IDEMPOTENCY HASH
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _hash_files(raw_files: list) -> str:
        """SHA-256 of sorted filenames + sizes — same files = same hash."""
        payload = "|".join(
            f"{f.filename}:{f.size_bytes}"
            for f in sorted(raw_files, key=lambda x: x.filename)
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# STANDALONE TEST HELPER
# ─────────────────────────────────────────────────────────────
def _make_test_state() -> ClaimState:
    """Create a minimal ClaimState for local testing."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from state import ClaimState, RawFile

    return ClaimState(
        claim_id="CLM-2026-TEST01",
        claim_type="OWN_DAMAGE",
        claimant_name="Rajesh Kumar",
        policy_number="SW-MH-2024-00123",
        vehicle_registration="MH02AB1234",
        raw_files=[
            RawFile(
                filename="registration_certificate.pdf",
                file_path="/tmp/rc_sample.pdf",
                doc_type_hint="RC",
                size_bytes=102400,
            ),
            RawFile(
                filename="drivers_license.pdf",
                file_path="/tmp/dl_sample.pdf",
                doc_type_hint="DL",
                size_bytes=51200,
            ),
        ],
    )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    logging.basicConfig(level=logging.INFO)
    state = _make_test_state()
    agent = DocumentVerificationAgent()
    updated_state = agent.run(state)

    output = updated_state.document_agent_output
    print("\n" + "=" * 60)
    print("DOCUMENT AGENT TEST RESULT")
    print("=" * 60)
    print(f"Claim ID    : {updated_state.claim_id}")
    print(f"Status      : {updated_state.status.value}")
    print(f"Doc Status  : {output.status.value}")
    print(f"DCS         : {output.document_completeness_score}%")
    print(f"Confidence  : {output.confidence_score:.2f}")
    print(f"Missing Docs: {[m.doc_code for m in output.missing_documents]}")
    print(f"Hard Errors : {[e.rule for e in output.validation_errors if e.severity == 'HARD']}")