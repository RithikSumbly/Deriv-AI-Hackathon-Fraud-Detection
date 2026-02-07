#!/usr/bin/env python3
"""
Generate a simple PDF slide deck explaining the Fraud Investigation Dashboard.
Run: python scripts/generate_slides.py
Output: website_overview_slides.pdf (in project root)
Requires: pip install reportlab
"""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "website_overview_slides.pdf"
PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch
TITLE_SIZE = 28
SLIDE_TITLE_SIZE = 22
BODY_SIZE = 12
BULLET_INDENT = 0.5 * inch


def draw_slide(c: canvas.Canvas, title: str, bullets: list[str], subtitle: str = ""):
    """Draw one slide: title at top, optional subtitle, then bullet list."""
    c.setFont("Helvetica-Bold", SLIDE_TITLE_SIZE)
    c.setFillColor(colors.HexColor("#1a1a2e"))
    c.drawString(MARGIN, PAGE_H - MARGIN - 0.4 * inch, title)
    y = PAGE_H - MARGIN - 0.9 * inch

    if subtitle:
        c.setFont("Helvetica", 14)
        c.setFillColor(colors.HexColor("#4a4a6a"))
        c.drawString(MARGIN, y, subtitle)
        y -= 0.35 * inch

    c.setFont("Helvetica", BODY_SIZE)
    c.setFillColor(colors.HexColor("#2d2d44"))
    for line in bullets:
        # Wrap long lines (approx 85 chars at 12pt)
        max_chars = 78
        if len(line) > max_chars:
            parts = []
            while line:
                parts.append(line[:max_chars])
                line = line[max_chars:]
            for p in parts:
                c.drawString(MARGIN + BULLET_INDENT, y, "  " + p)
                y -= 0.28 * inch
        else:
            c.drawString(MARGIN, y, "•  " + line)
            y -= 0.28 * inch
        if y < MARGIN + 0.5 * inch:
            break
    c.showPage()


def draw_title_slide(c: canvas.Canvas):
    """Cover slide."""
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.HexColor("#1a1a2e"))
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 0.3 * inch, "AI-Powered Fraud Detection")
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 0.2 * inch, "& Investigation")
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.HexColor("#5a5a7a"))
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 0.9 * inch, "Streamlit dashboard for investigators")
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#888899"))
    c.drawCentredString(PAGE_W / 2, MARGIN + 0.2 * inch, "Deriv AI Hackathon")
    c.showPage()


def main():
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=letter)
    c.setTitle("Fraud Investigation Dashboard — Overview")

    # Slide 1: Title
    draw_title_slide(c)

    # Slide 2: What it is
    draw_slide(
        c,
        "What is the website?",
        [
            "A live Streamlit dashboard for fraud investigators.",
            "Combines ML fraud scoring + anomaly detection with explainable alerts.",
            "Human-in-the-loop: investigators decide; AI assists with explanations and next steps.",
            "Every decision is auditable; feedback can be used to retrain models.",
        ],
        subtitle="Single web app to triage, investigate, and close cases.",
    )

    # Slide 3: Main features
    draw_slide(
        c,
        "Main features",
        [
            "Alert queue (sidebar): risk badge, fraud %, one-line AI explanation; sorted by risk.",
            "Case view: timeline reconstruction, evidence tabs (transactions, geo, identity, network).",
            "Device/IP network graph: see accounts linked by shared devices or IPs.",
            "Plain-language explanations: why an account was flagged, risk factors, confidence.",
            "Next-step recommendations from an LLM (suggestions only, no auto-labels).",
            "Decisions: confirm fraud, mark legit, or dismiss with required reason; stored in audit trail.",
            "Regulatory-style investigation reports and export of feedback for model retraining.",
        ],
    )

    # Slide 4: How it works (flow)
    draw_slide(
        c,
        "How it works",
        [
            "1. System runs a fraud classifier + anomaly detector on account/transaction data.",
            "2. Alerts appear in the queue with risk score and short AI explanation.",
            "3. Investigator selects an alert → case view loads (timeline, evidence, network).",
            "4. Investigator reviews evidence and optional LLM next-step suggestions.",
            "5. Investigator records a decision (fraud / legit / dismiss) with a reason.",
            "6. Reports can be generated; feedback is exported for periodic retraining.",
        ],
        subtitle="End-to-end flow.",
    )

    # Slide 5: Tech
    draw_slide(
        c,
        "Technology",
        [
            "Frontend: Streamlit (Python), dark theme, wide layout.",
            "Backend: Fraud classifier (e.g. LightGBM), anomaly detector, Neo4j for graph features.",
            "Explainability: SHAP-style factors, LLM for narrative explanations and next steps.",
            "Data: synthetic fraud dataset; supports unlabeled pipeline and feedback retraining.",
        ],
    )

    # Slide 6: Summary
    draw_slide(
        c,
        "Summary",
        [
            "One dashboard to detect, explain, investigate, and decide on fraud cases.",
            "Explainable and auditable; investigators stay in control.",
            "Designed to improve over time via feedback and retraining.",
        ],
        subtitle="Built for the Deriv AI Hackathon.",
    )

    c.save()
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
