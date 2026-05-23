from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "故障演化采样系统算法设计图说明.md"
IMAGE_PATH = ROOT / "docs" / "figures" / "fault_evolution_algorithm_design_cn.png"
OUT_PATH = ROOT / "docs" / "故障演化采样系统算法设计图说明.docx"


def set_run_font(run, name: str = "微软雅黑", size: int | None = None, bold: bool | None = None) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def set_paragraph_spacing(paragraph, before: int = 0, after: int = 6, line: float = 1.15) -> None:
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = line


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_text(cell, text: str, *, bold: bool = False, color: RGBColor | None = None) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if bold else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, size=10, bold=bold)
    if color is not None:
        run.font.color.rgb = color
    set_paragraph_spacing(p, after=0, line=1.05)


def add_markdown_text(paragraph, text: str, *, base_size: int = 10.5, bold_all: bool = False) -> None:
    # Basic inline code / emphasis handling, intentionally small and predictable.
    tokens = re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", text)
    for token in tokens:
        if not token:
            continue
        if token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, name="Consolas", size=base_size, bold=bold_all)
            run.font.color.rgb = RGBColor(15, 118, 110)
        elif token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size=base_size, bold=True)
        else:
            run = paragraph.add_run(token)
            set_run_font(run, size=base_size, bold=bold_all)


def add_code_block(doc: Document, lines: list[str]) -> None:
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=2, after=8, line=1.0)
    p.paragraph_format.left_indent = Cm(0.5)
    for i, line in enumerate(lines):
        if i:
            p.add_run("\n")
        run = p.add_run(line)
        set_run_font(run, name="Consolas", size=9)
        run.font.color.rgb = RGBColor(30, 41, 59)
    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F1F5F9")
    p_pr.append(shd)


def add_table_from_markdown(doc: Document, block: list[str]) -> None:
    rows = []
    for line in block:
        line = line.strip()
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", part or "") for part in parts):
            continue
        rows.append(parts)
    if not rows:
        return

    cols = max(len(row) for row in rows)
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    table.autofit = True
    for r_idx, row in enumerate(rows):
        for c_idx in range(cols):
            text = row[c_idx] if c_idx < len(row) else ""
            cell = table.cell(r_idx, c_idx)
            if r_idx == 0:
                shade_cell(cell, "0F766E")
                set_cell_text(cell, text, bold=True, color=RGBColor(255, 255, 255))
            else:
                if r_idx % 2 == 0:
                    shade_cell(cell, "F8FAFC")
                set_cell_text(cell, text)
    doc.add_paragraph()


def add_title_page(doc: Document) -> None:
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(title, before=8, after=4, line=1.1)
    run = title.add_run("故障演化采样系统算法设计图说明")
    set_run_font(run, size=22, bold=True)
    run.font.color.rgb = RGBColor(31, 41, 55)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(subtitle, after=12)
    run = subtitle.add_run("面向 PPT 展示与答辩讲解整理版")
    set_run_font(run, size=12)
    run.font.color.rgb = RGBColor(100, 116, 139)

    if IMAGE_PATH.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(str(IMAGE_PATH), width=Inches(10.3))
        set_paragraph_spacing(p, after=4)
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(cap, after=12)
        r = cap.add_run("图 1  故障演化采样系统算法设计图")
        set_run_font(r, size=10)
        r.font.color.rgb = RGBColor(100, 116, 139)


def convert_markdown(doc: Document, text: str) -> None:
    lines = text.splitlines()
    i = 0
    in_code = False
    code_lines: list[str] = []
    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith("```"):
            if in_code:
                add_code_block(doc, code_lines)
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        if not line.strip():
            i += 1
            continue

        if line.strip() == "---":
            p = doc.add_paragraph()
            set_paragraph_spacing(p, before=4, after=4)
            run = p.add_run("—" * 48)
            set_run_font(run, size=8)
            run.font.color.rgb = RGBColor(203, 213, 225)
            i += 1
            continue

        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            add_table_from_markdown(doc, block)
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            content = heading.group(2).strip()
            if level == 1:
                # The document already has a title page.
                i += 1
                continue
            style = f"Heading {min(level, 4)}"
            p = doc.add_paragraph(style=style)
            set_paragraph_spacing(p, before=8 if level <= 2 else 4, after=4)
            run = p.add_run(content)
            set_run_font(run, size={2: 15, 3: 13, 4: 11}.get(level, 10), bold=True)
            if level <= 2:
                run.font.color.rgb = RGBColor(15, 118, 110)
            i += 1
            continue

        if line.startswith(">"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            set_paragraph_spacing(p, before=3, after=6)
            add_markdown_text(p, line.lstrip("> ").strip(), base_size=11, bold_all=True)
            for run in p.runs:
                run.font.color.rgb = RGBColor(15, 118, 110)
            i += 1
            continue

        bullet = re.match(r"^-\s+(.+)$", line)
        if bullet:
            p = doc.add_paragraph(style="List Bullet")
            set_paragraph_spacing(p, after=2, line=1.08)
            add_markdown_text(p, bullet.group(1), base_size=10.5)
            i += 1
            continue

        numbered = re.match(r"^\d+\.\s+(.+)$", line)
        if numbered:
            p = doc.add_paragraph(style="List Number")
            set_paragraph_spacing(p, after=2, line=1.08)
            add_markdown_text(p, numbered.group(1), base_size=10.5)
            i += 1
            continue

        # Skip the two raw asset links at the top; the image is inserted explicitly.
        if line.strip().startswith("- PNG 版:") or line.strip().startswith("- SVG 版:"):
            i += 1
            continue

        p = doc.add_paragraph()
        set_paragraph_spacing(p, after=5, line=1.15)
        add_markdown_text(p, line, base_size=10.5)
        i += 1

    if code_lines:
        add_code_block(doc, code_lines)


def setup_document() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Cm(1.3)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.4)
    section.right_margin = Cm(1.4)

    styles = doc.styles
    styles["Normal"].font.name = "微软雅黑"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    styles["Normal"].font.size = Pt(10.5)
    for style_name in ("Heading 1", "Heading 2", "Heading 3", "Heading 4"):
        style = styles[style_name]
        style.font.name = "微软雅黑"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    return doc


def main() -> None:
    doc = setup_document()
    add_title_page(doc)
    text = MD_PATH.read_text(encoding="utf-8")
    convert_markdown(doc, text)
    doc.core_properties.title = "故障演化采样系统算法设计图说明"
    doc.core_properties.author = "Codex"
    doc.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
