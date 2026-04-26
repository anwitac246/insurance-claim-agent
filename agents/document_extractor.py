"""
agents/document_extractor.py
===========================
LLM-based document extraction utilities for Document Verification Agent.
"""

from __future__ import annotations

import json
import time
from typing import Any, Tuple

from groq import Groq


def extract_document(
    raw_file: Any,
    markdown_text: str,
    policy_context: str,
    groq_client: Groq,
    model: str = "llama-3.3-70b-versatile",
    max_retries: int = 2
) -> Tuple[str, dict, float]:
    """
    Use Groq LLM to:
      1. Identify which document type this is (RC, DL, Policy, etc.)
      2. Extract all typed fields for that document type.
      3. Return (doc_code, extracted_dict, confidence_score).

    Temperature=0 for idempotency.
    Retries up to MAX_RETRIES times on JSON parse failure.
    """
    system_prompt = f"""You are a document extraction AI for SecureWheel Insurance.
You receive parsed text from an insurance claim document and extract structured data.

Policy document requirements context:
{policy_context[:2000]}

RULES:
- First identify the document type. Return doc_code as one of:
  DOC-001 (RC), DOC-002 (DL), DOC-003 (Policy Schedule),
  DOC-004 (Claim Form), DOC-005 (Repair Estimate), DOC-006 (Final Bill),
  DOC-007 (Bank Details), DOC-008 (FIR), DOC-009 (PUC), DOC-010 (KYC),
  DOC-011 (Photos/Evidence), DOC-012 (Dashboard Photo)
- Extract ALL fields visible in the document. Use null for missing fields.
- Output ONLY valid JSON. No explanation, no markdown fences.
- Include a "confidence" field (0.0–1.0) reflecting how clearly you could read the document.
- Include a "doc_code" field.

JSON schema (use only fields relevant to the identified doc type):
{{
  "doc_code": "DOC-XXX",
  "confidence": 0.95,
  "registration_number": null,
  "engine_number": null,
  "chassis_number": null,
  "owner_name": null,
  "vehicle_class": null,
  "fuel_type": null,
  "rc_expiry_date": null,
  "dl_number": null,
  "holder_name": null,
  "dob": null,
  "vehicle_classes_authorized": [],
  "dl_validity_date": null,
  "issue_state": null,
  "policy_number": null,
  "policy_start_date": null,
  "policy_end_date": null,
  "idv": null,
  "coverage_type": null,
  "policyholder_name": null,
  "vehicle_registration": null,
  "premium_paid": null,
  "ncb_percentage": null,
  "voluntary_deductible": 0,
  "add_ons": [],
  "claim_date": null,
  "accident_date": null,
  "accident_time": null,
  "accident_location": null,
  "accident_cause": null,
  "estimated_loss": null,
  "claimant_signature_present": false,
  "fir_reported": false,
  "fir_number": null,
  "third_party_involved": false,
  "garage_name": null,
  "garage_gst": null,
  "workshop_code": null,
  "total_parts_cost": null,
  "total_labor_cost": null,
  "grand_total_estimate": null,
  "is_empaneled": false,
  "listed_damaged_parts": [],
  "fir_date": null,
  "police_station": null,
  "fir_jurisdiction_district": null,
  "bank_name": null,
  "ifsc_code": null,
  "account_number": null,
  "account_holder_name": null,
  "kyc_type": null,
  "kyc_name": null,
  "kyc_verified": false,
  "puc_valid_until": null,
  "image_count": 0,
  "ai_manipulation_score": 0.0
}}"""

    user_prompt = f"""Document filename: {raw_file.filename}
Document hint: {raw_file.doc_type_hint or 'not provided'}

Parsed document text:
{markdown_text[:4000]}

Extract and return JSON only."""

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,          # idempotency
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            raw_json = response.choices[0].message.content
            extracted = json.loads(raw_json)
            doc_code = extracted.pop("doc_code", "UNKNOWN")
            confidence = float(extracted.pop("confidence", 0.7))
            return doc_code, extracted, confidence

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = exc
            # In a real implementation, we would log this warning
            time.sleep(0.5 * (attempt + 1))

    # All attempts failed
    return "UNKNOWN", {}, 0.0