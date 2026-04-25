# POLICY DOCUMENT: POL-005
# VEHICLE CLASSIFICATION, ELIGIBILITY & SPECIAL COVERAGE RULES
# SecureWheel Insurance Co. | Effective: April 1, 2026 | Version: 1.8

---

## SECTION 1: OVERVIEW

**Policy ID:** POL-005  
**Linked To:** POL-001, POL-002, POL-003  
**Purpose:** Define vehicle classification rules, coverage eligibility for each class, and special conditions for electric vehicles (EVs), commercial vehicles, vintage vehicles, and modified vehicles.

---

## SECTION 2: VEHICLE CLASSIFICATION MATRIX

### 2.1 Private Vehicles
| Sub-Class | Description | Policy Type Available | Max IDV |
|---|---|---|---|
| PC-001 | Private Car (Petrol/Diesel/CNG) | Comprehensive / TP / OD | As per IRDAI schedule |
| PC-002 | Private Car (Electric — BEV) | Comprehensive / TP / OD | Includes battery pack value |
| PC-003 | Private Car (Hybrid — PHEV) | Comprehensive / TP / OD | As per IRDAI schedule |
| TW-001 | Two-Wheeler (up to 150cc) | Comprehensive / TP | As per IRDAI schedule |
| TW-002 | Two-Wheeler (150cc–500cc) | Comprehensive / TP | As per IRDAI schedule |
| TW-003 | Two-Wheeler (above 500cc — Premium) | Comprehensive / TP | Special valuation required |
| QD-001 | Quadricycle | Comprehensive / TP | As per IRDAI schedule |

### 2.2 Commercial Vehicles
| Sub-Class | Description | Mandatory Extras |
|---|---|---|
| CV-001 | Goods Carrying (GCV) < 1 Ton | Commercial OD + TP + PA for owner-driver |
| CV-002 | Goods Carrying (GCV) 1–10 Ton | Commercial OD + TP + PA + Goods in Transit (optional) |
| CV-003 | Goods Carrying (GCV) > 10 Ton | Full commercial package; annual fitness certificate required |
| CV-004 | Passenger Carrying (PCV) — Taxi/Cab | Commercial TP mandatory; OD optional; Passenger PA mandatory |
| CV-005 | Passenger Carrying (PCV) — Bus | Commercial full package; vehicle fitness certificate + route permit required |
| CV-006 | Miscellaneous Vehicle (Tractor, Crane) | Special commercial policy; seasonal endorsement available |

### 2.3 Special Categories
| Sub-Class | Description | Special Conditions |
|---|---|---|
| SP-001 | Vintage/Classic Vehicle (> 30 years) | Agreed value policy; limited mileage endorsement; no standard IDV depreciation |
| SP-002 | Modified Vehicle (CNG kit, LPG, EV conversion) | Modification must be declared; ARC certificate required |
| SP-003 | Import/Foreign Vehicle | Customs clearance document required; IDV based on customs-assessed value |
| SP-004 | Agricultural Vehicle (Tractor, Harvester) | Seasonal policy available; field-use endorsement |

---

## SECTION 3: ELECTRIC VEHICLE (EV) SPECIAL RULES

### 3.1 EV-Specific Coverage Components
For Battery Electric Vehicles (BEV) under sub-class PC-002:

- **Battery Pack Coverage:**
  - Battery pack is covered as part of the vehicle IDV
  - Battery depreciation follows a separate schedule (lithium-ion degrades differently)
  - Battery replacement claim: Only claimable if damage is due to accident, not normal cycle degradation

- **EV Battery Depreciation Schedule:**
  | Battery Age | Depreciation Rate |
  |---|---|
  | Up to 1 year | 5% |
  | 1–2 years | 15% |
  | 2–3 years | 25% |
  | 3–4 years | 35% |
  | 4–5 years | 50% |
  | Beyond 5 years | 70% |

- **Charging Infrastructure Damage:** NOT covered under standard EV policy; requires a separate home charging add-on endorsement.

- **Range Anxiety Loss / Battery Failure (Non-Accident):** NOT covered. EV breakdown due to battery Management System (BMS) failure is a mechanical breakdown exclusion.

### 3.2 EV Charging Station Incident
- If EV is damaged while plugged into a public charging station:
  - Covered if damage is due to an external event (another vehicle hitting it, fire, flood)
  - NOT covered if damage is due to charging equipment malfunction (covered by charging station operator's liability)

### 3.3 EV Specific Documents Required
- Battery health certificate (SoH — State of Health, minimum 70% SoH for claim processing)
- OEM or certified service center diagnosis report for battery damage claims
- **AI Rule:** For EV claims involving battery, extract `battery_soh_percentage` from diagnostic report; if SoH < 70%, flag for physical inspection

---

## SECTION 4: CNG/LPG MODIFIED VEHICLE RULES

- CNG/LPG kit must be declared on the policy (endorsed)
- Undeclared CNG/LPG kit: Vehicle coverage is VOIDED for any explosion/fire claim originating from the kit
- Declared kit requires:
  - ARAI (Automotive Research Association of India) approval certificate
  - Explosion Proof Certificate from certified fitter
  - Annual fitness/safety check certificate
- **AI Rule:** If `fuel_type = "CNG"` on RC but no CNG endorsement on policy → FLAG: COVERAGE VOID for fire/explosion claims; OD from collision still valid

---

## SECTION 5: COMMERCIAL VEHICLE SPECIAL CONDITIONS

### 5.1 Permit & Fitness Certificate
- All commercial vehicles (CV-001 to CV-006) must have a valid:
  - **Fitness Certificate (FC):** Issued by RTO; certifies vehicle is roadworthy
  - **Route Permit:** For PCV/GCV operating on specific routes
  - **Goods Permit:** For GCV carrying specific types of goods (hazardous, overweight, etc.)
- If Fitness Certificate is expired at date of accident → Claim is REJECTED (vehicle deemed unroadworthy)
- **AI Rule:** Extract `fitness_certificate_expiry` from commercial RC; compare to accident date

### 5.2 Driver Requirements for Commercial Vehicles
- GCV above 7.5 Ton: Driver must hold a Heavy Motor Vehicle (HMV) license
- PCV (Taxi): Driver must hold a Commercial Vehicle endorsement on DL
- Dangerous Goods Carrier: Driver must hold HAZMAT training certificate
- **AI Rule:** For CV claims, check DL class specifically against vehicle sub-class

### 5.3 Overloading Exclusion
- If vehicle was carrying load exceeding its Registered Carrying Capacity (RCC) at time of accident:
  - OD claim: REJECTED due to overloading exclusion
  - TP claim: STILL VALID (IRDAI mandates TP coverage regardless)
  - **AI Rule:** Flag overloading claims from accident report; reject OD, proceed TP only

---

## SECTION 6: VINTAGE VEHICLE (SP-001) SPECIAL RULES

- Vintage vehicles (manufactured before April 1996) are insured at **Agreed Value** (not IDV)
- Agreed Value is set mutually at policy inception based on certified valuation
- Claim payout = Agreed Value (no depreciation applied; no IDV schedule)
- Vintage vehicles cannot be enrolled in cashless cashless track; reimbursement only
- Condition: Vehicle must be kept in roadworthy condition with annual vintage club certification
- **AI Rule:** If RC manufacture year < 1996 → Apply SP-001 rules; do not apply standard IDV depreciation

---

## SECTION 7: ADD-ON COVERAGE ENDORSEMENTS

These optional add-ons must be verified on the Policy Schedule (DOC-003) before approving related claims:

| Add-On Code | Name | What it Covers |
|---|---|---|
| AO-001 | Zero Depreciation (Bumper-to-Bumper) | Nil depreciation on all parts; no deduction for age |
| AO-002 | Engine Protection Cover | Engine damage due to water ingression / oil leakage |
| AO-003 | Return to Invoice (RTI) | Total loss payout = original invoice value (not IDV) |
| AO-004 | Roadside Assistance (RSA) | Towing, fuel delivery, flat tyre, battery jumpstart |
| AO-005 | Personal Accident Cover — Passengers | PA cover for all passengers (up to ₹2L per person) |
| AO-006 | Consumables Cover | Covers cost of nuts, bolts, engine oil, coolant, etc. |
| AO-007 | Key & Lock Replacement | Covers cost of replacing lost/stolen vehicle keys |
| AO-008 | Tyre Protection | Covers tyre damage without requiring other vehicle damage |
| AO-009 | NCB Protect | Allows one claim per year without NCB reset |
| AO-010 | Invoice Gap Cover | Covers difference between IDV and loan outstanding |

**AI Rule:** For each claim item, check if related add-on is active on policy before applying standard exclusion. Example: Tyre damage normally excluded (E-010) → COVERED if AO-008 is active.

---

## SECTION 8: VEHICLE ELIGIBILITY VERIFICATION CHECKLIST

The Document Agent must verify ALL of the following before clearing DOC-001 (RC):

```
✓ RC is not expired
✓ RC owner name matches policy name (or transfer endorsement exists)  
✓ Engine number matches (last 5 digits)
✓ Chassis number matches (last 5 digits)
✓ Vehicle class on RC is insured class on policy
✓ Fuel type on RC matches policy (flag if CNG on RC but petrol on policy)
✓ For commercial vehicles: Fitness Certificate validity checked
✓ For EV: Battery capacity (kWh) matches policy schedule
✓ For vintage (pre-1996): Flag for SP-001 special rules
✓ For modified vehicles: Endorsement present on policy
```

Any failure = FLAG with specific reason; do not auto-reject unless it's a hard mismatch (engine/chassis number).
