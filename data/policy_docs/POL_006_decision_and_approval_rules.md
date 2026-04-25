# POLICY DOCUMENT: POL-006
# FINAL DECISION RULES, APPROVAL CRITERIA & REASONING TRACE STANDARDS
# SecureWheel Insurance Co. | Effective: April 1, 2026 | Version: 1.5

---

## SECTION 1: OVERVIEW

**Policy ID:** POL-006  
**Linked To:** POL-001 through POL-005  
**Purpose:** Define the Decision Agent's final approval/rejection logic, confidence thresholds, the mandatory SRE-grade reasoning trace format, and the output schema for every claim decision.

This document is the authoritative playbook for Agent 5 (Decision Agent). Every output must be deterministic, explainable, and auditable.

---

## SECTION 2: CLAIM DECISION STATES

Every claim must be assigned EXACTLY ONE of the following terminal states:

| State Code | Label | Description |
|---|---|---|
| D-001 | APPROVED | All checks passed; payout authorized |
| D-002 | APPROVED_PARTIAL | Claim valid but payout reduced (depreciation, partial fraud, cap applied) |
| D-003 | PENDING_DOCUMENTS | Missing mandatory documents; claimant notified |
| D-004 | PENDING_INVESTIGATION | SIU referral; auto-hold on payment |
| D-005 | REJECTED_EXCLUSION | Rejected due to a named policy exclusion |
| D-006 | REJECTED_FRAUD | Rejected due to confirmed or high-risk fraud |
| D-007 | REJECTED_POLICY_LAPSED | Policy was expired at date of accident |
| D-008 | REJECTED_COVERAGE_MISMATCH | Claimed incident not covered under active policy type |
| D-009 | ESCALATED_HUMAN | Confidence < 0.70 or edge case; requires human senior adjuster |

---

## SECTION 3: DECISION LOGIC FLOWCHART (SEQUENTIAL CHECKS)

The Decision Agent must execute checks in this EXACT ORDER. Failing any check triggers the listed state and STOPS further processing:

### Step 1: Policy Validity Check
```
IF policy_end_date < accident_date → STATE: D-007 (REJECTED_POLICY_LAPSED)
IF engine_number MISMATCH → STATE: D-009 (ESCALATED_HUMAN)
IF chassis_number MISMATCH → STATE: D-009 (ESCALATED_HUMAN)
```

### Step 2: Document Completeness Check
```
IF DCS < 80% → STATE: D-003 (PENDING_DOCUMENTS)
IF DCS 80–99% AND Tier 1 docs all present → PROCEED with flag
IF DCS = 100% → PROCEED clean
```

### Step 3: Coverage Eligibility Check
```
IF coverage_type = "TP_ONLY" AND claim_type = "OWN_DAMAGE" → STATE: D-008
IF accident_cause IN absolute_exclusions (E-001 to E-007) → STATE: D-005
IF add_on_required AND add_on_active = False → REDUCE payout / D-005 for that component
```

### Step 4: Fraud Risk Check
```
IF FRS > 0.75 → STATE: D-006 (REJECTED_FRAUD)
IF FRS 0.56–0.75 → STATE: D-004 (PENDING_INVESTIGATION)
IF FRS 0.31–0.55 → PROCEED with FRAUD_MEDIUM_FLAG; may trigger D-002
IF FRS ≤ 0.30 → PROCEED clean
```

### Step 5: Payout Computation
```
Run payout computation as per POL-003, Section 7
IF computed_payout > IDV → CAP at IDV
IF Total_Loss_Condition → Follow Section 2.3 of POL-003
```

### Step 6: Confidence Assessment
```
IF agent_confidence < 0.70 → STATE: D-009 (ESCALATED_HUMAN)
IF agent_confidence 0.70–0.85 → APPROVED/REJECTED with human review recommended
IF agent_confidence > 0.85 → APPROVED/REJECTED autonomous
```

### Step 7: Final State Assignment
```
IF all checks PASSED AND payout = full amount → D-001 (APPROVED)
IF all checks PASSED AND payout REDUCED → D-002 (APPROVED_PARTIAL)
```

---

## SECTION 4: CONFIDENCE SCORING MODEL

The Decision Agent computes an overall **Agent Confidence Score (ACS)** from 0.0 to 1.0:

### 4.1 ACS Components

| Component | Description | Max Weight |
|---|---|---|
| Document OCR Confidence | Avg confidence of LlamaParse extractions across all docs | 0.20 |
| Policy Match Confidence | Certainty of policy rule matching from RAG | 0.20 |
| Fraud Score Certainty | Inverse of FRS for low-risk; penalized for medium/high | 0.25 |
| Data Consistency | Cross-document validation (dates, names, amounts all agree) | 0.20 |
| Visual Evidence Quality | Image count, EXIF validity, damage consistency score | 0.15 |

**Formula:**
```
ACS = (Doc_OCR_conf × 0.20) + (Policy_match_conf × 0.20) + 
      ((1 - FRS) × 0.25) + (Data_consistency × 0.20) + (Visual_conf × 0.15)
```

### 4.2 Auto-Approval Threshold
- ACS > 0.85 AND FRS < 0.30 AND DCS = 100% → AUTO-APPROVE; no human in loop
- ACS < 0.70 → ALWAYS route to human adjuster; AI provides recommendation only
- ACS 0.70–0.85 → AI decision stands but human adjuster notified for next-day review

---

## SECTION 5: SRE-GRADE REASONING TRACE FORMAT

Every claim decision MUST produce a structured reasoning trace. This is mandatory for audit, regulatory compliance, and system debugging.

### 5.1 Reasoning Trace Schema
```json
{
  "claim_id": "CLM-2026-XXXXXX",
  "trace_version": "1.0",
  "trace_timestamp": "ISO-8601 datetime",
  "agents_executed": [
    {
      "agent_name": "DocumentAgent",
      "execution_time_ms": 0,
      "status": "SUCCESS | PARTIAL | FAILED",
      "outputs": {},
      "confidence": 0.0,
      "errors": []
    }
  ],
  "policy_checks": [
    {
      "check_id": "RULE-M-001",
      "check_name": "string",
      "result": "PASS | FAIL | SKIPPED",
      "details": "string"
    }
  ],
  "fraud_analysis": {
    "frs": 0.0,
    "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
    "triggered_flags": [],
    "pinecone_matches": []
  },
  "payout_computation": {
    "gross_repair_cost": 0,
    "depreciation_applied": 0,
    "deductible_compulsory": 0,
    "deductible_voluntary": 0,
    "idv_cap_applied": false,
    "final_approved_amount": 0,
    "settlement_mode": "CASHLESS | REIMBURSEMENT | TOTAL_LOSS"
  },
  "final_decision": {
    "state_code": "D-001",
    "state_label": "APPROVED",
    "agent_confidence_score": 0.0,
    "human_review_required": false,
    "rejection_reason": null,
    "ncb_reset": false,
    "siu_referral": false,
    "settlement_sla_days": 0
  },
  "decision_narrative": "Plain English explanation of the decision for the claimant and adjuster"
}
```

### 5.2 Decision Narrative Standards
The `decision_narrative` field must:
- Be written in clear English (not technical jargon)
- State what was verified, what was found, and why the decision was made
- For rejections: Cite the specific rule/exclusion code that triggered rejection
- For partial approvals: Explain exactly what was deducted and why
- Length: 100–300 words; structured but human-readable

**Example Approved Narrative:**
"Claim CLM-2026-001234 has been APPROVED for ₹42,500. All mandatory documents (RC, DL, Policy, Claim Form) were verified and consistent. The vehicle (MH-02-AB-1234, a 2023 Honda City, 2 years old) is covered under a Comprehensive Policy valid until December 2026. The accident on April 10, 2026 at Andheri, Mumbai is consistent with the submitted photographs (EXIF date/GPS verified). Repair estimate from Shree Motors (Empaneled — code SW-MUM-145) totals ₹47,000. After applying metal parts depreciation (10% for 2-year-old vehicle = ₹2,500) and compulsory deductible (₹1,000), the approved payout is ₹43,500. Fraud risk score is LOW (0.12). Settlement via cashless mode; garage will be paid directly within 7 business days."

---

## SECTION 6: APPEALS & RECONSIDERATION PROCESS

- Any rejected claim may be appealed within 30 days of rejection notice
- Appeal triggers: Human senior adjuster review + fresh fraud analysis
- Grounds for appeal: New documents submitted, factual error in AI assessment, dispute of exclusion applicability
- Appeal outcome is FINAL and communicated within 21 days
- IRDAI Ombudsman escalation available if appeal is also rejected

---

## SECTION 7: REGULATORY COMPLIANCE RULES

The AI system must log all of the following for IRDAI audit compliance:

**COMP-001:** Every claim decision must be logged with timestamp, agent version, and model used.  
**COMP-002:** All data used in the decision (extracted fields, scores, rule checks) must be stored in immutable audit log for minimum 7 years.  
**COMP-003:** No claim above ₹5 Lakhs can be auto-approved; human sign-off mandatory.  
**COMP-004:** System must be capable of generating a human-readable explanation of any decision within 60 seconds of request (XAI — Explainable AI requirement per IRDAI 2026 AI circular).  
**COMP-005:** All PII (Aadhaar, PAN, bank details) must be masked in logs; only last 4 digits or hashed values stored.  
**COMP-006:** AI model version and parameters used for each claim must be stored for reproducibility.

---

## SECTION 8: ESCALATION MATRIX

| Scenario | Auto-Action | Human Escalation Level |
|---|---|---|
| Claim > ₹5 Lakhs | HOLD | Senior Adjuster (L3) |
| FRS 0.56–0.75 | HOLD | Claims Executive (L2) |
| FRS > 0.75 | AUTO-REJECT + SIU | SIU Investigator + Legal |
| ACS < 0.70 | HOLD | Junior Adjuster (L1) |
| Engine/Chassis mismatch | HOLD | Senior Adjuster (L3) |
| Total Loss declaration | HOLD | Senior Surveyor + L3 Adjuster |
| Third-party death | HOLD | Legal Team + L3 Adjuster |
| Policy > ₹1Cr IDV | HOLD | Reinsurance Desk + L3 |
