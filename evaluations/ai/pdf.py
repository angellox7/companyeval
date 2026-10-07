"""Render a stored partner assessment as a letter-size PDF."""

import logging
import re
from pathlib import Path


def _agent_log(hypothesis_id, location, message, data):
    # #region agent log
    import json
    import time

    try:
        with open(
            r"C:\Users\angel\Documents\Projects\companyeval\debug-a6cd56.log",
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "a6cd56",
                        "runId": "pre-fix",
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion

logging.getLogger("fontTools.subset").setLevel(logging.ERROR)

from fpdf import FPDF

MARGIN_MM = 12.7
_SEGOE = Path(r"C:\Windows\Fonts\segoeui.ttf")
_SEGOE_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")
_LATIN_REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u00a0": " ",
    "\u00b7": " - ",
    "\u2022": "-",
}


def assessment_filename(company_name):
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', "", company_name or "").strip()
    return f"{cleaned or 'assessment'}-assessment.pdf"


def _latin1(text):
    cleaned = text or ""
    for source, dest in _LATIN_REPLACEMENTS.items():
        cleaned = cleaned.replace(source, dest)
    return cleaned.encode("latin-1", errors="replace").decode("latin-1")


class _MemoPDF(FPDF):
    def __init__(self):
        # #region agent log
        import fpdf as _fpdf_mod
        import inspect

        _font_byte = None
        if _SEGOE.is_file():
            _font_byte = _SEGOE.read_bytes()[39:40].hex()
        _agent_log(
            "A",
            "pdf.py:_MemoPDF.__init__",
            "fpdf module and font header byte",
            {
                "version": getattr(_fpdf_mod, "__version__", None),
                "file": getattr(_fpdf_mod, "__file__", None),
                "add_font_params": list(inspect.signature(FPDF.add_font).parameters),
                "segoe_exists": _SEGOE.is_file(),
                "segoe_bold_exists": _SEGOE_BOLD.is_file(),
                "segoe_byte_39": _font_byte,
            },
        )
        # #endregion
        super().__init__(format="letter", unit="mm")
        self.set_auto_page_break(auto=True, margin=MARGIN_MM)
        self.set_margins(MARGIN_MM, MARGIN_MM, MARGIN_MM)
        self.unicode_font = _SEGOE.is_file() and _SEGOE_BOLD.is_file()
        # #region agent log
        _agent_log(
            "B",
            "pdf.py:_MemoPDF.__init__",
            "font branch selected",
            {"unicode_font": self.unicode_font},
        )
        # #endregion
        if self.unicode_font:
            try:
                self.add_font("Memo", "", str(_SEGOE))
                self.add_font("Memo", "B", str(_SEGOE_BOLD))
            except Exception as exc:
                # #region agent log
                import traceback

                _agent_log(
                    "A",
                    "pdf.py:add_font",
                    "add_font failed",
                    {
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                )
                # #endregion
                raise
            self.family = "Memo"
        else:
            self.family = "Helvetica"

    def prepare(self, text):
        text = "" if text is None else str(text)
        if self.unicode_font:
            return text
        return _latin1(text)

    def use(self, style="", size=9):
        self.set_font(self.family, style, size)

    def paragraph(self, text, size=9, style="", color=(30, 30, 30)):
        self.use(style, size)
        self.set_text_color(*color)
        self.set_x(self.l_margin)
        self.multi_cell(
            0,
            size * 0.48,
            self.prepare(text),
            new_x="LMARGIN",
            new_y="NEXT",
        )

    def cited(self, text, number, size=9):
        self.use("", size)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.write(size * 0.48, self.prepare(text))
        if number is not None:
            self.char_vpos = "SUP"
            self.use("", max(size - 3, 6))
            self.write(size * 0.48, str(number))
            self.char_vpos = "LINE"
        self.ln(size * 0.55)

    def rule(self):
        self.ln(1.2)
        self.set_draw_color(210, 210, 210)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(1.6)


def _score_line(report):
    evaluation = report.evaluation
    if evaluation.composite is None:
        return "No composite yet"
    if evaluation.complete:
        return f"{evaluation.composite_display} · {evaluation.screen_label}"
    return (
        f"{evaluation.composite_display} · Partial · "
        f"{evaluation.scored_count} of {evaluation.factor_count} factors"
    )


def render_assessment_pdf(deal, report, memo):
    pdf = _MemoPDF()
    # #region agent log
    _agent_log(
        "D",
        "pdf.py:render_assessment_pdf",
        "pdf object created",
        {"family": pdf.family, "memo_sections": len(memo.get("sections", []))},
    )
    # #endregion
    pdf.add_page()
    pdf.paragraph(
        f"Partner assessment · {deal.get_sector_display()}",
        size=8,
        color=(90, 96, 104),
    )
    pdf.paragraph(deal.company_name, size=16, style="B", color=(20, 20, 20))
    if (deal.one_liner or "").strip():
        pdf.paragraph(deal.one_liner, size=10, color=(40, 40, 40))
    pdf.paragraph(_score_line(report), size=13, style="B")
    pdf.paragraph(
        "Calculated from the extracted facts and your weights.",
        size=8,
        color=(90, 96, 104),
    )

    for section in memo["sections"]:
        pdf.rule()
        pdf.paragraph(
            f"{section['label']}  {section['running_display']}",
            size=11,
            style="B",
            color=(20, 20, 20),
        )
        pdf.paragraph(section["progress_label"], size=8, color=(90, 96, 104))
        if section["claims"]:
            for item in section["claims"]:
                pdf.cited(item["claim"].body, item["number"])
        else:
            pdf.paragraph(
                "No sourced claim for this category.",
                size=9,
                color=(90, 96, 104),
            )

    pdf.rule()
    pdf.paragraph("Strongest argument against investing", size=11, style="B", color=(20, 20, 20))
    assessment = memo["assessment"]
    if assessment.against_verified:
        pdf.cited(assessment.against_text, memo["against_number"])
    else:
        pdf.paragraph(
            "The strongest argument against investing could not be tied to a source."
        )

    if report.flags or report.benchmark_rows:
        pdf.rule()
        pdf.paragraph("Calculated checks", size=11, style="B", color=(20, 20, 20))
        pdf.paragraph(
            "Calculated from the extracted facts and your weights.",
            size=8,
            color=(90, 96, 104),
        )
        for flag in report.flags:
            pdf.paragraph(f"{flag.severity_label}: {flag.message}", size=9)
        for row in report.benchmark_rows:
            pdf.paragraph(
                f"{row.label}: {row.value_display} · {row.position_label} ({row.band_display})",
                size=9,
            )

    if memo["footnotes"]:
        pdf.rule()
        pdf.paragraph("Sources", size=11, style="B", color=(20, 20, 20))
        for note in memo["footnotes"]:
            pdf.paragraph(
                f"{note['number']}. {note['citation']}. “{note['excerpt']}”",
                size=8,
            )

    try:
        rendered = bytes(pdf.output())
    except Exception as exc:
        # #region agent log
        import traceback

        _agent_log(
            "C",
            "pdf.py:output",
            "pdf.output failed",
            {
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        # #endregion
        raise
    # #region agent log
    _agent_log(
        "C",
        "pdf.py:output",
        "pdf.output succeeded",
        {"byte_len": len(rendered), "header": rendered[:8].hex()},
    )
    # #endregion
    return rendered
