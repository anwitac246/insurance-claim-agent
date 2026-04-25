# POLICY DOCUMENT: POL-007
# GEOGRAPHIC COVERAGE, JURISDICTION & CATASTROPHE RULES
# SecureWheel Insurance Co. | Effective: April 1, 2026 | Version: 1.2

---

## SECTION 1: OVERVIEW

**Policy ID:** POL-007  
**Linked To:** POL-001, POL-003  
**Purpose:** Define the geographic boundaries of coverage, state-specific rules, catastrophe zone protocols, and international coverage conditions.

---

## SECTION 2: STANDARD GEOGRAPHIC COVERAGE

### 2.1 Standard Coverage Area
All SecureWheel motor policies cover the insured vehicle anywhere within the territorial boundaries of India, including:
- All 28 States and 8 Union Territories
- National Highways and State Highways
- Within city limits, rural roads, and private property
- **Included:** Lakshadweep, Andaman & Nicobar Islands, Daman & Diu (with island surcharge on premium)

### 2.2 Exclusions from Standard Coverage
- **International Territory:** Standard policy does NOT cover incidents outside India
- **Myanmar, Nepal, Bhutan border crossing:** Coverage extends to 50km across border ONLY with "SAARC Extension Endorsement" (charged separately)
- **Restricted Zones:** No coverage for incidents in militarized zones, active combat areas, or UN-designated conflict zones

### 2.3 State-Specific Premium Zones
IRDAI classifies Indian states into premium zones based on risk profile. This affects the base premium but NOT the coverage rules for claims.

| Zone | States/UTs | Risk Classification |
|---|---|---|
| Zone A (High Risk) | Maharashtra, Tamil Nadu, Karnataka, Delhi | Urban high-density; higher theft/accident rate |
| Zone B (Medium Risk) | Gujarat, Rajasthan, Telangana, West Bengal | Mixed urban-rural |
| Zone C (Low Risk) | Northeast states, J&K, Himachal Pradesh, Uttarakhand | Low density; higher natural calamity risk |

---

## SECTION 3: NATURAL CATASTROPHE PROTOCOLS

### 3.1 IRDAI Catastrophe Zone Declaration
When IRDAI formally declares a Catastrophe Zone (e.g., Chennai floods 2015, Kerala floods 2018):
- Fast-track settlement: All flood/cyclone claims from declared zone settled within 7 days
- Surveyor visit may be waived for claims < ₹1 Lakh in declared zones
- Self-declaration by claimant accepted with photographic evidence

### 3.2 Catastrophe-Specific Claim Rules

**Flood Claims:**
- Vehicle must have been parked legally (not abandoned illegally in a floodway)
- Engine damage (hydrostatic lock): COVERED only if engine was NOT started after water ingression
  - Evidence required: Workshop diagnosis confirming hydrostatic lock; engine inspection report
  - If engine was started: Claim REJECTED for engine damage (user negligence)
- Interior damage (seats, dashboard, electronics): COVERED up to IDV limit
- Recovery/towing from flood: COVERED if within 48 hours of incident

**Cyclone/Storm Claims:**
- Falling tree/debris damage: COVERED
- Damage while vehicle was in motion during storm warning: Potential exclusion; risk assessment required

**Earthquake Claims:**
- COVERED for all earthquake-related physical damage
- Must be in a seismically active zone verified by Geological Survey of India (GSI) records

**Hailstorm Claims:**
- COVERED; evidence = weather bureau data for the date and location
- AI Rule: Cross-check India Meteorological Department (IMD) data for hailstorm on claimed date and GPS location

### 3.3 Flood Hotspot Zones (High-Alert)
The following cities/regions have elevated flood-claim fraud rates. All flood claims from these areas require physical surveyor inspection regardless of claim amount:
- Mumbai (Kurla, Dharavi, Bandra lowlands)
- Chennai (Tambaram, Velachery)
- Kolkata (South Kolkata low-lying areas)
- Ahmedabad (Satellite, Chandkheda)
- Patna city center

**AI Rule:** If claimed GPS location falls within a flood hotspot zone AND claimed peril is flood → MANDATORY surveyor; do NOT fast-track

---

## SECTION 4: TRANSIT COVERAGE RULES

### 4.1 Vehicle in Transit
Coverage extends to damage while the insured vehicle is being transported by:
- Road transport (on a carrier/flatbed truck) — COVERED
- Railway (Rail auto carrier) — COVERED
- Inland waterway (ferry) — COVERED
- Air freight — COVERED (international transit excluded unless international endorsement active)
- Sea freight within Indian waters — COVERED

**Required Documents for Transit Claim:**
- Consignment note (LR — Lorry Receipt or Railway Receipt)
- Transit insurance policy if separate (for high-value vehicles)
- Surveyor report at destination confirming transit damage

### 4.2 Vehicle Being Driven to New Location
- A newly purchased vehicle being driven from dealer to home: COVERED from date of policy inception (dealer's transit insurance covers dealer-to-road handover)
- Vehicle being relocated by driver (>500km move): COVERED under standard policy with no special endorsement needed

---

## SECTION 5: STATE-SPECIFIC RULES & REGULATIONS

### 5.1 States with Mandatory PUC for Claims (All from April 2026)
All states now follow the IRDAI 2026 directive requiring valid PUC. Previously only these states enforced it:
- Maharashtra, Delhi, Karnataka, Tamil Nadu, Gujarat

### 5.2 States with E-Challan Integration
In states with e-Challan systems (MH, DL, KA, TN, GJ, UP):
- The AI system must check if the vehicle has any pending e-Challans related to traffic violations at the time of accident
- Pending challans do NOT void the claim but are flagged for record
- Challan for the specific violation that caused the accident (e.g., red-light jumping → collision) may trigger partial exclusion

### 5.3 High-Accident Districts (NCRB Blacklist)
The National Crime Records Bureau (NCRB) publishes annual high-accident district lists. Claims from these districts undergo enhanced scrutiny:
- Agra (NH-19 stretch), Rajsamand (Rajasthan), Kurnool (AP), Araria (Bihar)
- Enhanced scrutiny = mandatory FIR + independent surveyor for all claims > ₹25,000

---

## SECTION 6: INTERNATIONAL / SAARC EXTENSION

### 6.1 SAARC Countries Extension (Add-On: AO-SAARC)
Covers incidents in Nepal, Bhutan, Bangladesh, Sri Lanka (not Pakistan):
- Must be endorsed on policy before travel (minimum 7 days notice)
- Coverage limit: Same as Indian IDV; however, settlement in INR only
- Local garage reimbursement only (cashless not available abroad)
- FIR equivalent from local police + Indian Embassy attestation required
- **AI Rule:** If accident GPS shows international coordinates → Check for SAARC endorsement; reject if not present

---

## SECTION 7: AI GEOGRAPHIC VALIDATION RULES

```
RULE-G-001: Extract GPS coordinates from EXIF of accident photos
RULE-G-002: Verify GPS is within India (lat: 8.4°N to 37.6°N; lon: 68.7°E to 97.25°E)
RULE-G-003: If GPS outside India boundary AND no SAARC endorsement → REJECT (E-008)
RULE-G-004: Check claimed accident district against NCRB high-accident list → FLAG if match
RULE-G-005: Check claimed accident location against IRDAI catastrophe zone declarations for claim date
RULE-G-006: For flood claims, cross-check IMD weather data for location and date
RULE-G-007: If GPS within flood hotspot zone → Force mandatory surveyor; override fast-track
```
