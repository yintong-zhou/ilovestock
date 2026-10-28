"""PDF of saved analyses for the History and Watchlist pages: a summary table, then one page per
ticker with its criteria, trade plan, reasons and note.

Built from history rows (`history.read`), so nothing is downloaded. The core font (Helvetica) is
Latin-1 only: other characters get an ASCII stand-in or "?".
"""

from datetime import datetime
from pathlib import Path

from fpdf import FPDF, FontFace

from ilovestock.export import NOTICE, SOURCES

LOGO = Path(__file__).with_name("logo.png")  # white-background version, for white pages
PRIMARY = (11, 61, 98)  # brand-guidelines.md
MUTED = (110, 120, 130)
STATUS = {"PASS": (46, 158, 91), "FAIL": (192, 57, 43)}  # N/D: muted
ASCII = str.maketrans({"→": "->", "≥": ">=", "≤": "<=", "–": "-", "—": "-", "…": "...", "’": "'"})
SUMMARY = ("Ticker", "Verdict", "Analyzed", "Data date", "Price", "Entry", "Stop", "Target",
           "Shares", "Fundamental", "Technical")  # fmt: skip
CRITERIA = ("Criterion", "Value", "Threshold", "Status", "Note")


def _t(x) -> str:
    """Text for the core font; None -> N/D."""
    s = "N/D" if x is None else str(x)
    return s.translate(ASCII).encode("latin-1", "replace").decode("latin-1")


def _n(x: float | None) -> str:
    return "N/D" if x is None else f"{x:.2f}"


def _when(iso: str) -> str:
    return iso[:16].replace("T", " ")


def split(criteria: list[dict]) -> tuple[list[dict], list[dict]]:
    """Fundamental (up to "Next earnings") and technical criteria, as web/src/format.ts groups()."""
    i = next((i + 1 for i, c in enumerate(criteria) if c["name"] == "Next earnings"), 0)
    return criteria[:i], criteria[i:]


def _passed(items: list[dict]) -> str:
    return f"{sum(c['status'] == 'PASS' for c in items)}/{len(items)}"


class _PDF(FPDF):
    def header(self):
        # brand-guidelines.md: the logo always sits top left.
        self.image(LOGO, x=self.l_margin, y=8, h=12)
        self.set_y(23)

    def footer(self):
        self.set_y(-12)
        self.set_font("helvetica", size=7)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{_t(NOTICE)}   Page {self.page_no()}/{{nb}}", align="C")


def _heading(pdf: FPDF, text: str, size: int) -> None:
    pdf.set_font("helvetica", "B", size)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, size * 0.6, _t(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0)


def _line(pdf: FPDF, text: str) -> None:
    pdf.multi_cell(0, 5, _t(text), new_x="LMARGIN", new_y="NEXT")


def _table(pdf, headings, rows, widths, align=None, status_col=None) -> None:
    head = FontFace(emphasis="BOLD", color=255, fill_color=PRIMARY)
    with pdf.table(
        col_widths=widths, text_align=align or "LEFT", headings_style=head, line_height=5
    ) as table:
        table.row(headings)
        for cells in rows:
            row = table.row()
            for i, text in enumerate(cells):
                color = STATUS.get(text, MUTED) if i == status_col else None
                row.cell(_t(text), style=FontFace(color=color) if color else None)


def render(rows: list[dict], title: str, now: datetime) -> bytes:
    pdf = _PDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(f"iLoveStock {title}")
    pdf.add_page()
    _heading(pdf, f"iLoveStock: {title}", 16)
    _line(pdf, f"Generated {now:%Y-%m-%d %H:%M}, latest saved analysis of {len(rows)} tickers")
    pdf.set_font(style="B")
    _line(pdf, NOTICE)
    pdf.set_font(style="")
    for s in SOURCES:
        _line(pdf, f"Source: {s}")
    pdf.ln(3)
    summary = []
    for r in rows:
        fund, tech = split(r["criteria"])
        summary.append(
            [r["ticker"], r["verdict"], _when(r["analyzed_at"]), r["data_date"]]
            + [_n(r[k]) for k in ("price", "entry", "stop", "target")]
            + [r["shares"], _passed(fund), _passed(tech)]
        )
    widths = (22, 22, 32, 24, 22, 22, 22, 22, 18, 35, 36)
    _table(pdf, SUMMARY, summary, widths, ("LEFT",) * 4 + ("RIGHT",) * 5 + ("LEFT",) * 2)

    for r in rows:
        pdf.add_page()
        _heading(pdf, f"{r['ticker']}: {r['verdict']}", 14)
        _line(
            pdf,
            f"Analyzed {_when(r['analyzed_at'])}, data as of {_t(r['data_date'])},"
            f" price {_n(r['price'])}",
        )
        for name, items in zip(("Fundamental", "Technical"), split(r["criteria"]), strict=True):
            pdf.ln(2)
            _heading(pdf, name, 11)
            cells = [
                [c["name"], c["value"], c["threshold"], c["status"], c["note"] or ""] for c in items
            ]
            _table(pdf, CRITERIA, cells, (55, 50, 45, 20, 107), status_col=3)
        pdf.ln(2)
        _heading(pdf, "Trade plan", 11)
        _line(
            pdf,
            f"Entry {_n(r['entry'])}, stop {_n(r['stop'])}, target {_n(r['target'])},"
            f" shares {_t(r['shares'])}",
        )
        note = [r["note"]] if r["note"] else []
        for heading, lines in (("Reasons", r["reasons"]), ("Note", note)):
            if lines:
                pdf.ln(2)
                _heading(pdf, heading, 11)
                for text in lines:
                    _line(pdf, text)
    return bytes(pdf.output())
