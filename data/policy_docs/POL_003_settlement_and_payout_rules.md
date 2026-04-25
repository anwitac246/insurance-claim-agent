# POLICY DOCUMENT: POL-003
# CLAIM SETTLEMENT, DEPRECIATION & PAYOUT CALCULATION RULES
# SecureWheel Insurance Co. | Effective: April 1, 2026 | Version: 3.0

---

## SECTION 1: OVERVIEW

**Policy ID:** POL-003  
**Linked To:** POL-001, POL-002  
**Purpose:** Define the precise financial rules for computing claim payout amounts, applying depreciation, handling deductibles, and processing settlement via different modes.

This document is the authoritative reference for the Decision Agent when computing final approved amounts.

---

## SECTION 2: CLAIM TYPES & SETTLEMENT MODES

### 2.1 Cashless Settlement
- Vehicle is repaired at a SecureWheel Empaneled Garage
- SecureWheel pays the garage directly after surveyor approval
- Claimant pays only: Compulsory Deductible + Non-covered items + Depreciation amount
- **Advantages:** No upfront payment by claimant; fastest settlement (target: 7 business days)
- **AI Rule:** If garage is empaneled (verify via `workshop_code` in DOC-005), default to cashless track

### 2.2 Reimbursement Settlement
- Vehicle repaired at a non-empaneled garage OR claimant has already paid
- Claimant submits final bill (DOC-006) after repair
- SecureWheel reimburses the approved amount minus deductibles/depreciation
- **Processing Time Target:** 15 business days from complete document submission
- **AI Rule:** If `is_empaneled = False` in DOC-005 extraction, route to reimbursement track; mandatory surveyor visit required

### 2.3 Total Loss Settlement
- If estimated repair cost > 75% of IDV → Declare Constructive Total Loss (CTL)
- Payout = IDV - Salvage Value - Policy Excess (Compulsory Deductible)
- Claimant must transfer RC ownership to SecureWheel (subrogation)
- **AI Rule:** If `grand_total_estimate > 0.75 × idv` → flag as TOTAL LOSS; escalate to Senior Surveyor

---

## SECTION 3: DEPRECIATION SCHEDULE FOR PARTS

When settling OD claims, depreciation is applied to replaced parts (NOT labor). The AI Decision Agent must apply the correct depreciation rate per part category:

### 3.1 Rubber, Nylon, Plastic Parts, Tyres, Tubes, Batteries, Airbags
| Part Category | Depreciation Rate |
|---|---|
| Rubber/Nylon/Plastic/Airbags | 50% |
| Tyres and Tubes | 50% (only if other body damage present) |
| Batteries (vehicle age > 2 yrs) | 50% |
| Batteries (vehicle age < 2 yrs) | 30% |

### 3.2 Fiberglass Components
| Vehicle Age | Depreciation Rate |
|---|---|
| Up to 5 years | 30% |
| Beyond 5 years | 50% |

### 3.3 All Metal Parts (Body, Frame, Engine Components)
| Vehicle Age | Depreciation Rate |
|---|---|
| Up to 6 months | 0% (Nil depreciation) |
| 6 months to 1 year | 5% |
| 1 year to 2 years | 10% |
| 2 years to 3 years | 15% |
| 3 years to 4 years | 25% |
| 4 years to 5 years | 35% |
| Beyond 5 years | 40% |

### 3.4 Glass Parts (Windshield, Windows)
- **Depreciation: NIL (0%)** — Full replacement cost covered regardless of vehicle age
- Exception: If windshield is replaced with non-OEM glass, 15% depreciation applies

### 3.5 Paint & Labor Charges
- **Depreciation: NIL (0%)** — Labor and painting charges are paid at actuals
- Exception: If overall vehicle age > 10 years, 10% depreciation on painting charges

---

## SECTION 4: DEDUCTIBLES (EXCESS)

### 4.1 Compulsory Deductible (Mandatory — Cannot be waived)
This amount is always deducted from the claim payout regardless of claim size:

| Vehicle Type | Compulsory Deductible |
|---|---|
| Two-wheelers (up to 150cc) | ₹100 |
| Two-wheelers (above 150cc) | ₹200 |
| Private Cars (engine up to 1500cc) | ₹1,000 |
| Private Cars (engine above 1500cc) | ₹2,000 |
| Commercial Vehicles (up to 1 Ton) | ₹1,500 |
| Commercial Vehicles (above 1 Ton) | ₹2,000–₹5,000 (based on GVW) |

### 4.2 Voluntary Deductible (Optional — Agreed at Policy Inception)
- Policyholder may opt for a higher voluntary deductible in exchange for lower premium
- Voluntary deductible amount is specified on the Policy Schedule
- **AI Rule:** Extract `voluntary_deductible` from DOC-003 (Policy Schedule); add to compulsory deductible for net deduction

### 4.3 Deductible Calculation Formula
```
Net Claim Payout = Gross Assessed Loss - Depreciation Amount - Compulsory Deductible - Voluntary Deductible - Salvage Value (if any)
```

---

## SECTION 5: SPECIFIC LOSS SCENARIOS & PAYOUT RULES

### 5.1 Theft (Total Vehicle Theft)
- Wait period: 30 days from date of theft before claim settlement (to allow police recovery efforts)
- Required: FIR (mandatory) + Non-traceable report from police or court order
- Payout = IDV - Compulsory Deductible (no depreciation applied to IDV for theft)
- Outstanding loan on vehicle: Settlement made to financer first, remainder to claimant
- **AI Rule:** If `accident_cause = "theft"` and FIR missing → HOLD; set 30-day wait timer

### 5.2 Partial Theft (Accessories/Parts Stolen)
- Stolen parts must be listed on the policy schedule as declared accessories
- Payout = Replacement cost of stolen parts - Depreciation (as per schedule) - Deductible
- Undeclared accessories: NOT claimable

### 5.3 Fire Damage
- FIR mandatory if fire is of suspicious origin
- Fire damage to engine/interiors: Covered under comprehensive policy
- Spontaneous combustion: Covered if vehicle is less than 5 years old; investigated for 5+ years
- **AI Rule:** Fire claims with suspicious FIR origin + vehicle age > 5 years → FRAUD FLAG

### 5.4 Natural Calamity (Flood, Cyclone, Earthquake)
- IRDAI may declare a catastrophe zone, enabling fast-track settlement within 7 days
- Engine damage due to water ingression (hydrostatic lock):
  - Covered IF engine was not started after water entry
  - NOT covered (Engine Hydrostatic Lock Exclusion) if evidence shows engine was started in flooded condition
- **AI Rule:** Check IRDAI catastrophe zone declaration for claim date and location

### 5.5 Hit-and-Run (Third Party Unknown)
- Claimant's OD claim processed normally under comprehensive policy
- Solatium Fund (Government) covers TP injury/death if the vehicle is unidentified
- FIR mandatory

### 5.6 Third-Party Property Damage
- Cap: ₹7.5 Lakhs (IRDAI 2026 motor tariff)
- Settlement via Motor Accident Claims Tribunal (MACT) if contested
- **AI Rule:** TP property damage claims above ₹7.5L → flag for legal team; AI approves only up to ₹7.5L

---

## SECTION 6: SETTLEMENT TIMELINES (SLA)

| Claim Type | Target Settlement Time |
|---|---|
| Cashless (empaneled garage, < ₹50K) | 3–5 business days |
| Cashless (empaneled garage, > ₹50K) | 7–10 business days |
| Reimbursement (< ₹1L) | 10–15 business days |
| Reimbursement (> ₹1L) | 15–21 business days |
| Total Loss | 30 business days |
| Theft | 45–60 days (post FIR + 30-day wait) |
| Disputed / SIU Investigation | 90 days max |

**SLA Breach:** If settlement is delayed beyond the target, IRDAI mandates 9% per annum interest on the approved amount payable to the claimant.

---

## SECTION 7: AI PAYOUT COMPUTATION RULES

The Decision Agent must compute payout using the following sequence:

**Step 1:** Retrieve `idv` and `coverage_type` from DOC-003  
**Step 2:** Retrieve itemized parts list from DOC-005 (repair estimate)  
**Step 3:** Classify each part into depreciation category (Section 3)  
**Step 4:** Compute: `Part_Net_Cost = Part_Cost × (1 - Depreciation_Rate)`  
**Step 5:** Sum all net parts costs + labor (no depreciation on labor)  
**Step 6:** Check if sum > 75% of IDV → if yes, declare Total Loss (Section 2.3)  
**Step 7:** Subtract: Compulsory Deductible + Voluntary Deductible  
**Step 8:** Apply NCB reset flag if claim is approved  
**Step 9:** Output: `final_approved_amount`, `settlement_mode`, `ncb_reset`, `payout_breakdown`

**Hard Limit:** `final_approved_amount` must NEVER exceed IDV. If computed amount > IDV, cap at IDV.
