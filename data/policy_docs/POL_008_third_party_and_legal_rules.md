# POLICY DOCUMENT: POL-008
# THIRD-PARTY LIABILITY, LEGAL PROCEEDINGS & PA COVER RULES
# SecureWheel Insurance Co. | Effective: April 1, 2026 | Version: 1.3

---

## SECTION 1: OVERVIEW

**Policy ID:** POL-008  
**Linked To:** POL-001, POL-003  
**Purpose:** Define rules for third-party (TP) liability claims, Motor Accident Claims Tribunal (MACT) proceedings, personal accident (PA) cover, and the handling of death/injury compensation.

---

## SECTION 2: THIRD-PARTY BODILY INJURY & DEATH

### 2.1 Coverage Basis
Per the Motor Vehicles Act, 1988 (amended 2019) and IRDAI 2026 tariff:
- Liability for third-party bodily injury or death is UNLIMITED in amount
- SecureWheel is liable up to the awarded amount by MACT (Motor Accident Claims Tribunal)
- Structured compensation formula used by courts:

**Compensation for Death:**
```
Compensation = (Annual Income × Multiplier) + Funeral Expenses (₹15,000 fixed) + 
               Loss of Estate (₹15,000 fixed) + Spousal Consortium (if applicable)
```

**Multiplier Table (based on age of deceased at time of accident):**
| Age of Deceased | Multiplier |
|---|---|
| Up to 15 years | 15 |
| 15–25 years | 18 |
| 26–30 years | 17 |
| 31–35 years | 16 |
| 36–40 years | 15 |
| 41–45 years | 14 |
| 46–50 years | 13 |
| 51–55 years | 11 |
| 56–60 years | 9 |
| 61–65 years | 7 |
| Above 65 years | 5 |

### 2.2 Hit-and-Run Compensation (Solatium Fund)
If the vehicle responsible is not identified (hit-and-run):
- Death: ₹2,00,000 (2 Lakhs) from Solatium Fund (Government)
- Grievous injury: ₹50,000 from Solatium Fund
- Claim filed with: Claim Inquiry Officer of the Motor Accident Claims Tribunal
- SecureWheel's TP policy does NOT cover hit-and-run by a third unknown vehicle; this is handled by Solatium Fund

### 2.3 AI Rules for TP Bodily Injury/Death Claims
```
RULE-TP-001: Always flag TP death/injury claims for human legal team; AI does NOT make final decisions
RULE-TP-002: Verify FIR is present and registered for all TP injury/death claims
RULE-TP-003: Compute preliminary compensation estimate using above formula for informational purposes only
RULE-TP-004: Check if driver was legally licensed for vehicle class; if not, subrogation rights against insured activated
RULE-TP-005: Notify legal team within 1 business day of any TP death claim
```

---

## SECTION 3: THIRD-PARTY PROPERTY DAMAGE

### 3.1 Coverage Cap
- Maximum TP property damage coverage: ₹7,50,000 (7.5 Lakhs) per IRDAI 2026
- If awarded damages exceed ₹7.5 Lakhs: SecureWheel pays up to ₹7.5L; balance is the insured's personal liability

### 3.2 TP Property Damage Claim Process
- Claimant (the TP, not policyholder) files claim via SecureWheel portal or at nearest branch
- FIR mandatory if damage > ₹50,000
- Independent surveyor assesses TP property damage
- If not contested: Settled directly
- If contested: Referred to MACT

### 3.3 Common TP Property Damage Scenarios
- Damage to another parked vehicle: Standard TP claim
- Damage to a building/shop/wall: Standard TP claim with property photos
- Damage to government property (road dividers, signals): FIR mandatory; PWD assessment report required
- Damage to crop/agriculture: Revenue department assessment required

---

## SECTION 4: PERSONAL ACCIDENT (PA) COVER

### 4.1 Compulsory PA Cover for Owner-Driver
Per IRDAI mandate (Motor Vehicles Act Section 147):
- Every motor policy must include mandatory PA cover for the owner-driver
- Coverage: ₹15,00,000 (15 Lakhs) for death or permanent total disability
- This is separate from the vehicle OD/TP coverage
- Premium: ₹750/year (fixed IRDAI rate for 2026)

### 4.2 PA Compensation Scale (Owner-Driver)
| Nature of Injury | Compensation (% of ₹15L Sum Insured) |
|---|---|
| Death | 100% (₹15,00,000) |
| Loss of two limbs or two eyes or one limb and one eye | 100% |
| Loss of one limb or one eye | 50% (₹7,50,000) |
| Permanent total disability from injuries other than above | 100% |

### 4.3 Optional PA Cover for Passengers (Add-On AO-005)
If AO-005 is active on the policy:
- Each passenger covered up to ₹2,00,000 (2 Lakhs) for death/PTD
- Maximum 6 passengers (or vehicle seating capacity as per RC, whichever is lower)
- Named passenger cover available for higher sums insured

### 4.4 PA Cover Exclusions
PA cover does NOT apply if:
- The insured was under the influence of alcohol/drugs (E-001)
- The accident was caused by willful self-injury or suicide
- The accident occurred while the vehicle was used for criminal purposes
- The insured was not the driver (PA covers owner-driver role specifically; unless AO-005 for passengers)

### 4.5 PA Claim Documents
- Death Certificate (from municipal corporation) — for death claims
- Post-mortem report — if accident-related death
- Medical reports (MRI, X-Ray, hospital discharge summary) — for disability claims
- Disability certificate from government-recognized medical board — for PTD claims
- **AI Rule:** PA claims require separate claim form (PA Form PA-2026); verify form type

---

## SECTION 5: LEGAL PROCEEDINGS & SUBROGATION

### 5.1 SecureWheel's Right of Subrogation
After settling a claim, SecureWheel has the legal right to recover the paid amount from the at-fault third party.

Subrogation scenarios:
- Insured's vehicle was hit by a third party: SecureWheel pays claim, then pursues TP for recovery
- Insured was drunk driving: SecureWheel may pay TP claim first (legal obligation) then recover from insured
- Insured DL was invalid: Same as drunk driving — pay TP, recover from insured

### 5.2 MACT Proceedings
When a claim goes to MACT (Motor Accident Claims Tribunal):
- SecureWheel's legal team represents the company
- All claim documents, policy details, and FIR must be submitted to tribunal
- AI system must generate a comprehensive claim dossier for legal team use
- Timeline: MACT proceedings may take 6 months to 3 years

### 5.3 Out-of-Court Settlement
For TP property damage below ₹2 Lakhs:
- Both parties may agree to out-of-court settlement
- SecureWheel facilitates but requires written consent from TP claimant
- Out-of-court settlement voids future claims on same incident

---

## SECTION 6: PREMIUM RECOVERY FOR FRAUDULENT CLAIMS

If a claim was paid and later found to be fraudulent:
- SecureWheel has the right to recover 100% of the paid amount + 18% GST + investigation costs
- Legal action under IPC Section 420 (Cheating) and Section 468 (Forgery for Cheating)
- Policy cancelled with permanent blacklisting on IIB registry
- **AI Rule:** All fraud recoveries logged to Pinecone `fraud_recoveries` namespace for future pattern training
