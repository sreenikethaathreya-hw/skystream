"""Body of the design document. Kept separate from the rendering helpers in build_docx.py."""

from datetime import date
from pathlib import Path

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

LIVE_URL = "https://skystream-510015.web.app"
RUN_URL = "https://skystream-api-842137351485.us-central1.run.app"


def build(doc, figures: dict[str, Path], shots: Path, ledger_shot: Path, segments: list, competitors: list,
          report: dict, today: date) -> None:
    title_page(doc, today)
    doc.toc()
    doc.page_break()
    executive_summary(doc)
    problems(doc)
    scope(doc, segments, competitors)
    doc.page_break()
    users(doc)
    walkthrough(doc, shots, ledger_shot)
    doc.page_break()
    flow(doc, figures)
    doc.page_break()
    architecture(doc, figures)
    calculations(doc)
    flags(doc)
    ai(doc, figures)
    doc.page_break()
    data_sources(doc, report)
    data_elements(doc, figures)
    unused_elements(doc)
    data_quality(doc, report)
    synthetic(doc)
    derived(doc)
    doc.page_break()
    data_model(doc)
    api(doc)
    deployment(doc)
    testing(doc)
    limits(doc)
    glossary(doc)


def title_page(doc, today: date) -> None:
    for _ in range(6):
        doc.d.add_paragraph()
    title = doc.d.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Defensible Demand Ledger")
    run.bold = True
    run.font.size = Pt(30)
    run.font.color.rgb = RGBColor(0x1A, 0x5C, 0x31)
    sub = doc.d.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run("Use Case 2: Market Intelligence and Demand Capture\nApplication, User Interaction and Data Design")
    run.font.size = Pt(15)
    for _ in range(3):
        doc.d.add_paragraph()
    meta = doc.d.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        f"Locked scope: Spain > Sweet Pepper > Blocky PGH (passive greenhouse)\n"
        f"Live demo: {LIVE_URL}\n"
        f"Repository: skystream (backend/, packages/web/, scripts/ingest/)\n"
        f"Document date: {today:%d %B %Y}\n\n"
        "SMEs: Abhijeet Chaudhry, Leticia Dias"
    ).font.size = Pt(11)
    doc.page_break()


def executive_summary(doc) -> None:
    doc.h("1. Executive summary")
    doc.p(
        "The Defensible Demand Ledger is a working demand-capture tool for one locked crop and geography: "
        "**Spain > Sweet Pepper > Blocky greenhouse pepper (Blocky PGH)**, nine active micro-segments. A sales rep "
        "enters a monthly demand number and, while typing, sees what it does to market share, to the year-to-go "
        "position and to the hectares it implies. Deterministic rules flag implausible entries against history. "
        "The rep's one-sentence justification is turned into a structured, checkable claim by the **Jev** decision "
        "model. When the month closes the claim is checked against actual sales, which builds a per-rep track "
        "record. The consensus meeting then only reviews the exceptions, and approved numbers leave the tool as a "
        "low / mid / high supply range."
    )
    doc.p("What the app delivers against the success criteria in the brief:")
    doc.table(
        ["Success criterion (brief)", "How the app meets it"],
        [
            ["Rep enters a demand number for one locked crop and geography",
             "Scope is fixed in the data (9 Blocky PGH micro-segments in Spain) and shown as a locked badge in the header."],
            ["Immediately sees market-share impact",
             "Share tile recalculates in the browser on every keystroke (< 1 ms): volume share, value share, range, change vs plan and last year, and the competitor split."],
            ["Year-to-go impact", "Year-to-go tile: full-year estimate, gap to plan, needed vs entered vs last-year monthly rate."],
            ["Implausibility flag against history", "Eight deterministic rules (plus a data-quality rule) with plain-language messages; any flag makes the justification mandatory."],
            ["One-sentence justification becomes structured reasoning",
             "Jev returns ten typed decisions with probabilities (driver, direction, size, competitor, variety, evidence, specificity, checkable, fits market notes, explains flags)."],
            ["Live entry, live recalculation, no next-day lag", "All impact math runs client-side; the server recomputes the same math on submit; structuring takes about 0.3 s."],
            ["Stretch: consensus assistant drafts reasons-to-believe", "Gemini drafts the RTB from confirmed claims, market notes and competitor trends only."],
        ],
        widths=[5.5, 11.5],
        caption="Success criteria and how they are met",
    )
    doc.p(
        "Beyond the brief, the app adds the **Defensible Demand Ledger** ideas: a volume-versus-price split with a "
        "'price is carrying this number' flag, a rep-supplied confidence range that feeds supply planning, claims "
        "that are resolved against later data, a per-rep track record, and an exceptions-only consensus queue."
    )


def problems(doc) -> None:
    doc.h("2. Business problems and how the application solves them")
    doc.p(
        "Today reps update demand in disconnected spreadsheets and a homegrown SharePoint application (i-MAPS). "
        "The sample exports come from three separate lists on that site: **MAPSHistData** (market), "
        "**Syngenta5YrsSales** (Syngenta plan) and **CompetitorMktShare** (competitors). Nothing links them at "
        "entry time, so share is not recalculated until a later refresh."
    )
    rows = [
        ["1. Next-day lag; no real-time feedback",
         "Three unconnected lists; share recalculated later.",
         "Market, plan, competitor and monthly data are joined once into a 'cube' and sent to the browser; demandMath.ts recalculates every tile per keystroke with no network call.",
         "Capture screen tiles"],
        ["2. A number cannot be defended during the conversation",
         "Rep has no view of share, hectares or year-to-go while talking to a customer.",
         "Four live tiles (share + competitor split, year-to-go, implied hectares, plausibility) plus a revenue split, all updating as the number changes.",
         "Capture screen"],
        ["3. No validation against history",
         "Implausible numbers flow into the plan unchecked.",
         "Eight deterministic flags (share > 100%, share above history, hectares above market, month outlier, against market trend, price carrying, above grower potential, range too wide, price outside band). Flags never block; they make the justification mandatory.",
         "Plausibility tile, Ledger, Consensus"],
        ["4. Revenue plan silently depends on price",
         "In the sample plan, Blocky PGH revenue stays flat while volume and share fall; price makes up the gap.",
         "Volume/price decomposition of every number vs last year and a 'price is carrying this number' flag when volume falls and price supplies at least 70% of the revenue movement.",
         "Revenue split card, flag"],
        ["5. Single-point numbers drive seed production committed a year or more ahead",
         "Over-forecast leads to write-offs; under-forecast to lost sales.",
         "Rep supplies a low/high range; tiles show both ends; the supply export marks low-confidence lines (wide range or weak rep) as 'build to low'.",
         "Entry panel, Supply CSV"],
        ["6. Reasons are lost as free text; no record of why a number changed",
         "Justifications live in comment cells ('80% of this microsegment').",
         "Jev structures the sentence into typed fields with probabilities; each entry stores number, range, impact snapshot, flags and claim; earlier entries are superseded, not deleted.",
         "Justification box, Ledger"],
        ["7. No way to know whose numbers to trust",
         "Bias and accuracy per rep are invisible.",
         "When a month closes, each claim is resolved against actuals (numeric check + Jev yes/no verdict). Track record = claim hit rate, bias, range coverage; shown next to new entries and used by the consensus queue.",
         "Track record screen, Advance month"],
        ["8. Consensus meetings discuss every line",
         "Time spent on routine numbers.",
         "Exceptions-only queue (flags, weak rep, vague or flag-ignoring justification) with a Jev triage suggestion; routine lines approved in bulk; Gemini drafts the reasons-to-believe.",
         "Consensus screen"],
        ["9. Source data quality",
         "Duplicates, renamed segments, missing IDs, noisy CRM rows.",
         "Ingest pipeline deduplicates, joins on IDs, recovers IDs from descriptions, caps outliers, anonymizes, and publishes a data-quality report.",
         "Data quality screen"],
        ["10. Constraints: synthetic sales, public data only, no production access, no forecasting model",
         "Brief non-negotiables.",
         "Syngenta figures scaled + noised; rep names pseudonymized; everything loaded from files; every number comes from the rep - the app calculates, checks and records only.",
         "Whole design"],
    ]
    doc.table(["Problem", "Evidence / cause", "How the app solves it", "Where"], rows, widths=[3.4, 3.6, 7.4, 2.6],
              size=8, caption="Problem-to-solution map")


def scope(doc, segments: list, competitors: list) -> None:
    doc.h("3. Scope, constraints and the locked segment")
    doc.h("3.1 Why Spain > Sweet Pepper > Blocky PGH", 2)
    doc.bullets([
        "Sweet pepper is Syngenta's largest line in the Spain sample (about EUR 28.8M of 2026 plan sales before anonymization).",
        "Blocky PGH is the mega-segment where Syngenta leads (about 31% value share in the competitor file, reconciled exactly by the app's own calculation).",
        "It has the richest supporting material: rep comments, six market-note fields, a full competitor split, CRM grower rows with Syngenta varieties, and a clear market driver (the T. parvispinus pest).",
        "The market and sales data are national (no province split), so the locked geography is Spain; Almeria appears only as context in comments and grower regions.",
    ])
    doc.h("3.2 The nine active micro-segments (2026, anonymized plan)", 2)
    doc.table(
        ["ID", "Cycle / colour", "Owner", "Planted ha", "Area vs 2025", "Density (k/ha)", "Market KS", "Ex-seed EUR/KS",
         "Plan KS", "Vol. share"],
        segments, size=7.5, caption="Locked micro-segments (market from MV360 Market, plan from MV360 Sales, anonymized)",
    )
    doc.p("Nine further Blocky PGH micro-segments exist in the hierarchy (2429-2431, 2441, 2442, 2445, 2447, 2485, "
          "2486) but have no 2026 market area, so they are excluded from capture.", size=9.5)
    doc.h("3.3 Competitive landscape used by the app (2026)", 2)
    doc.table(["Competitor", "Value share", "Value", "Trend"], competitors, widths=[5, 3, 3.5, 3], size=8.5,
              caption="Blocky PGH competitor shares (Syngenta share recomputed from anonymized sales; others rescaled)")
    doc.h("3.4 Constraints honoured", 2)
    doc.bullets([
        "**No forecasting model.** Every number and every range comes from the rep. The app only calculates, checks, records and summarizes.",
        "**Synthetic sales.** Syngenta quantities and values are multiplied by one hidden factor with 3% per-row noise; rep names are replaced by Rep A / Rep B.",
        "**No live systems.** All data is loaded from the supplied spreadsheets; monthly layers are synthetic.",
        "**Public sources only.** No scraping. Spain's agriculture ministry statistics (MAPA/ESYRCE) are named as the outside check for hectares but not fetched.",
        "**Out of scope.** Territory and geographic roll-up, other crops and countries, treatment of FPI launches in share (open SME question).",
    ])


def users(doc) -> None:
    doc.h("4. Users, roles and permissions")
    doc.p("The demo uses a role switcher in the header instead of sign-in (the backend reads an X-Demo-User header). "
          "Real authentication (for example Firebase Auth) must replace it before any real data is used.")
    doc.table(
        ["User", "Role", "Owns", "Can do"],
        [
            ["Rep A", "Sales rep (autumn cycles)", "2481, 2482, 2483, 2484",
             "View all segments; submit demand only for owned segments and open months; structure justifications; see own track record."],
            ["Rep B", "Sales rep (early and spring cycles)", "2432, 2433, 2446, 2448, 2449", "Same as Rep A for owned segments."],
            ["Consensus lead", "Product specialist", "-",
             "See the exceptions queue; approve / discuss / challenge; bulk-approve routine lines; draft RTB; export the supply CSV."],
            ["Anyone (demo)", "-", "-", "Advance the demo month; reset demo data; view Ledger, Track record and Data quality."],
        ],
        widths=[2.6, 3.6, 3.6, 7.2], caption="Roles",
    )
    doc.p("Server-side rules enforced regardless of the UI: only the owning rep can submit for a segment (403 otherwise); "
          "closed months (before the demo clock) are rejected (400); a flagged entry without a justification is rejected "
          "(422); low <= value <= high is validated; only the consensus lead can approve or bulk-approve (403).")


def walkthrough(doc, shots: Path, ledger_shot: Path) -> None:
    doc.h("5. How a user interacts with the application")
    doc.p(f"Open {LIVE_URL}. The header shows the locked scope, the AI status (Jev live / Gemini on), the demo clock "
          "(starts at September 2026), the Advance month and Reset buttons, and the Acting as selector. Navigation "
          "tabs below the header adapt to the role: reps see Capture; the lead sees Consensus.")

    doc.h("5.1 Capture (sales rep)", 2)
    doc.image(shots / "01-baseline.png", "Capture screen for micro-segment 2482 at the plan number")
    doc.p("**Left column.** The micro-segment list puts the rep's own segments first with their plan volume and "
          "volume share; other reps' segments are view-only. Below it, the rep's own track record (claims right, bias, "
          "actuals inside range) is always visible.")
    doc.p("**Segment header.** Label, full hierarchy description and the rep comment from the plan (for 2482: "
          "\"Syngenta leader of the red BP. 40% MS of the whole market and 80% of this microsegment...\").")
    doc.p("**Month grid.** Twelve columns with four rows: Plan (synthetic monthly split), Last year, Actual (only "
          "for closed months) and Demand (latest submitted entry, or the live draft for the selected month). Closed "
          "months are greyed and cannot be selected; the selected open month is highlighted.")
    doc.p("**Entry panel.** The demand number in thousand seeds (KS), a two-slider confidence range (low and high "
          "percentages, default -8% / +8%) and an optional net price in EUR/KS (defaults to the plan net price).")
    doc.p("**Live tiles** (recomputed on every keystroke, no server call):")
    doc.bullets([
        "**Market share**: full-year volume share with low-high range, change vs plan and vs last year, value share, Blocky PGH mega-segment value share and the three competitors that lose most when Syngenta gains.",
        "**Year to go**: gap to plan (green above, red below), full-year estimate, plan, actuals to date, and the monthly run rate needed vs entered vs last year for the open months.",
        "**Implied hectares**: full-year volume divided by plant density, a bar against the planted hectares of the segment, and the range.",
        "**Plausibility**: 'No flags' or each flag as a plain-language message; any flag switches the justification to required.",
        "**Where the revenue change comes from**: volume effect and price effect vs last year as signed bars, with average price now vs last year.",
    ])
    doc.image(shots / "02-flags.png", "Typing 40,000 KS: share above 100%, hectares above the market and a month outlier fire; submit is blocked until a justification exists")
    doc.p("**Justification.** The rep writes one sentence and clicks **Structure with Jev**. The claim summary and ten "
          "decision cards appear, each with its probability bar. Warnings appear when a field is low-confidence or "
          "when Jev judges that the sentence does not explain the flags. If the numbers change after structuring, the "
          "result is marked stale and re-run on submit.")
    doc.image(shots / "03-structured-claim.png", "14,500 KS with a justification structured by Jev; the price-carrying warning remains visible")
    doc.p("**Submit.** The server recomputes the math, stores the entry with its impact snapshot, flags and claim, "
          "supersedes the previous entry for the same segment and month, and shows a confirmation toast naming the "
          "month the claim will be checked against. Gemini rewrites the claim summary in the background.")

    doc.h("5.2 Consensus (consensus lead)", 2)
    doc.image(shots / "prod-04-consensus.png", "Exceptions-only queue with Jev triage and a Gemini-drafted reasons-to-believe (production)")
    doc.bullets([
        "**Exceptions** list every open entry that has at least one reason: a flag message, a rep with a weak track record (claim hit rate < 60% or |bias| > 10%), a vague justification (specificity < 1.5 of 3) or one that does not explain its flags (Jev < 0.5), or an earlier Discuss/Challenge status.",
        "Each exception shows the full entry card, a 'Why this is on the agenda' box and **Jev suggests** approve / discuss / challenge with a confidence bar, plus Approve / Discuss / Challenge buttons.",
        "**Routine entries** (no reasons) are listed on the right with one **Bulk approve routine** button.",
        "**Reasons to believe**: pick a segment and click Draft RTB. Gemini writes the narrative from confirmed claims, market facts, competitor trends and the market-dynamics note; without Gemini a structured template is used. The number of cited claims is shown.",
        "**Supply handoff**: Export supply range CSV downloads approved lines with low / mid / high, build_to (low for wide ranges or weak reps, otherwise mid), build_ks, rep and reason.",
    ])

    doc.h("5.3 Advance month", 2)
    doc.p("The header button closes the current month: the synthetic actuals for that month become visible, every "
          "pending claim due that month is resolved (numeric check plus Jev yes/no verdict), track records are "
          "recomputed, the clock moves forward, and a toast summarises confirmed / contradicted / inconclusive claims. "
          "Reset restores the seed (clock back to September 2026, 38 historical entries).")

    doc.h("5.4 Ledger", 2)
    doc.image(ledger_shot, "Ledger: every entry with impact snapshot, flags, claim tags and resolution against actuals")
    doc.p("A newest-first timeline filterable by segment and rep. Each card shows value and range, full-year estimate "
          "and share at the time of entry, the justification, the claim summary, flag badges, compact claim tags, and "
          "either 'Will be checked against <month> <signal>' or 'Resolved against actuals: X vs plan Y, inside/outside "
          "range, evidence supports the claim with p% probability (provider)'. History entries are labelled.")

    doc.h("5.5 Track record", 2)
    doc.image(shots / "06-track-record.png", "Track record per rep with the latest resolved claims")
    doc.p("Per rep: claims confirmed (hit rate), bias (average of (entry - actual) / actual), actual inside range "
          "(coverage), confirmed/contradicted counts, a Reliable or Weak badge, and the latest resolved claims. "
          "Seeded history: Rep A 83% hit rate, +1% bias, 89% coverage (reliable); Rep B 40%, +13%, 10% (weak).")

    doc.h("5.6 Data quality", 2)
    doc.image(shots / "07-data-quality.png", "Data quality report produced by the ingest")
    doc.p("One card per source (sales, market, competitors, grower, hierarchy, geo) plus scope, anonymization and "
          "synthetic layers, listing what the ingest found and fixed. Section 12 details every figure.")


def flow(doc, figures: dict[str, Path]) -> None:
    doc.h("6. End-to-end flow")
    doc.image(figures["user_flow"], "User flow across rep, application/AI and consensus lead", width_cm=16.5)
    doc.h("6.1 Step-by-step", 2)
    doc.numbered([
        "Rep selects an owned micro-segment and an open month (the demo clock marks earlier months as closed).",
        "Rep types the demand in KS, adjusts the low/high range and optionally a net price.",
        "The browser recalculates share, competitor split, year-to-go, implied hectares, the revenue split and all flags on each keystroke.",
        "If any flag fires, the justification becomes mandatory; otherwise it is optional but recommended.",
        "Rep writes one sentence and structures it: the backend sends one fan-out call to Jev with 9-10 typed questions; Gemini is consulted only for Choice answers under 0.8 confidence.",
        "Rep reviews the tags and probabilities, refines the sentence if needed, and submits.",
        "The server re-validates ownership, month, range and justification, recomputes the math, stores entry + impact + flags + claim, supersedes the previous entry, and schedules a Gemini summary rewrite.",
        "The consensus lead sees exceptions with reasons and a Jev triage suggestion and decides; routine lines are bulk-approved.",
        "The lead drafts the reasons-to-believe (Gemini) and exports the supply range CSV.",
        "Advance month reveals actuals and resolves due claims (numeric check + Jev verdict).",
        "Track records are recomputed.",
        "The rep's track record is shown next to the next entry, and weak records route future entries to consensus.",
    ])
    doc.h("6.2 Demo script (about 6 minutes)", 2)
    doc.numbered([
        "Capture as Rep A, segment 2482 (Autumn late Red), September: baseline tiles at the plan number.",
        "Type 40000: share above 100%, hectares above the 3,316 ha market, month outlier; submit disabled.",
        "Type 14500 and write 'Two Almeria cooperatives are switching from Sur Seeds to Leontes because of T. parvispinus tolerance.' Structure with Jev and show the probabilities. The price-carrying warning stays - volume is below last year and price holds revenue up.",
        "Submit; submit a clean line (2484 at plan); switch to Rep B and submit 2432 for October with a vague sentence.",
        "Switch to the Consensus lead: only two exceptions (2482 price carrying; 2432 weak rep + vague). Bulk-approve 2484, approve the rest, Draft RTB for 2482, export the CSV.",
        "Advance month: September claims resolve; Ledger shows 'Resolved against actuals'; Track record updates.",
        "Finish on Data quality to show the ingest rigour.",
    ])


def architecture(doc, figures: dict[str, Path]) -> None:
    doc.h("7. Architecture")
    doc.image(figures["architecture"], "System architecture", width_cm=17)
    doc.h("7.1 Components", 2)
    doc.table(
        ["Layer", "Technology", "Responsibility"],
        [
            ["Ingest", "Python, pandas (scripts/ingest)", "Read the six workbooks, clean, join on IDs, anonymize, synthesize monthly data and rep history, write data/seed/*.json and ingest_report.json."],
            ["Frontend", "React 19, Vite 8, TypeScript, TanStack Query, Tailwind v4, lucide icons", "Screens, role switcher, demo controls; demandMath.ts and flags.ts compute impacts per keystroke."],
            ["API", "FastAPI, Pydantic (camelCase DTOs), uvicorn", "Thin routers; services hold logic; same math re-run server-side on submit."],
            ["Persistence", "SQLAlchemy 2 async, Alembic, SQLite (demo) / Postgres (docker-compose)", "Reference tables, entries, claims, track records, demo clock."],
            ["AI", "DecisionProvider; httpx Jev client; google-genai Vertex client", "Jev for typed decisions; Gemini for prose and low-confidence fallback; fixtures and offline decider for resilience."],
            ["Hosting", "Cloud Run (API + bundled SPA), Firebase Hosting (SPA + /api rewrite)", "Single service, max one instance; SQLite reseeded on cold start."],
            ["Secrets / IAM", "Secret Manager, service account skystream-api", "JEV_API_KEY from secret jev-api-key; roles/aiplatform.user for Vertex."],
        ],
        widths=[2.4, 5.2, 9.4], caption="Components",
    )
    doc.h("7.2 Why the math runs twice", 2)
    doc.p("The live requirement ('no next-day lag') puts the calculations in the browser, which is instant but "
          "client-controlled. The server therefore recomputes the identical formulas on submit and stores its own "
          "impact snapshot and flags. Both implementations are pinned to the same golden cases "
          "(tests/fixtures/demand_math_cases.json, 7 cases) so they cannot drift.")
    doc.h("7.3 Performance", 2)
    doc.table(
        ["Operation", "Measured"],
        [
            ["Keystroke to tile update", "< 1 ms of math; UI render within one frame"],
            ["GET /api/segments/cube (all 9 segments)", "~0.13 s"],
            ["Structure justification, Jev confident", "~0.26-0.3 s (one fan-out call)"],
            ["Structure justification, Gemini fallback used", "~1.3 s (capped at 5 s)"],
            ["Repeat of the same justification", "~0.14 s (cached)"],
            ["First request after scale-to-zero", "~9-13 s (container start + seeding)"],
            ["Gemini RTB draft", "several seconds (user-initiated, shows 'Drafting...')"],
        ],
        widths=[9, 8], caption="Latency (production, Cloud Run us-central1)",
    )


def calculations(doc) -> None:
    doc.h("8. Calculations")
    doc.p("Notation: Y = current year (2026), m = entered month, clock = first open month, open months = clock..12, "
          "plan_m = synthetic monthly plan, actual_m = synthetic actual (revealed only for m < clock).")
    doc.table(
        ["Output", "Formula", "Source elements"],
        [
            ["Actuals to date", "sum(actual_m) for m < clock", "monthly_actuals (from Sales Qty)"],
            ["Other open months", "sum over open months != m of (latest submitted entry, else plan_m)", "demand_entries, monthly_plan"],
            ["Full-year estimate (FY)", "actuals to date + entered value + other open months", "-"],
            ["FY low / high", "same with entry low / high", "rep range"],
            ["Gap to plan", "FY - plan FY (Sales Qty, year Y)", "plan_years.qty_ks"],
            ["Year-to-go remaining", "plan FY - actuals to date", "-"],
            ["Needed monthly rate", "max(0, YTG remaining) / months remaining", "-"],
            ["Entered monthly rate", "(FY - actuals to date) / months remaining", "-"],
            ["Last-year monthly rate", "sum(last-year actual over open months) / months remaining", "monthly_actuals 2025"],
            ["Volume share", "FY / Market Qty (KS)", "market_years.qty_ks"],
            ["Plan / last-year share", "plan FY / market KS; last-year qty / last-year market KS", "plan_years, market_years"],
            ["Historical max share", "max over 2024..Y of Syngenta qty / market qty", "plan_years, market_years"],
            ["FY value", "actual value to date + value x price + other open x plan net price", "Sales Value / Qty"],
            ["Value share", "FY value / (Market Qty x Market AvgPrice ExSeed)", "market_years"],
            ["Mega value share", "(Syngenta mega value - segment plan value + FY value) / sum over segments of market qty x ex-seed price", "all segments"],
            ["Competitor new share", "share x (100 - new Syngenta %) / (100 - baseline Syngenta %)", "competitor_shares"],
            ["Implied hectares", "FY / Market Avg Plant Density", "market_years.density"],
            ["Mega implied hectares", "sum(plan qty / density) - segment plan / density + FY / density", "-"],
            ["Volume effect", "(FY - last-year qty) x last-year price", "plan_years 2025"],
            ["Price effect", "(FY value / FY - last-year price) x FY", "-"],
            ["Price share of change", "price effect / (|volume effect| + |price effect|)", "-"],
            ["Month sigma", "max(population stdev of (actual_m - plan_m) for closed months, 15% of plan_m, 50 KS)", "-"],
            ["Month z", "(value - plan_m) / month sigma", "-"],
        ],
        widths=[3.6, 8.4, 5.0], size=8, caption="Formulas (identical in demand_math.py and demandMath.ts)",
    )
    doc.p("Market Qty (KS) equals Market Planted Area (HA) x Market Avg Plant Density on all 994 market rows that carry "
          "both values, which is why hectares and seed quantity can be converted in both directions. Competitor EUR "
          "values equal market quantity x ex-seed price x share (median ratio 1.000 across 73 mega-segments), which "
          "is why value share is computed against quantity x ex-seed price.")


def flags(doc) -> None:
    doc.h("9. Plausibility rules")
    doc.table(
        ["Code", "Severity", "Fires when", "Threshold", "Why it matters"],
        [
            ["no_market", "critical", "Segment has no market quantity", "market KS <= 0", "Share cannot be checked; data-quality issue."],
            ["share_over_100", "critical", "Implied volume share above the whole market", "> 100%", "Physically impossible."],
            ["share_above_history", "warning", "Share far above anything seen", "> 2024-2026 max + 10 pts", "Unprecedented gains need evidence."],
            ["implied_ha_over_market", "critical", "Implied Syngenta hectares exceed planted area", "> market ha", "More seed than land."],
            ["month_outlier", "warning", "Far from both plan month and last year's month", "> 2 sigma from each", "Catches typos and unexplained spikes."],
            ["against_market_trend", "warning", "Demand up while area shrinks, or down while it grows", "area change beyond +/-3% and entry beyond +/-5% of plan month", "Contradicts market dynamics (e.g. T. parvispinus); message quotes the market note."],
            ["price_carrying", "warning", "Volume falls vs last year and price supplies most of the revenue movement", "volume effect < 0, price effect > 0, price share >= 70%", "Revenue plan depends on an unvalidated price assumption."],
            ["above_grower_potential", "warning", "Mega implied ha above CRM Syngenta grower potential", "> capped Syngenta ha", "More than the known customer base could plant."],
            ["range_too_wide", "warning", "Low-high range large relative to the number", "(high - low) / value > 30%", "Supply will build to the low end."],
            ["price_outside_history", "warning", "Entered net price outside history", "outside min-10% .. max+10% of 2024-2026 net prices", "Price assumption needs a reason."],
        ],
        widths=[3.1, 1.6, 4.2, 3.6, 4.5], size=7.8, caption="Flags (identical in flags.py and flags.ts)",
    )
    doc.p("Flags never block submission. Any flag makes the one-sentence justification mandatory, adds the entry to "
          "the consensus exceptions, and is stored with the entry.")
    doc.p("Two further checks compare the structured justification with the number (claim_checks.py). They are "
          "shown under the claim while the rep writes and stored as warning flags on submit, so they reach the "
          "Ledger and the consensus reasons:")
    doc.table(
        ["Code", "Fires when", "Example"],
        [
            ["claim_direction_mismatch", "Jev reads the claim as up (down) but the number is at least 5% below (above) the plan month",
             "'Growers are delaying planting' with a number 15% above plan"],
            ["claim_size_mismatch", "The change vs the plan month is more than 2.5x the upper bound of the size Jev read (negligible 2%, small 5%, moderate 20%), or the rep describes a large effect and the number moves less than 8%",
             "A 'small' effect described for a number 900% above plan"],
        ],
        widths=[3.8, 8.0, 5.2], size=8, caption="Claim-consistency checks",
    )
    doc.p("Competitor shares in the re-split never go below 0%: if Syngenta's implied value would exceed the whole "
          "Blocky PGH market, every competitor shows 0% and the share tile says the number exceeds the market.")


def ai(doc, figures: dict[str, Path]) -> None:
    doc.h("10. AI design: Jev decides, Gemini writes")
    doc.image(figures["ai_flow"], "AI decision flow", width_cm=17)
    doc.h("10.1 Why two models", 2)
    doc.p("**Jev** (TypeSafe, jev-1.13.0) is a decision model: it takes a state and typed questions and returns a "
          "choice, a score or a yes-probability for each, with probabilities, in one call of roughly 0.3 s. It never "
          "writes text, which suits every classification and verification step and removes the risk of a model "
          "inventing numbers. **Gemini 3.8 Flash** on Vertex AI (global endpoint) is used only where prose is needed "
          "or Jev is unsure.")
    doc.h("10.2 Jev question set for one justification", 2)
    doc.p("State sent: JUSTIFICATION sentence, SEGMENT label and description, ENTRY summary (month value, plan, range, "
          "full year, share), FLAGS fired, MARKET NOTES (six note fields plus the plan's rep comment). The sentence-level "
          "questions are prefixed with 'Judge only the JUSTIFICATION line' so flag text cannot leak into the answer.")
    doc.table(
        ["Key", "Type", "Options / levels", "Used for"],
        [
            ["driver", "Choice", "pest_disease, competitor_move, launch_phaseout, price, area_change, weather_water, customer_win_loss, other", "Claim driver; decides the verification signal"],
            ["direction", "Choice", "up, down, neutral", "Claim resolution rule"],
            ["magnitude", "Score", "Negligible, Small (<5%), Moderate (5-20%), Large (>20%)", "Claim size"],
            ["competitor", "Choice", "Competitors from MV360 Competitors (Enza Zaden, Limagrain, Nunhems/BASF, Panora Seeds, Rijk Zwaan, Semillas Fito, Sur Seeds) + none", "Tag; RTB"],
            ["variety", "Choice", "Syngenta varieties from Grower Potential (Hokkaido, Saitama, Leontes, Bokken, Kaamos, Akame, Norris, Carlomagno) + none", "Tag; RTB"],
            ["evidence_source", "Choice", "own_customer_contact, distributor, field_trial, public_statistics, market_notes, none", "Tag"],
            ["verifiable", "Noul", "true/false", "Can later data confirm it?"],
            ["consistent_with_market_notes", "Noul", "true/false", "Fits the market notes?"],
            ["specificity", "Score", "Vague, Some detail, Specific, Specific and quantified", "Vague (< 1.5) sends the entry to consensus"],
            ["addresses_flags", "Noul (only when flags fired)", "true/false", "< 0.5 prompts the rep and sends to consensus"],
        ],
        widths=[3.2, 2.2, 7.4, 4.2], size=8, caption="Justification questions",
    )
    doc.h("10.3 Confidence gating and fallback", 2)
    doc.bullets([
        "For driver, direction, competitor and variety, confidence below 0.8 triggers a Gemini extraction constrained to the same option lists (JSON schema enum, thinking level LOW, 5 s timeout).",
        "Scores (size and specificity) are gated too: confidence below 0.4 (the winning level's probability on a four-level scale) triggers the same Gemini extraction over the level labels.",
        "If Gemini fails or times out, Jev's answer is kept and the field is reported as low-confidence to the rep.",
        "Yes/no answers between 40% and 60% are shown as 'Uncertain' rather than Yes or No.",
        "The provider string stored with every claim records who decided: 'jev', 'jev + gemini fallback', 'jev (recorded)' or 'offline decider'.",
        "Finished claims are cached by state, so Structure then Submit with the same text costs one Jev call.",
    ])
    doc.h("10.4 Other Jev decisions", 2)
    doc.bullets([
        "**Claim verification** (Advance month): Noul 'Given the EVIDENCE, did the CLAIM turn out to be true?' with evidence text 'Sep actual sales X KS vs plan Y KS (+z%). Rep entered V KS (range L-H).'",
        "**Triage** (Consensus): Choice approve / discuss / challenge over the entry, justification and concerns; stored on the entry.",
    ])
    doc.h("10.5 Claim resolution rule", 2)
    doc.table(
        ["Claim direction", "Numeric support when", "Resolution"],
        [
            ["up", "actual >= plan for the month", "confirmed if numeric support and Jev p >= 0.5"],
            ["down", "actual < plan", "contradicted if no numeric support and Jev p < 0.5"],
            ["neutral", "|actual - plan| / plan <= 5%", "inconclusive when they disagree"],
        ],
        widths=[3, 6, 8], caption="Resolution",
    )
    doc.p("Signal recorded per driver: competitor_move -> competitor_share; area_change, pest_disease, weather_water -> "
          "market_hectares; others -> next_month_actuals. In this demo every signal is checked against monthly actuals "
          "because the sample has no monthly competitor or hectare series.")
    doc.h("10.6 Gemini uses", 2)
    doc.bullets([
        "Low-confidence field extraction (above).",
        "Claim summary rewrite after submit (background task, never blocks the rep).",
        "Reasons-to-believe narrative from confirmed claims, market facts, competitor trends and the market-dynamics note; prompt forbids new numbers; template fallback.",
    ])
    doc.h("10.7 Operating modes", 2)
    doc.table(
        ["AI_MODE", "Behaviour"],
        [["live", "Call Jev; on error fall back to recorded fixture, then offline decider"],
         ["record", "Live, and save every Jev response to tests/fixtures/ai/ for offline demos"],
         ["replay", "Recorded fixture if present, else deterministic offline decider"],
         ["auto", "live when JEV_API_KEY is set, otherwise replay"]],
        widths=[3, 14], caption="AI modes",
    )


def data_sources(doc, report: dict) -> None:
    doc.h("11. Source spreadsheets")
    s, m, c, g, h, geo = (report[k] for k in ("sales", "market", "competitors", "grower", "hierarchy", "geo"))
    doc.table(
        ["Workbook / tab", "Rows", "Origin", "Role in the app"],
        [
            ["MV360 Market Spain Sample / Sheet1", f"{m['rowsRead']:,}", "SharePoint list i-MAPS MAPSHistData", "Market size, area, density, prices, qualitative market notes"],
            ["MV360 Sales Spain Sample / Sheet1", f"{s['rowsRead']:,}", "SharePoint list Syngenta5YrsSales", "Syngenta plan and history (quantity, value, launches, rep comments)"],
            ["MV360 Sales Spain Sample (1) / Sheet1", f"{s['rowsRead']:,}", "Byte-identical copy (same MD5)", "Not loaded; identity verified and reported"],
            ["MV360 Competitors Spain Sample / Sheet1", f"{c['rowsRead']:,}", "SharePoint list CompetitorMktShare", "Competitor shares, values, trends"],
            ["Grower Potential ES Sample / Sheet1", f"{g['rowsRead']:,}", "CRM grower-potential export", "Syngenta variety footprint, grower hectares ceiling"],
            ["Prod Hierarchy - complete / prod hierarchy", f"{h['tabs']['prod hierarchy']:,}", "Product hierarchy master", "Micro-segment IDs, descriptions, cycle, colour, ecology"],
            ["Prod Hierarchy / examples, 5yrSales, MAPS, MAPS (2)",
             f"{h['tabs']['examples']}, {h['tabs']['5yrSales']}, {h['tabs']['MAPS']:,}, {h['tabs']['MAPS (2)']}",
             "Naming cross-walks", "Reference only; the app joins on IDs so name mapping is not needed"],
            ["Spain Geo / City", f"{geo['cityRows']:,}", "Province/city pivot", "Data-quality checks only (roll-up out of scope)"],
            ["Spain Geo / Pincode", "2,299", "Street and postcode list", "Data-quality checks only"],
        ],
        widths=[5.2, 2.2, 4.2, 5.4], size=8, caption="Workbooks and tabs",
    )


def element_table(doc, caption: str, rows: list[list[str]]) -> None:
    doc.table(["Data element (column)", "Why it is used", "How it is used (stored as -> used by)"], rows,
              widths=[3.6, 6.0, 7.4], size=7.8, caption=caption)


def data_elements(doc, figures: dict[str, Path]) -> None:
    doc.h("12. Data elements used, why, and how")
    doc.image(figures["lineage"], "Lineage from spreadsheet elements to seed tables and app features", width_cm=17)
    doc.p("Every column that influences the application is listed below. 'Stored as' names the seed table and "
          "column; 'used by' names the feature. Columns that were deliberately not used are listed in section 13.")

    doc.h("12.1 MV360 Market Spain Sample (MAPSHistData)", 2)
    element_table(doc, "Market elements used", [
        ["Micro Segment", "Stable numeric key shared with the hierarchy and sales; names were renamed in February 2026, IDs were not.",
         "market_years.segment_id -> join to segments and plan_years; scope selection (9 segments with 2026 area)."],
        ["Year", "Time axis 2024-2030; 2026 is the current year, 2025 the comparison year.",
         "market_years.year -> current-year context, last-year share, area trend, historical max share."],
        ["Mega Segment Desc", "Identifies the locked mega-segment.", "Filter = 'SWEET PEPPER BLOCKY PGH' (not stored)."],
        ["Country", "Confirms the file is Spain-only (all 3,553 rows).", "Scope check (not stored)."],
        ["Market Planted Area (HA)", "Physical ceiling for any demand number; basis of the market-trend signal.",
         "market_years.hectares -> Implied hectares tile, implied_ha_over_market and against_market_trend flags, RTB market line."],
        ["Market Qty (KS)", "Denominator of volume share; verified as hectares x density on all 994 rows with both values.",
         "market_years.qty_ks -> volume share, share range, share_over_100, share_above_history, historical max share."],
        ["Market Avg Plant Density", "Converts seed quantity (thousand seeds) to hectares.",
         "market_years.density -> implied hectares, mega implied hectares, grower-potential flag."],
        ["Market AvgPrice (ExSeed)", "Seed price in the market; market value = quantity x ex-seed price reconciles the competitor EUR values.",
         "market_years.price_exseed -> value share, mega value share, competitor re-split."],
        ["Market AvgPrice (Farmgate)", "Grower-level price; kept for context and future margin views.", "market_years.price_farmgate -> stored, not used in the math."],
        ["CompetitorPOV", "Qualitative intelligence on who leads the segment.", "market_years.notes.competitors -> Jev state (consistency check), capture context."],
        ["MarketDynamics", "Explains area movements (e.g. T. parvispinus impact).",
         "market_years.notes.dynamics -> against_market_trend message, RTB 'Watch' line, Jev state."],
        ["GrowersPOV, ConsumersPov, Distributors, TechnologyAdapt", "Additional market context (grower treatments, commodity nature, distributor ties such as Agrupainver).",
         "market_years.notes.* -> Jev state for consistent_with_market_notes."],
        ["Modified", "821 micro-segment/year pairs are duplicated (232 with conflicting values).", "Deduplication: keep the most recently modified row (not stored)."],
        ["Path", "Provenance of the export (i-MAPS list).", "Documentation only."],
    ])

    doc.h("12.2 MV360 Sales Spain Sample (Syngenta5YrsSales)", 2)
    element_table(doc, "Sales elements used", [
        ["Title", "Holds the year (2024-2030). 2024-2025 are treated as history, 2026 as the current plan, 2027+ as outlook.",
         "plan_years.year -> plan FY, last-year actuals, historical shares, net price history."],
        ["Microsegment ID", "Join key to market and hierarchy (40 rows missing).", "plan_years.segment_id."],
        ["Microsegment Description", "Recovers missing IDs: 5 Blocky PGH rows for 2448 carried trailing non-breaking spaces and match the hierarchy exactly once normalized.",
         "ID recovery (not stored); 35 rows still without ID are dropped."],
        ["Country", "Mixed 'Spain' / 'SPAIN' (205 rows).", "Normalized to Spain (not stored)."],
        ["Sales Qty", "Syngenta volume in thousand seeds - the number the rep is re-estimating.",
         "Anonymized -> plan_years.qty_ks -> plan FY, share numerator, last-year volume, monthly_plan and monthly_actuals split, track record baselines."],
        ["Sales Value", "Syngenta revenue; together with quantity gives net price.",
         "Anonymized -> plan_years.value_eur and net_price = value / qty -> FY value, value share, revenue split, price flags, mega Syngenta value."],
        ["FPI Qty", "New-launch quantity growing towards 2030; treatment in share is an open SME question.", "plan_years.fpi_qty_ks -> stored for context."],
        ["Qualitative Comments", "The rep's own reasoning in the plan (e.g. '80% of this microsegment', Sur Seeds / Limagrain leadership).",
         "plan_years.comment -> capture header quote, Jev state ('rep comment'), RTB context."],
        ["Modified By", "Shows reps (Garcia, Salinas, Pascual...) edit rows - evidence of the manual process.", "Not loaded; replaced by pseudonyms Rep A / Rep B."],
    ])

    doc.h("12.3 MV360 Competitors Spain Sample (CompetitorMktShare)", 2)
    element_table(doc, "Competitor elements used", [
        ["Mega_Segment_Id", "Selects the Blocky PGH rows (SP01).", "Filter (not stored beyond competitor_shares.mega_segment_id)."],
        ["CompetitorDesc", "Names of the players that lose or gain share.",
         "competitor_shares.competitor -> share tile competitor split, Jev competitor options, RTB competitive context."],
        ["2024% ... 2030%", "Share per competitor per year (sums to 100 per mega-segment in 80 of 87 cases).",
         "Syngenta share recomputed from anonymized sales; other competitors rescaled to 100 - Syngenta -> competitor_shares.share_pct -> re-split on every keystroke."],
        ["2024 ... 2030 (EUR)", "Validated that value = market qty x ex-seed price x share (median ratio 1.000).",
         "Recomputed from market value x share -> competitor_shares.value_eur."],
        ["CompetitorTrend", "Growing / Declining / No change signal.", "competitor_shares.trend -> RTB competitive context, cube."],
    ])

    doc.h("12.4 Grower Potential ES Sample (CRM)", 2)
    element_table(doc, "Grower-potential elements used", [
        ["Crop Local", "Matches the mega-segment name ('SWEET PEPPER BLOCKY PGH', 522 rows).", "Scope filter (not stored)."],
        ["Variety", "Shows which Syngenta varieties growers plant (Saitama, Hokkaido, Leontes, Bokken, Kaamos, Akame...).",
         "grower_potential.variety -> the Jev variety option list and RTB vocabulary."],
        ["Competitor", "Variety owner; for Blocky PGH it is either SYNGENTA or blank, so the file measures Syngenta's customer base, not competitors.",
         "grower_potential.owner -> Syngenta grower ceiling."],
        ["Hecatres Info.", "Hectares per grower-crop row (column name misspelt in the source). Raw total 92,030 ha vs about 10,000 ha market.",
         "Capped at 500 ha per row (32 rows) -> grower_potential.hectares -> above_grower_potential flag ceiling (38,724 ha capped)."],
        ["Density", "Plant density at grower level.", "grower_potential.density -> stored."],
        ["Region", "Sparse region labels (Med-Sur Almeria-Costas 69, Murcia 9 in scope).", "grower_potential.region -> stored for context."],
        ["Country Picklist", "Says IN / FR on 8,953 of 8,998 rows although every row is Spain.", "Data-quality check only."],
        ["Grower Price (Local Currency), Total Addressable Market (Grower Price) + currency", "Completely empty.", "Data-quality check only."],
    ])

    doc.h("12.5 Prod Hierarchy - complete", 2)
    element_table(doc, "Hierarchy elements used (tab: prod hierarchy)", [
        ["f_microSegment", "Master list of micro-segment IDs.", "segments.id."],
        ["f_microSegmentDesc", "Canonical description; also the key for recovering missing sales IDs.",
         "segments.description; cycle profile derived from it (spring / autumn early / medium / late) -> seasonal curve and segment label."],
        ["f_megaSegmentDesc", "Defines the 18 micro-segments of Blocky PGH.", "Scope filter; segments.mega_segment_desc."],
        ["Cycle", "Warm-to-cool vs cool-to-warm cycle.", "segments.cycle -> display."],
        ["Color", "Red / yellow / orange etc.", "segments.color -> segment label and colour dot."],
        ["Ecology Desc", "Passive greenhouse.", "segments.ecology -> display."],
        ["Tabs examples, 5yrSales, MAPS, MAPS (2)", "Show naming mismatches between market and 5-year plan.", "Row counts reported; not loaded because joins use IDs."],
    ])

    doc.h("12.6 Spain Geo", 2)
    element_table(doc, "Geo elements used", [
        ["State (City tab)", "Pivot export mixing provinces and regions, with 'Total' subtotal rows.",
         "Data-quality counts: 761 rows, 62 subtotal rows, 61 provinces/regions. Geographic roll-up is out of scope."],
        ["Address (Postal Code) (Pincode tab)", "1,222 postcodes lost their leading zero (e.g. 2007 instead of 02007).", "Data-quality count only."],
    ])


def unused_elements(doc) -> None:
    doc.h("13. Data elements deliberately not used")
    doc.table(
        ["Workbook", "Columns", "Reason"],
        [
            ["Market", "Title, Territory, CU, GCU, Species, Micro Segment Desc, Macro Segment, Product Type2, Ecology Desc, Mega Segment (code), Multiplication Indicator, System, SalesArea_ComUnit, Compliance Asset Id, ID, Created, Created By, Modified By, UpdateControl, Item Type",
             "Constant within the locked scope, duplicated by the hierarchy (descriptions, ecology), or SharePoint metadata."],
            ["Sales", "ID, New Region, ComUnit_BusArea, Country ISO2, Destination ID, Species, Mega Segment, mega_segment_id, Avg Net Price, Created, Created By, Modified, Item Type, Path",
             "Metadata or constant. Avg Net Price is recomputed as value / quantity so it stays consistent with the anonymized figures."],
            ["Competitors", "Title, Forecast Customer Country_D, SalesArea_ComUnit, Species, Mega_Segment_Desc, GrowthRate%, Product, ResearchDevelopment, GTM_Channel, GTM_Promotion, GTM_Price, Created/Modified metadata",
             "Sparse free text or metadata; GrowthRate% is implied by the yearly shares."],
            ["Grower Potential", "SP Season, Crop: RefData Name, UoM, Quantity, Data Source, Irrigation Qty, BioPotential SE (+ currency), Type, Type Of Culture, BU, DB Region, Country Name, Region Name",
             "Constant (ES_VE2026, Open Field, Vegetable, Western Europe); Quantity and Irrigation Qty track hectares but in mixed units (UoM varies: country land unit, hectares, kilo seeds); 99.9% 'Rollover' source; or an unexplained EUR metric with extreme outliers (BioPotential up to 3.35bn)."],
            ["Prod Hierarchy", "Rename-history columns (2021-2025), codes (Macro/Cycle/Color/Destination/Species/Product Type), t_* and 5yr Sales Plan mapping columns",
             "Needed only for name-based joins; the app joins on IDs."],
            ["Spain Geo", "City, Street", "Territory and geographic roll-up are out of scope."],
        ],
        widths=[2.6, 8.4, 6.0], size=7.8, caption="Unused columns and why",
    )


def data_quality(doc, report: dict) -> None:
    doc.h("14. Data quality findings and cleaning rules")
    s, m, c, g, geo = (report[k] for k in ("sales", "market", "competitors", "grower", "geo"))
    doc.table(
        ["Finding", "Count", "Rule applied"],
        [
            ["Two Sales files byte-identical", "MD5 equal", "Load one copy."],
            ["Market duplicate micro-segment/year pairs", f"{m['duplicatePairs']} pairs ({m['conflictingDuplicatePairs']} conflicting), {m['rowsRemovedAsDuplicates']} rows removed", "Keep latest Modified."],
            ["Market qty = hectares x density", f"{m['qtyEqualsHaTimesDensityRows']} of {m['rowsWithHaAndDensity']} rows", "Relationship used for implied hectares."],
            ["Sales rows without micro-segment ID", f"{s['rowsWithoutMicroSegmentId']}", f"{s['idsRecoveredByExactDescription']} recovered by whitespace-normalized description, {s['rowsDroppedWithoutId']} dropped."],
            ["Sales rows without quantity", f"{s['rowsWithoutQuantity']}", "Treated as zero when aggregating."],
            ["Country spelled SPAIN", f"{s['countryNormalized']}", "Normalized to Spain."],
            ["Competitor shares summing to 100", f"{c['megaSegmentsSummingTo100']} of {c['megaSegments']} mega-segments", "Syngenta recomputed; others rescaled to sum to 100."],
            ["Grower country picklist wrong (IN/FR)", f"{g['countryPicklistMismatch']:,} of {g['rowsRead']:,}", "Ignored; Country Name used."],
            ["Grower region missing", f"{g['regionMissingPct']}%", "Region kept as optional context."],
            ["Grower empty columns", ", ".join(g["emptyColumns"]), "Ignored."],
            ["Grower hectare outliers in scope", f"{g['scopeRowsCapped']} of {g['scopeRows']} rows > 500 ha; {g['scopeHectaresRaw']:,} ha raw vs {g['scopeHectaresCapped']:,} ha capped", "Cap at 500 ha per row; used only as a ceiling."],
            ["Geo pivot subtotal rows", f"{geo['subtotalRows']} of {geo['cityRows']}", "Reported only."],
            ["Postcodes missing leading zero", f"{geo['postcodesMissingLeadingZero']:,}", "Reported only."],
        ],
        widths=[5.2, 5.0, 6.8], size=8, caption="Data-quality findings (from ingest_report.json)",
    )


def synthetic(doc) -> None:
    doc.h("15. Synthetic and anonymized layers")
    doc.p("The spreadsheets are yearly. The brief asks for a monthly demand table and live year-to-go, so the ingest "
          "creates monthly layers. All of them are marked synthetic in the app and must be confirmed with the SMEs.")
    doc.table(
        ["Layer", "How it is built", "Why"],
        [
            ["Anonymization", "Syngenta quantity and value x one hidden factor (0.88-1.12) x (1 + N(0, 3%)) per row, value also x (1 + N(0, 1%)); rep names -> Rep A / Rep B", "Brief: sales figures synthetic unless cleared."],
            ["Seasonal curves", "Per cycle profile, base weight 0.015 per month plus peaks: spring Sep .12, Oct .30, Nov .30, Dec .12; autumn early Apr .12, May .30, Jun .28, Jul .10; autumn medium May .10, Jun .30, Jul .30, Aug .12; autumn late Jul .20, Aug .30, Sep .30, Oct .08; autumn Jun .20, Jul .30, Aug .25", "Seed is sold ahead of transplanting windows in Almeria."],
            ["monthly_plan", "Yearly plan quantity split by the curve (2025, 2026)", "Plan per month for year-to-go and outlier checks."],
            ["monthly_actuals 2025", "Plan x curve x (1 + N(0, 6%)), rescaled to the yearly total", "Last-year monthly pattern."],
            ["monthly_actuals 2026", "Plan x curve x (1 + drift + N(0, 6%)); drift 2482 +8%, 2448 -12%, 2481 -6%; values = qty x net price x (1 + N(0, 1%)); revealed only before the demo clock", "Lets claims be confirmed or contradicted in the demo."],
            ["Rep history (38 entries, Jan-Aug 2026)", "Rep A: bias +1%, noise 4%, range +/-8%. Rep B: bias +13%, noise 7%, range +/-4%. Templates for justifications; claim resolved by direction vs actual", "Seeds a meaningful track record (Rep A reliable, Rep B weak)."],
            ["Demo clock", "Starts at September 2026", "Matches the date of the demo; autumn-late and spring peaks are still open."],
        ],
        widths=[3.2, 9.0, 4.8], size=8, caption="Synthetic layers",
    )


def derived(doc) -> None:
    doc.h("16. Derived data elements created by the application")
    doc.table(
        ["Element", "Where", "Meaning"],
        [
            ["segments.profile", "segments", "Cycle profile parsed from the description (spring, autumn_early, autumn_medium, autumn_late, autumn)."],
            ["plan_years.net_price", "plan_years", "value / quantity after anonymization."],
            ["demand_entries.impact", "demand_entries (JSON)", "Full impact snapshot (all outputs in section 8) at submit time."],
            ["demand_entries.flags", "demand_entries (JSON)", "Flags fired at submit time."],
            ["demand_entries.status", "demand_entries", "submitted, approved, discuss, challenged, superseded."],
            ["demand_entries.triage", "demand_entries (JSON)", "Jev triage choice, confidence, probabilities, provider."],
            ["claims.*", "claims", "Structured claim fields, decisions with probabilities, provider, signal, check month, resolution and resolution detail (actual, plan, in range, error %, Jev probability, evidence text)."],
            ["rep_track_records.*", "rep_track_records", "entries resolved, bias, claim hit rate, range coverage, confirmed, contradicted."],
            ["Supply CSV", "export", "segment, month, low / mid / high, build_to, build_ks, rep, reason."],
        ],
        widths=[4.2, 4.0, 8.8], size=8, caption="Derived elements",
    )


def data_model(doc) -> None:
    doc.h("17. Database model")
    doc.table(
        ["Table", "Key columns", "Content"],
        [
            ["segments", "id (micro-segment), description, cycle, color, ecology, mega_segment_id, profile, owner_id", "9 locked micro-segments"],
            ["market_years", "segment_id, year, hectares, qty_ks, density, price_exseed, price_farmgate, notes (JSON)", "63 rows"],
            ["plan_years", "segment_id, year, qty_ks, value_eur, net_price, fpi_qty_ks, comment", "63 rows"],
            ["competitor_shares", "mega_segment_id, competitor, year, share_pct, value_eur, trend", "9 players x 7 years"],
            ["monthly_plan", "segment_id, year, month, qty_ks", "2025-2026"],
            ["monthly_actuals", "segment_id, year, month, qty_ks, value_eur", "2025-2026 (2026 revealed by clock)"],
            ["grower_potential", "variety, owner, hectares, density, region", "522 capped rows"],
            ["demand_entries", "id, user_id, segment_id, year, month, value, low, high, price, justification, impact, flags, status, source, triage, reviewed_by/at, created_at", "Ledger"],
            ["claims", "entry_id, driver, direction, magnitude, competitor, variety, evidence_source, verifiable, consistent_with_notes, specificity, addresses_flags, summary, decisions, provider, signal, check_year/month, resolution, resolution_detail, resolved_at", "One per justified entry"],
            ["rep_track_records", "user_id, entries_resolved, bias_pct, claim_hit_rate, range_coverage, confirmed, contradicted", "Materialized on advance"],
            ["demo_clock", "year, month", "Single row"],
        ],
        widths=[3.2, 9.6, 4.2], size=7.8, caption="Tables (one Alembic migration)",
    )


def api(doc) -> None:
    doc.h("18. API")
    doc.table(
        ["Method and path", "Role", "Purpose"],
        [
            ["GET /api/health", "-", "Liveness"],
            ["GET /api/meta", "-", "Scope, users, clock, AI status, thresholds"],
            ["GET /api/segments/cube", "-", "All segment contexts for client-side math (one call per page load)"],
            ["POST /api/justifications/analyze", "-", "Impact, flags and Jev-structured claim for a draft"],
            ["POST /api/entries", "owning rep", "Validate, recompute, store entry + claim, supersede previous"],
            ["GET /api/entries", "-", "Ledger (filters: segmentId, userId, includeSuperseded, limit)"],
            ["POST /api/demo/advance", "-", "Close month, resolve claims, recompute track records"],
            ["POST /api/demo/reset", "-", "Reseed demo data"],
            ["GET /api/reps", "-", "Track records"],
            ["GET /api/consensus/queue", "-", "Exceptions with reasons + Jev triage; routine entries"],
            ["POST /api/consensus/bulk-approve", "lead", "Approve routine entries"],
            ["POST /api/consensus/entries/{id}/decision", "lead", "approve / discuss / challenge"],
            ["POST /api/consensus/rtb", "-", "Reasons-to-believe draft (Gemini or template)"],
            ["GET /api/export/supply.csv", "-", "Approved supply range"],
            ["GET /api/data-quality", "-", "Ingest report"],
        ],
        widths=[6.2, 2.4, 8.4], size=8, caption="Endpoints",
    )


def deployment(doc) -> None:
    doc.h("19. Deployment and operations")
    doc.table(
        ["Item", "Value"],
        [
            ["Live URL (Firebase Hosting)", LIVE_URL],
            ["Cloud Run URL", RUN_URL],
            ["GCP project", "skystream-510015 (billing account 0173FC-2DDC0C-483654)"],
            ["Cloud Run service", "skystream-api, us-central1, max 1 instance, min 0, 1 GiB, port 8080"],
            ["Image", "us-central1-docker.pkg.dev/skystream-510015/skystream/api:latest (Cloud Build, multi-stage: Node builds SPA, Python runs API)"],
            ["Service account", "skystream-api@skystream-510015.iam.gserviceaccount.com: roles/aiplatform.user, secretAccessor on jev-api-key"],
            ["Secret", "jev-api-key -> JEV_API_KEY"],
            ["Environment", "AI_MODE=live, GEMINI_ENABLED=true, GCP_PROJECT=skystream-510015, GCP_LOCATION=global, DATABASE_URL=sqlite (per instance)"],
            ["Deploy", "deploy/deploy.sh (APIs, registry, SA, build, run deploy, firebase deploy)"],
        ],
        widths=[4.5, 12.5], size=8.5, caption="Production configuration",
    )
    doc.p("Local development: npm install; cd backend && uv sync && uv run alembic upgrade head && uv run python seed.py; "
          "npm run dev (API :8000, web :5173). npm run ingest rebuilds data/seed from data/raw/*.xlsx.")


def testing(doc) -> None:
    doc.h("20. Testing and quality")
    doc.bullets([
        "**Backend (pytest, 37 tests)**: golden math cases, flag rules, claim-consistency checks, decision provider (offline, recorded fixture, live mocked, Jev failure, low-confidence, Gemini fallback and summary), full API loop (flag enforcement, ownership, closed months, supersede, consensus, advance, CSV, RTB, track records, reset, data quality).",
        "**Frontend (vitest, 22 tests)**: TypeScript math and flags against the same golden cases; tile components.",
        "**End to end (Playwright)**: the demo script from capture to track record, run locally and against production.",
        "**Static checks**: ruff (lint + format) and TypeScript strict type check.",
    ])


def limits(doc) -> None:
    doc.h("21. Limitations, risks and next steps")
    doc.table(
        ["Area", "Current state", "Next step"],
        [
            ["Authentication", "Role switcher via header", "Firebase Auth / SSO with role claims"],
            ["Persistence", "SQLite per Cloud Run instance, reset on cold start; brief inconsistency possible if a second instance starts", "Cloud SQL Postgres (already supported) or min-instances=1"],
            ["Monthly data", "Synthetic curves and actuals", "Confirm seasonality; load real monthly demand and year-to-date actuals"],
            ["Claim signals", "Competitor and hectare claims checked against monthly sales", "Add competitor-share and MAPA/ESYRCE hectare feeds"],
            ["Jev", "Early-access model; confidence gating + Gemini fallback + offline decider", "Record fixtures for demos; tune option wording and 0.8 threshold on labelled examples"],
            ["Thresholds", "Defaults (10 pts, 2 sigma, 30% range, 70% price share)", "Calibrate with the SMEs"],
            ["Scope", "One crop, one country", "Territory roll-up and more crops after the MVP"],
        ],
        widths=[3.0, 7.0, 7.0], size=8, caption="Limitations and next steps",
    )
    doc.h("21.1 Open questions for the SMEs", 2)
    doc.bullets([
        "Are the 2024-2025 Sales rows actuals and 2026+ the plan? Where do monthly demand and year-to-date actuals live today?",
        "Entry unit and level: thousand seeds per micro-segment, or per mega-segment?",
        "Monthly seasonality for Blocky PGH seed in Spain.",
        "Meaning of FPI and whether launch quantities count toward share.",
        "Plausibility thresholds the business would trust.",
        "Seed production lead time and current excess / write-off rate (to size the supply-range benefit).",
        "Clearance to use real Syngenta figures and to send (synthetic) text to Jev's hosted API.",
    ])


def glossary(doc) -> None:
    doc.h("22. Glossary")
    doc.table(
        ["Term", "Meaning"],
        [
            ["KS", "Thousand seeds, the unit of market and Syngenta quantity"],
            ["PGH", "Passive greenhouse"],
            ["Micro / mega segment", "Hierarchy levels; micro = cycle x colour within a crop type, mega = crop type (Blocky PGH = SP01)"],
            ["YTG", "Year to go: plan minus actuals to date"],
            ["FY", "Full-year estimate"],
            ["RTB", "Reasons to believe: the narrative defending a demand number"],
            ["FPI", "New-launch quantity in the Sales list"],
            ["Jev Choice / Score / Noul", "Pick one option / weighted score on an ordered rubric / probability that a statement is true"],
            ["Claim", "The structured, checkable form of a rep's justification"],
            ["Track record", "Per-rep hit rate, bias and range coverage from resolved claims"],
        ],
        widths=[4.5, 12.5], size=8.5, caption="Terms",
    )
