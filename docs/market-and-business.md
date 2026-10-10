# Market and business

Condensed from `.claude/research/kapiling-market-2026-10-10.md` (date 2026-10-10, Philippines). Source tags like [S1] refer to the source list at the end. Anything labelled **ESTIMATE** is our own calculation, not a published figure. Conversions use PHP 58 per USD 1, an assumption implied by IDC's framing [S27], not a live rate.

## Problem evidence

- 11.42M Filipinos are aged 60+ (10.2% of the household population, up from 9.22M in 2020) [S1]. About 19.6% are projected to be 60+ by 2055 [S30].
- 69.1% of older Filipinos have hypertension; 51.5% of those are untreated (LSAHP 2018) [S5].
- Records for older persons are "fragmented, multiple sources, inaccessible" across 27 geriatric-centre hospitals [S9]. The national health information exchange is still a work in progress [S10].
- Out-of-pocket health spending was PHP 615.16B in 2024, about 43 to 44% of health spending [S12].
- Medication non-adherence among elderly hypertensive patients is 58 to 78% in local studies [S14][S14b].
- Not found: any Philippine study of repeat lab testing, of emergency information gaps, or of internet use by age 60+ (the only age figure found is 14% for ages 55+ in 2021 [S7]).

## Market size (all ESTIMATES)

Assumptions: PHP 99/month (PHP 1,188/year), set between KonsultaMD at PHP 60/month and Medisafe at about PHP 2,319/year [S23][S25]. 40% of seniors can use Kapiling on their own or a household phone (no direct source; reasoning: overall internet use is 67 to 84% [S4][S6], falls with age [S7], but 59% of seniors live with a child [S20]).

| Layer | Definition | Users | Arithmetic | PHP per year |
|---|---|---|---|---|
| TAM | All Filipinos aged 60+ | 11.42M | 11.42M x 1,188 | 13.57B (about USD 234M) |
| SAM | Reachable seniors with hypertension | 3.16M | 11.42M x 40% x 69.1% = 3,156,488; x 1,188 | 3.75B (about USD 65M) |
| SOM year 3 | 1% of SAM, 20% paying | 31.6k users, 6,313 payers | 3,156,488 x 1%; 6,313 x 1,188 | 7.5M |
| SOM year 5 | 3% of SAM, 20% paying | 94.7k users, 18,939 payers | 3,156,488 x 3%; 18,939 x 1,188 | 22.5M, before B2B2C |

Sub-segment: 11.42M x 18% (seniors relying on remittances from children abroad [S20]) is about 2.06M seniors with a child overseas; a proxy, not a counted figure. B2B2C: PHP 60 per senior per year across 94.7k users is about PHP 5.7M a year. For reference, published digital-health market sizes are USD 0.83B (Statista) to USD 2.82B (IMARC, broad eHealth) [S21][S22]; the research notes these are top-down and dominated by telehealth and insurers.

## Competitors

Every Philippine app found is cloud-based and mostly sells consultations: KonsultaMD (PHP 60/month) [S23], mWell [S40], HealthNow [S41], Medgate (PHP 999/year) [S42], SeriousMD (doctor-owned records) [S43], HiDok [S44], LiveFuller [S45], PhilHealth and eGovPH (ID wallet, available offline, strongest substitute for the card wallet) [S46][S47]. Hospital portals (St. Luke's, Medical City, Makati Medical) hold only their own results [S48][S49][S50]. Globally, Apple Health Records is not offered in the Philippines [S24], Google Health Connect is a platform [S26], and Medisafe (about PHP 2,319/year) is English-first reminders [S25]. Paper folders, camera rolls and Messenger groups are the real substitutes; no usage figures were found. No competitor found combines a Tagalog voice companion, offline AI, an intake-form filler and a family-PIN access log.

## Timing: 7/10

For: small open models now run offline in 2 to 3 GB of RAM [S28]; 22.5% of adults have used telehealth [S29]; health data is sensitive under RA 10173 [S31][S32]; the 60+ share is rising. Against: more than half of phones ship below USD 100 [S27]; willingness to pay is low (PHP 60 to 999 a year for telehealth comparables); software-as-medical-device rules are vague [S58]; eGovPH may absorb the ID-card part.

## SWOT

| Strengths | Weaknesses |
|---|---|
| Fully local AI: private, offline, near-zero inference cost | Heavy models for low-end phones |
| Tagalog voice, built for seniors and families | No backup or sync, so data-loss risk |
| Intake-form fill and QR emergency card | No clinical validation; hackathon-stage team |
| Family PIN with an access log | Hard to monetise without a cloud service |

| Opportunities | Threats |
|---|---|
| OFW children as payers (about 2.06M seniors, ESTIMATE) | eGovPH or PhilHealth adding records features |
| LGU, OSCA and YAKAP partners | Telcos bundling mWell or KonsultaMD |
| HMO adherence programmes | FDA reclassifying it as a medical device |
| Other ageing Southeast Asian markets | Apple or Google native health records |

## Business model

Seniors use Kapiling free. Paying customers are families and institutions. Unit economics below are **ESTIMATES**.

| Model | Price | Notes |
|---|---|---|
| Family plan | PHP 99/month | Paid family seats, backup and extra representatives. Net about PHP 84 after an assumed 15% store fee; at assumed 5% monthly churn, lifetime value is about PHP 1,680 (84 / 0.05); target acquisition cost up to PHP 550 |
| LGU / OSCA / YAKAP licence | PHP 50 to 100 per senior per year | A city with 20k enrolled seniors pays PHP 1 to 2M a year; sales cycle 6 to 12 months |
| HMO / pharmacy white label | PHP 5 to 15 per member per month | 10k members is PHP 0.6 to 1.8M a year; needs outcome data |
| Home box | At cost, plus PHP 149/month support | A household mini-PC for seniors whose phone cannot run the models (PHP 12 to 25k, unsourced estimate); doubles as the backup target |

Channels: LGUs and OSCA offices, PhilHealth YAKAP providers, HMOs, pharmacies (RA 9994 senior discounts [S52]), hospitals, OFW remittance points. Grants noted: DOST-PCHRD annual call [S55], DICT Startup Grant Fund up to PHP 1M [S56].

## Key risks

Software-as-a-medical-device classification (mitigation: stay a record keeper, fixed disclaimers, get a regulatory opinion before any HMO or hospital deal) [S58]; wrong auto-filled values (human confirmation of every extracted value); data loss on a lost device (planned encrypted export); phones too weak for the models (tiered models or the home box); government substitution (integrate rather than compete).

## Sources

- [S1] PSA, Age and Sex Distribution, 2024 POPCEN. https://psa.gov.ph/statistics/population-and-housing/node/1684083861
- [S4] DataReportal, Digital 2025: The Philippines. https://datareportal.com/reports/digital-2025-philippines
- [S5] PubMed 37379565, hypertension among older adults in the Philippines. https://pubmed.ncbi.nlm.nih.gov/37379565/
- [S6] PSA NICTHS 2024. https://psa.gov.ph/statistics/nicths/node/1684077807
- [S7] IJEAS / Univ. Malaya, citing Statista 2021. https://ijeas.um.edu.my/index.php/jati/article/download/5914/3630/13006
- [S9] Garcia et al., JMIR 2022. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8887638/
- [S10] Acta Medica Philippina, eHealth interoperability. https://actamedicaphilippina.upm.edu.ph/index.php/acta/article/view/3937
- [S12] P4H, out-of-pocket expenses. https://p4h.world/en/news/philippine-healthcare-families-drowning-in-out-of-pocket-expenses/
- [S14] Gutierrez and Sakulbumrungsil, systematic review. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8485436/
- [S14b] Ateneo de Zamboanga abstract. https://som.host.adzu.edu.ph/research/abstract.php?id=1267
- [S20] DRDF, LSAHP Wave 2 summary. https://www.drdf.org.ph/the-longitudinal-study-of-ageing-and-health-in-the-philippines-lsahp-wave-2-executive-summary1/
- [S21] Statista, Digital Health Philippines. https://www.statista.com/outlook/hmo/digital-health/philippines
- [S22] IMARC, Philippines eHealth Market. https://www.imarcgroup.com/philippines-ehealth-market
- [S23] KonsultaMD pricing (Rappler). https://www.rappler.com/?p=255138
- [S24] Apple, Health Records guide. https://register.apple.com/resources/ehr/Getting_Started_Guide.pdf
- [S25] Medisafe Premium cost. https://help-center.medisafe.com/en/articles/8102603-how-much-does-medisafe-premium-cost
- [S26] Android Health Connect PHR. https://developer.android.com/health-and-fitness/guides/personal-health-records/overview
- [S27] IDC via iConnect007, PH smartphone market 2024. https://mail.iconnect007.com/article/144034/philippines-smartphone-market-sees-continued-growth-for-the-second-consecutive-year-in-2024/144031/ein
- [S28] Gigazine, Gemma 3n release. https://wbgsv0a.gigazine.net/gsc_news/en/20250627-google-gemma-3n-full-release
- [S29] Standard Insights, telehealth in the Philippines. https://standard-insights.com/telehealth-in-the-philippines/
- [S30] PSA population projections. https://psa.gov.ph/sites/default/files/dhsd/Press%20Release%20CBPP.pdf
- [S31] NPC, FAQ on Circular 2023-06. https://privacy.gov.ph/wp-content/uploads/2024/12/v12-19-2024_FAQ-NPC-Circular-2023-06_NNJ_JDN.pdf
- [S32] DOH-NPC JMC 2020-0002. https://privacy.gov.ph/wp-content/uploads/2020/10/jmc2020-0002v1.pdf
- [S40] mWell (GadgetMatch). https://www.gadgetmatch.com/mwell-health-wellness-app-for-filipinos/
- [S41] OneNews, online consultation costs. https://www.onenews.ph/articles/how-much-does-it-cost-to-consult-a-doctor-online-5-telemedicine-websites-for-your-health-concerns-1
- [S42] Medgate pricing (same OneNews article as S41).
- [S43] SeriousMD. https://seriousmd.com/
- [S44] BusinessWorld, HiDok. https://www.bworldonline.com/?p=193760
- [S45] LiveFuller App Store. https://apps.apple.com/us/app/-/id1477695448
- [S46] PNA, e-PhilHealth. https://alpha.pna.gov.ph/articles/1228643
- [S47] FilipiKnow, eGovPH app guide. https://filipiknow.net/egovph-app-guide-2026-how-to-register-on-your-phone/
- [S48] St. Luke's eHealth Hub 2.0. https://www.stlukes.com.ph/news-and-events/news-and-press-release/access-your-health-at-your-fingertips-how-the-upgraded-st-lukes-ehealth-hub-20-app-keeps-up-with-your-fast-and-busy-lifestyle
- [S49] The Medical City South Luzon. https://themedicalcitysouthluzon.com/?p=1380
- [S50] Makati Medical Center. https://www.makatimed.net.ph/
- [S52] RA 9994 discounts (BatasNatin). https://batasnatin.com/laws/senior-citizens-20-percent-discount-vat-exemption
- [S55] DOST-PCHRD 2026 call. https://www.pchrd.dost.gov.ph/calls_and_events/2026-call-for-proposals-for-health-rd-for-2028-funding/
- [S56] DICT Startup Grant Fund (Newsbytes). https://newsbytes.ph/2022/11/22/dict-opens-application-for-startup-grant-fund-for-pinoy-startups/
- [S58] Chambers, Digital Healthcare 2022 Philippines. https://practiceguidesdev.chambers.com/practice-guides/digital-healthcare-2022/philippines/trends-and-developments
