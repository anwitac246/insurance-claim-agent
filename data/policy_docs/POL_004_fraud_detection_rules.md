# POLICY DOCUMENT: POL-004
# FRAUD DETECTION, RED FLAGS & SIU ESCALATION RULES
# SecureWheel Insurance Co. | Effective: April 1, 2026 | Version: 2.5

---

## SECTION 1: OVERVIEW

**Policy ID:** POL-004  
**Linked To:** POL-001, POL-002, POL-003  
**Purpose:** Define the fraud detection framework, scoring methodology, red flag indicators, and escalation protocols for the AI Fraud Agent and Special Investigation Unit (SIU).

Insurance fraud is estimated to cost the Indian motor insurance sector ₹45,000 Crores annually. SecureWheel's Zero Tolerance Fraud Policy mandates AI-first detection with human SIU escalation for high-risk claims.

---

## SECTION 2: FRAUD RISK SCORING MODEL

The Fraud Agent computes a **Fraud Risk Score (FRS)** from 0.0 to 1.0 for every claim.

### 2.1 FRS Thresholds & Actions

| FRS Range | Risk Level | Action |
|---|---|---|
| 0.0 – 0.30 | LOW | Auto-proceed to Decision Agent |
| 0.31 – 0.55 | MEDIUM | Proceed with enhanced scrutiny flag |
| 0.56 – 0.75 | HIGH | HOLD; assign to senior claims executive for review |
| 0.76 – 1.00 | CRITICAL | AUTO-REJECT + Immediate SIU referral |

### 2.2 FRS Computation Formula
FRS is a weighted sum of individual red flag scores:
```
FRS = Σ (Red_Flag_Weight × Red_Flag_Triggered)
```
Maximum raw score is normalized to 1.0. Individual red flags and weights are defined in Section 3.

---

## SECTION 3: RED FLAG INDICATORS & WEIGHTS

### Category A: Policy-Level Red Flags (Weight: High)

| Flag ID | Description | Weight |
|---|---|---|
| RF-A-001 | Policy taken less than 30 days before accident | 0.35 |
| RF-A-002 | Policy renewed specifically after a long lapse (> 6 months), then claimed within 60 days | 0.40 |
| RF-A-003 | Previous claim filed on same policy within the last 6 months | 0.25 |
| RF-A-004 | Policy value (IDV) significantly higher than market value of vehicle (IDV inflation) | 0.30 |
| RF-A-005 | Policy address doesn't match vehicle's usual operating district for > 6 months | 0.20 |
| RF-A-006 | Policyholder has 3 or more claims across any insurer in the past 3 years (check IIB — Insurance Information Bureau) | 0.45 |

### Category B: Document-Level Red Flags (Weight: High)

| Flag ID | Description | Weight |
|---|---|---|
| RF-B-001 | AI detects image manipulation in submitted photos (deepfake/Photoshop artifacts) | 0.55 |
| RF-B-002 | EXIF metadata missing from all submitted damage photos | 0.30 |
| RF-B-003 | EXIF date/time inconsistent with claimed accident date (>4 hour variance) | 0.40 |
| RF-B-004 | EXIF GPS location inconsistent with claimed accident location (>2 km variance) | 0.40 |
| RF-B-005 | FIR filed > 72 hours after accident without valid documented reason | 0.25 |
| RF-B-006 | RC or DL shows signs of tampering (font inconsistency, watermark mismatch) | 0.50 |
| RF-B-007 | Cancelled cheque bank account recently opened (< 90 days) | 0.20 |

### Category C: Incident-Level Red Flags (Weight: Medium)

| Flag ID | Description | Weight |
|---|---|---|
| RF-C-001 | Accident reported on a holiday, weekend, or late night (11pm–5am) without corroborating witness | 0.15 |
| RF-C-002 | Damage pattern inconsistent with claimed accident type (e.g., fire damage claimed as collision) | 0.50 |
| RF-C-003 | Vehicle damage photos show pre-existing rust/damage clearly predating the claimed incident | 0.35 |
| RF-C-004 | Claimed accident location is a known fraud hotspot (from historical Pinecone vector DB) | 0.30 |
| RF-C-005 | Accident involves two vehicles with same IP address on digital claim submission | 0.60 |
| RF-C-006 | Vehicle reported as total loss after recent high-premium renewal | 0.35 |
| RF-C-007 | Multiple claims for same vehicle across different insurers in same calendar year | 0.55 |

### Category D: Garage/Vendor Red Flags (Weight: Medium)

| Flag ID | Description | Weight |
|---|---|---|
| RF-D-001 | Garage invoice shows parts not consistent with damage shown in photos | 0.40 |
| RF-D-002 | Garage has flagged > 15 suspicious claims in the last 12 months (Pinecone DB check) | 0.35 |
| RF-D-003 | Garage repair cost significantly higher than SecureWheel benchmark (>40% above avg) | 0.25 |
| RF-D-004 | Invoice uses sequential invoice numbers (potential invoice fabrication) | 0.20 |
| RF-D-005 | Garage is newly registered (< 6 months) with no track record | 0.20 |
| RF-D-006 | Same repairer, same claimant combination for third time in 12 months | 0.30 |

### Category E: Behavioral/Historical Red Flags (Weight: Low-Medium)

| Flag ID | Description | Weight |
|---|---|---|
| RF-E-001 | Claimant's phone number matches a number flagged in IIB fraud registry | 0.50 |
| RF-E-002 | Claimant's email/IP matches a previously rejected fraudulent claim | 0.55 |
| RF-E-003 | Vehicle VIN found in stolen vehicle database | 0.90 |
| RF-E-004 | Driver named on DL is also named on 2+ other companies' claims in 12 months | 0.40 |
| RF-E-005 | Claim submitted via unusual channel or geography (e.g., Mumbai policy submitted from Delhi IP) | 0.15 |

---

## SECTION 4: SOFT FRAUD vs. HARD FRAUD CLASSIFICATION

### 4.1 Soft Fraud (Opportunistic Fraud)
Definition: Real accident, but claimant inflates the claim amount or includes pre-existing damage.
- Indicators: RF-C-003, RF-D-001, RF-D-003, RF-B-002
- Response: Partial claim approval after deducting inflated/pre-existing items; claimant warned; NCB forfeited
- **AI Rule:** Soft fraud FRS 0.31–0.55 → Approve adjusted amount + issue FRAUD WARNING LETTER

### 4.2 Hard Fraud (Staged/Deliberate Fraud)
Definition: Accident is entirely fabricated or deliberately staged.
- Indicators: RF-B-001, RF-C-005, RF-E-003, RF-A-006, RF-C-002
- Response: AUTO-REJECT + SIU referral + Policy cancellation + IIB blacklist reporting
- **AI Rule:** Hard fraud FRS > 0.75 → AUTO-REJECT; log to Pinecone `fraud_cases` namespace; notify SIU within 1 hour

### 4.3 Internal/Agent Fraud
Definition: Fraud perpetrated by a SecureWheel agent or empaneled garage.
- Indicators: RF-D-002, RF-D-004, RF-D-006 combined
- Response: SIU referral + Garage de-empanelment pending investigation

---

## SECTION 5: PINECONE FRAUD VECTOR DB RULES

The Fraud Agent uses Pinecone for:

### 5.1 Historical Claim Pattern Matching
- Namespace: `fraud_historical_claims`
- Query: Embed claim metadata (location, garage, claimant, date, amount) → find cosine similarity > 0.85 with known fraud cases
- If match found: Add RF weight of 0.40 automatically

### 5.2 Fraud Hotspot Location DB
- Namespace: `fraud_hotspots`
- Contains: GPS coordinates of high-fraud accident locations (radius 500m clustering)
- If claimed accident GPS within 500m of a hotspot: RF-C-004 triggered

### 5.3 Flagged Vendor Registry
- Namespace: `flagged_vendors`
- Contains: Garage GST numbers and workshop codes with fraud history
- If workshop code matches: RF-D-002 triggered

### 5.4 Blacklisted Entity Registry
- Namespace: `blacklisted_entities`
- Contains: Claimant Aadhaar hash, PAN hash, phone hash, email hash, IP hash
- Any match: RF-E-001 or RF-E-002 triggered; FRS += 0.50 minimum

---

## SECTION 6: SIU ESCALATION PROTOCOL

When FRS > 0.75 OR any E-003 (stolen VIN) flag is triggered:

1. **Immediate Actions (within 1 hour):**
   - Auto-reject claim with reason code `FRAUD_SIU_REFERRAL`
   - Generate SIU Alert with: Claim ID, FRS score, triggered flags, evidence summary
   - Freeze any pending payments on the account

2. **Within 24 Hours:**
   - Assign a human SIU investigator
   - Request police verification of FIR details
   - Commission independent surveyor inspection

3. **Within 72 Hours:**
   - SIU field investigation at accident location and garage
   - Claimant interview (if soft fraud only)
   - Submit findings to legal team if hard fraud confirmed

4. **Reporting:**
   - All confirmed fraud cases reported to IIB (Insurance Information Bureau of India) within 7 days
   - Policy cancelled; claimant blacklisted across all IRDAI member insurers

---

## SECTION 7: FRAUD AGENT OUTPUT SCHEMA

The Fraud Agent must output the following structured data for every claim:

```json
{
  "claim_id": "string",
  "fraud_risk_score": 0.0,
  "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "triggered_flags": [
    {
      "flag_id": "RF-X-XXX",
      "description": "string",
      "weight": 0.0,
      "evidence": "string"
    }
  ],
  "fraud_type": "NONE | SOFT | HARD | INTERNAL",
  "pinecone_similar_cases": ["claim_id_1", "claim_id_2"],
  "hotspot_match": true,
  "blacklist_match": false,
  "recommendation": "PROCEED | HOLD | REJECT_SIU",
  "siu_alert_generated": false,
  "agent_confidence": 0.0,
  "reasoning_trace": "string"
}
```
