"""Render the architecture, user-flow, AI-decision and data-lineage diagrams used in the design document."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

GREEN, GREEN_BG = "#1a5c31", "#eef7f0"
PURPLE, PURPLE_BG = "#6b46c1", "#f3effc"
BLUE, BLUE_BG = "#214f94", "#eef4fd"
AMBER, AMBER_BG = "#92600a", "#fff7e8"
GREY, GREY_BG = "#4b5563", "#f4f5f2"
RED, RED_BG = "#9b2626", "#fdeeee"


def _canvas(w: float, h: float):
    fig, ax = plt.subplots(figsize=(w, h), dpi=170)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, edge=GREEN, fill=GREEN_BG, size=8.5, bold_first=True, align="center"):
    ax.add_patch(
        FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", linewidth=1.3,
                       edgecolor=edge, facecolor=fill)
    )
    lines = text.split("\n")
    if bold_first and len(lines) > 1:
        ax.text(x + w / 2 if align == "center" else x + 0.12, y + h - 0.2, lines[0], ha=align, va="top",
                fontsize=size + 0.5, fontweight="bold", color=edge)
        ax.text(x + w / 2 if align == "center" else x + 0.12, y + h - 0.48, "\n".join(lines[1:]), ha=align,
                va="top", fontsize=size - 0.5, color="#1b2a1f", linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=edge,
                fontweight="bold" if bold_first else "normal", linespacing=1.3)


def group(ax, x, y, w, h, label, edge=GREY):
    ax.add_patch(
        FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.2", linewidth=1.1,
                       edgecolor=edge, facecolor="none", linestyle=(0, (4, 3)))
    )
    ax.text(x + 0.15, y + h - 0.12, label, ha="left", va="top", fontsize=9, fontweight="bold", color=edge)


def arrow(ax, p1, p2, label=None, color="#374151", style="-|>", rad=0.0, size=7.5, label_pos=0.5, dashed=False):
    ax.add_patch(
        FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=11, linewidth=1.2, color=color,
                        connectionstyle=f"arc3,rad={rad}", linestyle="--" if dashed else "-")
    )
    if label:
        mx = p1[0] + (p2[0] - p1[0]) * label_pos
        my = p1[1] + (p2[1] - p1[1]) * label_pos
        ax.text(mx, my, label, fontsize=size, ha="center", va="center", color=color,
                bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "none", "alpha": 0.95})


def diamond(ax, cx, cy, w, h, text, edge=AMBER, fill=AMBER_BG):
    ax.add_patch(Polygon([(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)],
                         closed=True, linewidth=1.3, edgecolor=edge, facecolor=fill))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=8, color=edge, fontweight="bold", linespacing=1.2)


def architecture(out: Path) -> None:
    fig, ax = _canvas(16, 10.5)
    ax.text(8, 10.25, "Defensible Demand Ledger: system architecture", ha="center", fontsize=14, fontweight="bold")

    group(ax, 0.2, 5.2, 3.5, 4.7, "Offline data preparation", edge=AMBER)
    box(ax, 0.45, 8.0, 3.0, 1.45, "6 source workbooks\nMV360 Market, Sales, Competitors\nGrower Potential ES\nProd Hierarchy, Spain Geo",
        edge=AMBER, fill=AMBER_BG, size=8)
    box(ax, 0.45, 6.3, 3.0, 1.35, "scripts/ingest (pandas)\ndedupe, ID joins, cap outliers\nanonymize, synthesize months\nwrite data-quality report",
        edge=AMBER, fill=AMBER_BG, size=8)
    box(ax, 0.45, 5.4, 3.0, 0.7, "data/seed/*.json (committed)", edge=AMBER, fill=AMBER_BG, size=8.5, bold_first=True)
    arrow(ax, (1.95, 8.0), (1.95, 7.65))
    arrow(ax, (1.95, 6.3), (1.95, 6.1))

    group(ax, 4.1, 7.4, 7.6, 2.5, "Browser: React 19 SPA (Vite, TanStack Query, Tailwind)", edge=GREEN)
    box(ax, 4.35, 7.65, 2.3, 1.75, "Screens\nCapture, Ledger\nConsensus, Track record\nData quality\nrole switcher, demo clock", size=8)
    box(ax, 6.85, 7.65, 2.35, 1.75, "demandMath.ts + flags.ts\nshare, YTG, implied ha\nvolume/price split\n8 plausibility rules\n< 1 ms per keystroke", size=8)
    box(ax, 9.4, 7.65, 2.1, 1.75, "Query cache\none GET /segments/cube\nmutations: submit,\nadvance, approve, RTB", size=8)
    arrow(ax, (6.65, 8.5), (6.85, 8.5))
    arrow(ax, (9.4, 8.5), (9.2, 8.5))

    box(ax, 12.1, 8.2, 3.6, 1.25, "Firebase Hosting\nskystream-510015.web.app\nstatic SPA, /api/** rewrite", edge=BLUE, fill=BLUE_BG, size=8)
    arrow(ax, (11.7, 8.8), (12.1, 8.8), "HTTPS")

    group(ax, 4.1, 0.25, 7.6, 6.8, "Cloud Run service skystream-api (us-central1, 1 instance, FastAPI + uv)", edge=GREEN)
    box(ax, 4.35, 5.35, 7.1, 1.25, "Routers (thin HTTP layer)\n/meta /segments/cube /justifications/analyze /entries /demo/advance /demo/reset\n/reps /consensus/queue /consensus/bulk-approve /consensus/entries/{id}/decision /consensus/rtb /export/supply.csv",
        size=7.8)
    box(ax, 4.35, 3.1, 3.45, 2.0, "Services\ncontext_service (cube)\nentry_service (submit, supersede)\nclock_service (resolve claims)\nconsensus_service (queue, RTB)\ntrack_record, export, seed", size=7.8)
    box(ax, 8.0, 3.1, 3.45, 2.0, "demand_math.py + flags.py\nsame formulas as the browser\nrecomputed on submit\nimpact snapshot stored\nwith every entry", size=7.8)
    box(ax, 4.35, 0.5, 3.45, 2.35, "SQLAlchemy async + Alembic\nSQLite (demo) or Postgres\nsegments, market_years, plan_years\ncompetitor_shares, monthly_plan,\nmonthly_actuals, grower_potential,\ndemand_entries, claims,\nrep_track_records, demo_clock", size=7.5)
    box(ax, 8.0, 0.5, 3.45, 2.35, "DecisionProvider (app/ai)\nmode: live / record / replay\nJev client (typed decisions)\nGemini client (prose, fallback)\nfixture store + offline decider\nin-memory claim cache", edge=PURPLE, fill=PURPLE_BG, size=7.8)
    arrow(ax, (7.9, 5.35), (6.1, 5.1))
    arrow(ax, (7.9, 5.35), (9.7, 5.1))
    arrow(ax, (6.1, 3.1), (6.1, 2.85))
    arrow(ax, (7.8, 4.0), (8.0, 4.0))
    arrow(ax, (7.8, 3.3), (8.6, 2.85), rad=0.1)
    arrow(ax, (3.45, 5.75), (4.35, 2.4), "seed on\nstartup", rad=-0.2, color=AMBER, label_pos=0.45)

    arrow(ax, (13.9, 8.2), (11.45, 6.2), "/api/** rewrite", color=BLUE, rad=-0.1)

    box(ax, 12.1, 4.3, 3.6, 1.55, "TypeSafe Jev\napi.typesafe.ai/v1/systemone\njev-1.13.0, Choice/Score/Noul\n~0.3 s per fan-out call", edge=PURPLE, fill=PURPLE_BG, size=8)
    box(ax, 12.1, 2.3, 3.6, 1.55, "Vertex AI Gemini\ngemini-3.8-flash (global)\nsummaries, RTB narrative\nlow-confidence fallback", edge=PURPLE, fill=PURPLE_BG, size=8)
    box(ax, 12.1, 0.5, 3.6, 1.35, "Secret Manager + IAM\njev-api-key -> JEV_API_KEY\nSA skystream-api: aiplatform.user", edge=BLUE, fill=BLUE_BG, size=8)
    arrow(ax, (11.45, 2.0), (12.1, 5.0), "decisions", color=PURPLE, rad=-0.15)
    arrow(ax, (11.45, 1.6), (12.1, 3.0), "prose", color=PURPLE, rad=-0.1)
    arrow(ax, (12.1, 1.15), (11.45, 1.15), dashed=True, color=BLUE)

    box(ax, 0.45, 0.5, 3.0, 4.3, "Deployment pipeline\ndeploy/deploy.sh\n1. enable APIs\n2. Artifact Registry repo\n3. service account + IAM\n4. Cloud Build: node stage\n   builds SPA, python stage\n   bundles API + seed\n5. gcloud run deploy\n6. firebase deploy hosting",
        edge=BLUE, fill=BLUE_BG, size=8, align="left")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def user_flow(out: Path) -> None:
    fig, ax = _canvas(15, 13)
    ax.text(7.5, 12.75, "User flow: from a typed number to a trusted, approved demand line", ha="center", fontsize=14,
            fontweight="bold")
    for x, label, c in [(0.2, "SALES REP", GREEN), (5.2, "APP + JEV / GEMINI", PURPLE), (10.2, "CONSENSUS LEAD", BLUE)]:
        ax.add_patch(FancyBboxPatch((x, 0.2), 4.6, 12.1, boxstyle="round,pad=0.02,rounding_size=0.2",
                                    linewidth=0.8, edgecolor=c, facecolor="none", linestyle=(0, (2, 3))))
        ax.text(x + 2.3, 12.1, label, ha="center", fontsize=10, fontweight="bold", color=c)

    box(ax, 0.6, 10.8, 3.8, 0.9, "1. Pick micro-segment + open month\nowned segments listed first", size=8)
    box(ax, 0.6, 9.4, 3.8, 1.0, "2. Type demand (KS), drag range,\noptional net price", size=8)
    box(ax, 5.6, 9.2, 3.8, 1.4, "3. Live recalculation in browser\nshare (vol/value), competitor split\nyear-to-go, implied ha\nvolume vs price, flags", edge=PURPLE, fill=PURPLE_BG, size=8)
    diamond(ax, 7.5, 7.9, 2.6, 1.1, "Any flags?")
    box(ax, 0.6, 7.0, 3.8, 1.1, "4. Write one-sentence justification\n(required if flagged)", size=8)
    box(ax, 5.6, 5.6, 3.8, 1.55, "5. Structure with Jev\n1 call, 9-10 typed questions\ndriver, direction, size, competitor,\nvariety, evidence, specificity...\nGemini only if confidence < 0.8", edge=PURPLE, fill=PURPLE_BG, size=7.8)
    box(ax, 0.6, 5.3, 3.8, 1.0, "6. Review tags + probabilities\nrefine sentence if weak, Submit", size=8)
    box(ax, 5.6, 3.95, 3.8, 1.3, "7. Server re-validates math\nstores entry + impact + flags + claim\nprevious entry superseded\nGemini polishes summary (background)", edge=PURPLE, fill=PURPLE_BG, size=7.8)
    diamond(ax, 12.5, 10.3, 3.0, 1.3, "Exception?\nflag / weak rep /\nvague claim")
    box(ax, 10.6, 8.1, 3.8, 1.3, "8a. Review exception\nreasons + Jev triage suggestion\nApprove / Discuss / Challenge", edge=BLUE, fill=BLUE_BG, size=8)
    box(ax, 10.6, 6.4, 3.8, 1.0, "8b. Bulk-approve routine lines\none click", edge=BLUE, fill=BLUE_BG, size=8)
    box(ax, 10.6, 4.7, 3.8, 1.2, "9. Draft RTB (Gemini, confirmed\nclaims only) + export supply CSV\nlow / mid / high, build-to rule", edge=BLUE, fill=BLUE_BG, size=8)
    box(ax, 5.6, 1.9, 3.8, 1.55, "10. Advance month\nreveal actuals, resolve due claims:\nnumeric check + Jev Noul verdict\n-> confirmed / contradicted / inconclusive", edge=PURPLE, fill=PURPLE_BG, size=7.8)
    box(ax, 5.6, 0.45, 3.8, 1.1, "11. Track records recomputed\nhit rate, bias, range coverage", edge=PURPLE, fill=PURPLE_BG, size=8)
    box(ax, 0.6, 0.6, 3.8, 1.3, "12. Rep sees own track record\nnext to the next entry; weak\nrecords go to consensus", size=8)

    arrow(ax, (2.5, 10.8), (2.5, 10.4))
    arrow(ax, (4.4, 9.9), (5.6, 9.9), "every keystroke")
    arrow(ax, (7.5, 9.2), (7.5, 8.45))
    arrow(ax, (6.2, 7.9), (4.4, 7.6), "yes: required", size=7)
    arrow(ax, (8.8, 7.9), (9.3, 6.8), "no: optional", size=7, rad=-0.3)
    arrow(ax, (4.4, 7.2), (5.6, 6.5))
    arrow(ax, (5.6, 5.9), (4.4, 5.8))
    arrow(ax, (4.4, 5.4), (5.6, 4.7))
    arrow(ax, (9.4, 4.8), (11.0, 9.8), "queue", rad=-0.25)
    arrow(ax, (12.5, 9.65), (12.5, 9.4), "yes", size=7)
    arrow(ax, (14.0, 10.3), (14.6, 6.9), "no", rad=-0.3, size=7)
    arrow(ax, (14.6, 6.9), (14.4, 6.9))
    arrow(ax, (12.5, 8.1), (12.5, 7.4))
    arrow(ax, (12.5, 6.4), (12.5, 5.9))
    arrow(ax, (10.6, 5.0), (9.4, 3.2), "next month", rad=0.1)
    arrow(ax, (7.5, 1.9), (7.5, 1.55))
    arrow(ax, (5.6, 1.0), (4.4, 1.2))
    arrow(ax, (0.6, 1.25), (0.6, 9.9), rad=-0.12, dashed=True, color=GREY)
    ax.text(0.28, 5.0, "next cycle", rotation=90, fontsize=7.5, color=GREY, ha="center", va="center")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def ai_flow(out: Path) -> None:
    fig, ax = _canvas(15, 7.2)
    ax.text(7.5, 7.0, "AI decision flow: Jev decides, Gemini writes", ha="center", fontsize=14, fontweight="bold")
    box(ax, 0.2, 4.6, 2.8, 1.6, "State sent to Jev\nJUSTIFICATION sentence\nSEGMENT + ENTRY summary\nFLAGS fired\nMARKET NOTES + rep comment", size=7.8)
    box(ax, 3.5, 4.6, 3.0, 1.6, "Jev fan-out (1 call)\nChoice: driver, direction,\ncompetitor, variety, evidence\nScore: magnitude, specificity\nNoul: verifiable, fits notes,\nexplains flags", edge=PURPLE, fill=PURPLE_BG, size=7.6)
    diamond(ax, 8.0, 5.4, 2.4, 1.3, "Choice conf.\n>= 0.8?")
    box(ax, 9.9, 5.8, 2.6, 0.95, "Accept Jev answer\nprovider = jev", edge=GREEN, fill=GREEN_BG, size=8)
    box(ax, 9.9, 4.2, 2.6, 1.25, "Gemini fallback\nenum-constrained JSON\nthinking LOW, 5 s cap\nfails -> keep Jev, mark low", edge=PURPLE, fill=PURPLE_BG, size=7.6)
    box(ax, 12.8, 4.6, 2.0, 1.6, "Structured claim\n+ template summary\ncached by state\n~0.3 s typical", edge=GREEN, fill=GREEN_BG, size=7.8)
    arrow(ax, (3.0, 5.4), (3.5, 5.4))
    arrow(ax, (6.5, 5.4), (6.8, 5.4))
    arrow(ax, (9.2, 5.6), (9.9, 6.2), "yes", size=7)
    arrow(ax, (9.2, 5.2), (9.9, 4.8), "no", size=7)
    arrow(ax, (12.5, 6.2), (12.8, 5.8))
    arrow(ax, (12.5, 4.8), (12.8, 5.0))

    box(ax, 0.2, 1.9, 2.8, 1.8, "Modes (AI_MODE)\nlive: call Jev\nrecord: live + save fixture\nreplay: fixture, else offline\nauto: live if key present", edge=GREY, fill=GREY_BG, size=7.8)
    box(ax, 3.5, 1.9, 3.0, 1.8, "Claim resolution (advance month)\nnumeric: up -> actual >= plan\ndown -> actual < plan\nneutral -> within 5%\n+ Jev Noul: evidence supports?", edge=PURPLE, fill=PURPLE_BG, size=7.6)
    box(ax, 6.9, 1.9, 2.9, 1.8, "Resolution\nconfirmed: numeric & p >= 0.5\ncontradicted: neither\ninconclusive: disagree", edge=GREEN, fill=GREEN_BG, size=7.8)
    box(ax, 10.2, 1.9, 2.3, 1.8, "Triage (consensus)\nJev Choice:\napprove / discuss /\nchallenge + confidence", edge=PURPLE, fill=PURPLE_BG, size=7.8)
    box(ax, 12.8, 1.9, 2.0, 1.8, "Gemini prose\nclaim summary\n(background)\nRTB narrative", edge=PURPLE, fill=PURPLE_BG, size=7.8)
    arrow(ax, (6.5, 2.8), (6.9, 2.8))
    box(ax, 0.2, 0.2, 14.6, 1.2, "Guardrails: models never produce or change a number; every decision is stored with its probabilities and the provider that made it;\n"
        "Gemini is never on the keystroke or submit path; without keys the app replays recorded Jev answers, then a deterministic offline decider.",
        edge=GREY, fill="white", size=8, bold_first=False)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def lineage(out: Path) -> None:
    fig, ax = _canvas(16, 9.5)
    ax.text(8, 9.3, "Data lineage: spreadsheet elements -> seed tables -> app features", ha="center", fontsize=14,
            fontweight="bold")
    src = [
        ("MV360 Market", "Micro Segment, Year, Planted Area (HA),\nQty (KS), Plant Density, ExSeed/Farmgate\nprice, 6 POV notes, Modified", 7.5),
        ("MV360 Sales", "Title (year), Microsegment ID + Desc,\nSales Qty, Sales Value, FPI Qty,\nQualitative Comments, Country", 6.0),
        ("MV360 Competitors", "Mega_Segment_Id, CompetitorDesc,\n2024%-2030%, 2024-2030 EUR,\nCompetitorTrend", 4.5),
        ("Grower Potential ES", "Crop Local, Variety, Competitor,\nHecatres Info., Density, Region,\nCountry Picklist (check)", 3.0),
        ("Prod Hierarchy", "f_microSegment, f_microSegmentDesc,\nf_megaSegmentDesc, Cycle, Color,\nEcology Desc", 1.5),
        ("Spain Geo", "State, Address (Postal Code)\n(data-quality checks only)", 0.0),
    ]
    for title, body, y in src:
        box(ax, 0.2, y, 4.2, 1.25, f"{title}\n{body}", edge=AMBER, fill=AMBER_BG, size=7.6)
    tables = [
        ("market_years", 7.7), ("plan_years", 6.55), ("monthly_plan / monthly_actuals\n(synthetic split)", 5.4),
        ("competitor_shares", 4.25), ("grower_potential", 3.1), ("segments", 1.95), ("ingest_report.json", 0.8),
    ]
    for t, y in tables:
        box(ax, 6.0, y, 3.4, 0.9, t, edge=GREEN, fill=GREEN_BG, size=8.2, bold_first=True)
    feats = [
        ("Share tile: volume + value share,\nhistorical max, competitor split", 7.7),
        ("Year-to-go tile: plan FY, actuals\nto date, monthly rates", 6.55),
        ("Implied hectares tile +\nhectare / trend flags", 5.4),
        ("Revenue split: volume vs price\n+ price-carrying flag", 4.25),
        ("Jev state (notes, comments,\ncompetitor + variety options)", 3.1),
        ("Grower-potential ceiling flag\nseasonal curve by cycle", 1.95),
        ("Data quality screen", 0.8),
    ]
    for f, y in feats:
        box(ax, 11.2, y, 4.6, 0.9, f, edge=BLUE, fill=BLUE_BG, size=7.8, bold_first=False)
    links = [(8.1, 8.15), (8.1, 5.85), (6.6, 7.0), (6.6, 5.85), (5.1, 4.7), (3.6, 3.55), (2.1, 2.4), (2.1, 5.85),
             (0.8, 1.25), (6.6, 1.25), (8.1, 1.25), (3.6, 1.25)]
    for ys, yt in links:
        arrow(ax, (4.4, ys), (6.0, yt), color="#9ca3af")
    feature_links = [(8.15, 8.15), (8.15, 5.85), (8.15, 4.7), (7.0, 7.0), (7.0, 4.7), (5.85, 7.0), (4.7, 8.15),
                     (8.15, 3.55), (7.0, 3.55), (4.7, 3.55), (3.55, 2.4), (2.4, 2.4), (1.25, 1.25)]
    for ys, yt in feature_links:
        arrow(ax, (9.4, ys), (11.2, yt), color="#9ca3af")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def render_all(out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "architecture": out_dir / "architecture.png",
        "user_flow": out_dir / "user_flow.png",
        "ai_flow": out_dir / "ai_flow.png",
        "lineage": out_dir / "lineage.png",
    }
    architecture(paths["architecture"])
    user_flow(paths["user_flow"])
    ai_flow(paths["ai_flow"])
    lineage(paths["lineage"])
    return paths
