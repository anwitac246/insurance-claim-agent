# POLICY DOCUMENT: POL-002
# MANDATORY DOCUMENT REQUIREMENTS FOR CLAIM PROCESSING
# SecureWheel Insurance Co. | Effective: April 1, 2026 | Version: 2.1

---

## SECTION 1: PURPOSE & SCOPE

**Policy ID:** POL-002  
**Linked To:** POL-001 (Master Coverage Policy)  
**Purpose:** Define the exact document requirements for each claim category. This document is the ground truth for the Document Validation Agent. Every document listed under a specific claim type is MANDATORY unless explicitly marked [CONDITIONAL].

Failure to provide any mandatory document results in a "PENDING — DOCUMENT INCOMPLETE" status. The claimant must be notified within 24 hours with a precise list of missing documents.

---

## SECTION 2: TIER 1 — MANDATORY CORE DOCUMENTS (ALL CLAIMS)

These documents are required for EVERY claim without exception, regardless of claim type, value, or vehicle category.

### DOC-001: Registration Certificate (RC)
- **Accepted Format:** Original or government-certified digital copy (DigiLocker RC accepted)
- **Validation Rules:**
  - Registration number must EXACTLY match the policy schedule
  - Engine number (last 5 digits minimum) must match policy
  - Chassis number (last 5 digits minimum) must match policy
  - RC must NOT be expired at date of loss
  - Name of registered owner must match policy schedule (or an endorsement for transfer must exist)
- **Rejection Trigger:** Any mismatch in engine/chassis number → FLAG for human review
- **AI Extraction Fields:** `registration_number`, `engine_number`, `chassis_number`, `owner_name`, `vehicle_class`, `fuel_type`, `rc_expiry_date`

### DOC-002: Driver's License (DL)
- **Accepted Format:** Original, laminated copy, or DigiLocker DL (Driving License)
- **Validation Rules:**
  - DL must be VALID (not expired) on the DATE OF ACCIDENT
  - DL must cover the CLASS of vehicle involved:
    - LMV (Light Motor Vehicle) for cars up to 7500kg
    - MCWG (Motorcycle With Gear) for two-wheelers above 50cc
    - Transport Vehicle license for commercial trucks/taxis
  - DL must belong to the person driving at the time of accident
  - Learner's License (LL): Claim is VALID only if a permanent DL holder was present in the vehicle
- **Rejection Trigger:** Expired DL, wrong vehicle class, or DL not belonging to driver → AUTO-REJECT (Exclusion E-002)
- **AI Extraction Fields:** `dl_number`, `holder_name`, `dob`, `vehicle_classes_authorized`, `dl_validity_date`, `issue_state`

### DOC-003: Insurance Policy Schedule
- **Accepted Format:** Soft copy (PDF/JPG) or original paper policy
- **Validation Rules:**
  - Policy number must be unique and verified against SecureWheel's policy database
  - Policy period (start & end date) must cover the date of accident
  - IDV (Insured Declared Value) must be present and numeric
  - Coverage type must be verified (Comprehensive vs TP-Only — TP-Only cannot process OD claims)
  - Policyholder name must match RC owner (or valid endorsement must exist)
- **Rejection Trigger:** Policy expired at date of accident → AUTO-REJECT
- **AI Extraction Fields:** `policy_number`, `policy_start_date`, `policy_end_date`, `idv`, `coverage_type`, `policyholder_name`, `vehicle_registration`, `premium_paid`, `ncb_percentage`

### DOC-004: Duly Filled & Signed Claim Form
- **Accepted Format:** SecureWheel standard claim form (Form CF-2026) — physical or e-signed digital
- **Mandatory Fields on Claim Form:**
  - Date, time, and exact location of accident (GPS coordinates or address)
  - Cause of accident (collision, fire, theft, natural calamity, etc.)
  - Third-party involved: Yes/No (if Yes, third-party details required)
  - Police report filed: Yes/No (FIR number if applicable)
  - Claimant's signature (wet or DSC — Digital Signature Certificate)
  - Estimated repair cost (preliminary)
- **Rejection Trigger:** Unsigned claim form or missing date-of-accident → INCOMPLETE status
- **AI Extraction Fields:** `claim_date`, `accident_date`, `accident_time`, `accident_location`, `accident_cause`, `estimated_loss`, `claimant_signature_present`, `fir_reported`, `third_party_involved`

---

## SECTION 3: TIER 2 — FINANCIAL & TECHNICAL DOCUMENTS

### DOC-005: Repair Estimate / Workshop Invoice (Initial)
- **Who Provides It:** Empaneled garage OR any IRDAI-registered workshop
- **Validation Rules:**
  - Must be on official letterhead with garage GST number and IRDAI workshop code
  - Must be itemized: each part listed separately with part number, quantity, and unit cost
  - Labor charges must be listed separately from parts cost
  - Estimate must NOT include pre-existing damage unrelated to the claimed incident
  - Empaneled garage estimates are auto-approved up to ₹50,000 without surveyor visit
  - Non-empaneled garage: Surveyor assessment mandatory for any claim
- **AI Extraction Fields:** `garage_name`, `garage_gst`, `workshop_code`, `total_parts_cost`, `total_labor_cost`, `grand_total_estimate`, `is_empaneled`, `listed_damaged_parts[]`

### DOC-006: Final Repair Bill & Payment Receipt [CONDITIONAL — Reimbursement Claims Only]
- **Required For:** Reimbursement claims (where claimant has already paid the garage)
- **NOT Required For:** Cashless claims (garage paid directly by SecureWheel)
- **Validation Rules:**
  - Final bill amount must be consistent with the approved estimate (variance > 20% triggers re-survey)
  - Payment receipt must show full payment made to garage by claimant
  - Bank transfer proof (NEFT/RTGS reference) or UPI reference accepted; cash payment above ₹10,000 NOT accepted as per IRDAI 2026 norms
- **AI Extraction Fields:** `final_bill_amount`, `payment_mode`, `payment_reference`, `payment_date`, `payee_name`

### DOC-007: Cancelled Cheque / Bank Account Details
- **Purpose:** To process Electronic Fund Transfer (EFT) for claim settlement
- **Validation Rules:**
  - Account name on cheque must match policyholder's name
  - IFSC code and account number must be valid
  - Only savings or current accounts accepted; no loan/credit accounts
  - Alternatively, pre-verified UPI ID accepted for claims up to ₹50,000
- **AI Extraction Fields:** `bank_name`, `ifsc_code`, `account_number`, `account_holder_name`, `bank_branch`

---

## SECTION 4: TIER 3 — LEGAL & INCIDENT VALIDATION DOCUMENTS

### DOC-008: First Information Report (FIR) [CONDITIONAL]
- **MANDATORY for these incident types:**
  - Theft of vehicle (entire vehicle stolen)
  - Third-party bodily injury or death
  - Third-party property damage above ₹50,000
  - Fire damage (arson suspected)
  - Major collision on public road involving multiple vehicles
  - Hit-and-run by unknown vehicle
- **NOT Required For:** Minor single-vehicle dents, parking damage, flood damage, natural calamity
- **Validation Rules:**
  - FIR must be registered at the police station with jurisdiction over accident location
  - FIR date must be within 24 hours of accident (delayed FIR > 24 hrs: FLAG with reason)
  - FIR number must be verifiable (AI system to log for manual verification)
- **AI Extraction Fields:** `fir_number`, `police_station`, `fir_date`, `fir_time`, `fir_jurisdiction_district`, `fir_officer_name`

### DOC-009: Pollution Under Control (PUC) Certificate [CONDITIONAL]
- **MANDATORY for all claims effective April 1, 2026 (IRDAI 2026 directive)**
- **Exempted:** Vehicles with active BS-VI emission certification renewed within 6 months
- **Validation Rules:**
  - PUC must be VALID on date of accident
  - Expired PUC at time of accident: Claim is REDUCED by 10% as non-compliance penalty
  - Missing PUC with no valid reason: Claim HELD until PUC status verified
- **AI Extraction Fields:** `puc_certificate_number`, `puc_valid_until`, `puc_testing_center`, `emission_standard`

### DOC-010: KYC Documents — Aadhaar or PAN [CONDITIONAL]
- **MANDATORY for:**
  - Claims with gross assessed value above ₹1,00,000 (1 Lakh)
  - Any claim where policyholder's identity has not been previously KYC-verified in SecureWheel's system
  - All new policyholders filing their first claim
- **Accepted Documents (any one):**
  - Aadhaar Card (masked — only last 4 digits of Aadhaar number should be visible per UIDAI guidelines)
  - PAN Card
  - Aadhaar-linked mobile OTP verification (digital KYC)
- **Validation Rules:**
  - Name on KYC document must match policy schedule name (minor spelling variations: FLAG for human review)
  - PAN must not be on the CIBIL defaulter list or IRDAI watchlist
- **AI Extraction Fields:** `kyc_type`, `kyc_id_masked`, `kyc_name`, `kyc_dob`, `kyc_verified`

---

## SECTION 5: TIER 4 — VISUAL EVIDENCE (MANDATORY FROM 2026)

### DOC-011: Accident Scene Photographs/Videos
- **MANDATORY:** Minimum 4 photographs of the damaged vehicle from all angles
- **Recommended:** Video walkthrough of damage (360° of vehicle)
- **Validation Rules:**
  - Photographs must show damage consistent with the claimed incident type
  - EXIF metadata (date/time/GPS) must align with claimed date and location of accident
  - Images must NOT be edited or digitally altered (AI fraud detection applied)
  - For theft claims: Photograph of the location from where vehicle was stolen
  - For flood claims: Photographs showing water level marks on vehicle
- **AI Extraction Fields:** `image_count`, `video_present`, `exif_date_consistent`, `exif_gps_consistent`, `damage_visible`, `damage_type_detected`, `ai_manipulation_score`

### DOC-012: Dashboard / Odometer Photograph
- **MANDATORY for:** Claims where vehicle age or mileage is disputed
- **Shows:** Odometer reading, fuel level, warning lights active at time of damage
- **AI Extraction Fields:** `odometer_reading`, `fuel_level_indicator`, `warning_lights_active[]`

---

## SECTION 6: DOCUMENT COMPLETENESS SCORING

The Document Agent must compute a Document Completeness Score (DCS) before passing to the next agent:

```
DCS = (Documents_Provided / Documents_Required_for_Claim_Type) × 100
```

**Decision Logic based on DCS:**
- **DCS = 100%** → Proceed to Policy Agent and Fraud Agent
- **DCS = 80–99%** → CONDITIONAL HOLD: Proceed with flag; notify claimant of missing docs within 24 hrs
- **DCS = 50–79%** → INCOMPLETE: Halt processing; return full missing document list to claimant
- **DCS < 50%** → REJECT as INSUFFICIENT DOCUMENTATION; claimant must restart

**Minimum DCS to proceed:** 80% (all Tier 1 documents must be 100% present regardless of DCS)
