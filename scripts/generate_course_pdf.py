"""Generate the course manual PDF from Markdown.

This is a lightweight renderer for the project manual. It intentionally keeps
the source of truth in course/paper_rag_agent_project_manual.md and supports
the Markdown features used by that file: headings, paragraphs, bullet/numbered
lists, fenced code blocks, blockquotes, and simple pipe tables.
"""

from __future__ import annotations

import argparse
import html
import re
from collections.abc import Iterable
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MD = ROOT / "course" / "paper_rag_agent_project_manual.md"
DEFAULT_PDF = ROOT / "course" / "paper_rag_agent_project_manual.pdf"
FONT_CANDIDATES = [
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_MD)
    parser.add_argument("--output", type=Path, default=DEFAULT_PDF)
    args = parser.parse_args()

    _register_fonts()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    story = build_story(args.input.read_text(encoding="utf-8"))
    doc = SimpleDocTemplate(
        str(args.output),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title="Paper RAG Agent Project Manual",
        author="paper_rag contributors",
        subject="Course manual for DeepSeek Harness and MCP Agentic RAG project",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def build_story(markdown: str) -> list:
    styles = _styles()
    story: list = []
    lines = markdown.splitlines()
    i = 0
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = " ".join(item.strip() for item in paragraph if item.strip())
        if text:
            story.append(Paragraph(_inline(text), styles["BodyCJK"]))
            story.append(Spacer(1, 4))
        paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped == "---":
            flush_paragraph()
            story.append(Spacer(1, 8))
            i += 1
            continue
        if stripped.startswith("```"):
            flush_paragraph()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            story.append(_code_block("\n".join(code), styles["Code"]))
            story.append(Spacer(1, 6))
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            flush_paragraph()
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            story.append(_table(table_lines, styles["TableCell"], styles["TableHeader"]))
            story.append(Spacer(1, 8))
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            level = min(len(stripped) - len(stripped.lstrip("#")), 4)
            title = stripped[level:].strip()
            if title:
                style_name = f"H{level}" if level <= 3 else "H4"
                if level == 1 and story:
                    story.append(PageBreak())
                story.append(Paragraph(_inline(title), styles[style_name]))
                story.append(Spacer(1, 4))
            i += 1
            continue
        if not stripped:
            flush_paragraph()
            i += 1
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            story.append(Paragraph(_inline(stripped.lstrip("> ").strip()), styles["Quote"]))
            story.append(Spacer(1, 4))
            i += 1
            continue
        bullet = _bullet_text(stripped)
        if bullet:
            flush_paragraph()
            story.append(Paragraph(_inline(bullet), styles["Bullet"]))
            story.append(Spacer(1, 2))
            i += 1
            continue
        paragraph.append(line)
        i += 1

    flush_paragraph()
    return story


def _register_fonts() -> None:
    font_path = next((path for path in FONT_CANDIDATES if path.exists()), None)
    if font_path is None:
        raise RuntimeError("No CJK-capable font found for PDF generation")
    pdfmetrics.registerFont(TTFont("ManualCJK", str(font_path)))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "H1": ParagraphStyle(
            "H1",
            parent=base["Title"],
            fontName="ManualCJK",
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#111827"),
            spaceAfter=8,
        ),
        "H2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="ManualCJK",
            fontSize=15,
            leading=20,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=4,
        ),
        "H3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName="ManualCJK",
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#1f2937"),
            spaceBefore=8,
            spaceAfter=3,
        ),
        "H4": ParagraphStyle(
            "H4",
            parent=base["Heading4"],
            fontName="ManualCJK",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#374151"),
            spaceBefore=6,
            spaceAfter=2,
        ),
        "BodyCJK": ParagraphStyle(
            "BodyCJK",
            parent=base["BodyText"],
            fontName="ManualCJK",
            fontSize=9.4,
            leading=14.2,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "Bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="ManualCJK",
            fontSize=9.1,
            leading=13.4,
            leftIndent=10,
            firstLineIndent=-7,
            wordWrap="CJK",
        ),
        "Quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName="ManualCJK",
            fontSize=9,
            leading=13.5,
            leftIndent=10,
            rightIndent=8,
            textColor=colors.HexColor("#4b5563"),
            backColor=colors.HexColor("#f9fafb"),
            borderColor=colors.HexColor("#e5e7eb"),
            borderWidth=0.5,
            borderPadding=5,
            wordWrap="CJK",
        ),
        "Code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="ManualCJK",
            fontSize=7.6,
            leading=10.2,
            textColor=colors.HexColor("#111827"),
            backColor=colors.HexColor("#f3f4f6"),
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="ManualCJK",
            fontSize=7.4,
            leading=10.2,
            wordWrap="CJK",
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="ManualCJK",
            fontSize=7.6,
            leading=10.4,
            textColor=colors.white,
            wordWrap="CJK",
        ),
    }


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(
        r"`([^`]+)`",
        lambda match: f'<font name="ManualCJK" color="#111827">{match.group(1)}</font>',
        escaped,
    )
    return escaped


def _bullet_text(stripped: str) -> str | None:
    if stripped.startswith("- "):
        return f"• {stripped[2:].strip()}"
    match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
    if match:
        return f"{match.group(1)}. {match.group(2).strip()}"
    return None


def _code_block(code: str, style: ParagraphStyle) -> Preformatted:
    clean = code.rstrip() or " "
    return Preformatted(clean, style, maxLineLength=96, dedent=0)


def _is_table_sep(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _table(lines: list[str], cell_style: ParagraphStyle, header_style: ParagraphStyle) -> LongTable:
    rows = [_split_table_row(line) for line in lines]
    header = rows[0]
    body = rows[2:]
    ncols = max(len(row) for row in [header, *body])
    normalized = [_pad(row, ncols) for row in [header, *body]]
    data = []
    for r_idx, row in enumerate(normalized):
        style = header_style if r_idx == 0 else cell_style
        data.append([Paragraph(_inline(cell.strip()), style) for cell in row])

    page_width = A4[0] - 32 * mm
    col_widths = _column_widths(normalized, page_width)
    table = LongTable(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ffffff")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _pad(row: list[str], ncols: int) -> list[str]:
    return row + [""] * (ncols - len(row))


def _column_widths(rows: Iterable[list[str]], total: float) -> list[float]:
    row_list = list(rows)
    ncols = max(len(row) for row in row_list)
    weights = [1.0] * ncols
    for col in range(ncols):
        max_len = max(len(row[col]) if col < len(row) else 0 for row in row_list)
        weights[col] = min(3.2, max(1.0, max_len / 18))
    weight_sum = sum(weights)
    return [total * weight / weight_sum for weight in weights]


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("ManualCJK", 7.5)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(16 * mm, 9 * mm, "Paper RAG Agent 项目技术手册")
    canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


if __name__ == "__main__":
    main()
