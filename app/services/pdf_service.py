"""
services/pdf_service.py
------------------------
Converts Markdown report to a properly formatted scientific PDF using ReportLab.
Fixed: tables now render correctly with proper column widths.
"""

import logging, re
from pathlib import Path
from datetime import datetime
from app.config.settings import REPORTS_DIR

logger = logging.getLogger(__name__)


class PDFService:

    def generate(self, markdown_text: str, uniprot_id: str) -> str:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer,
                HRFlowable, Table, TableStyle, KeepTogether
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{uniprot_id}_report_{timestamp}.pdf"
            output_path = REPORTS_DIR / filename

            doc = SimpleDocTemplate(
                str(output_path), pagesize=A4,
                rightMargin=2*cm, leftMargin=2*cm,
                topMargin=2.5*cm, bottomMargin=2*cm,
            )

            styles = getSampleStyleSheet()

            title_style = ParagraphStyle("ReportTitle", parent=styles["Title"],
                fontSize=20, textColor=colors.HexColor("#1a3a5c"),
                spaceAfter=6, alignment=TA_CENTER)
            subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"],
                fontSize=10, textColor=colors.HexColor("#5a6a7a"),
                spaceAfter=16, alignment=TA_CENTER)
            h1_style = ParagraphStyle("H1", parent=styles["Heading1"],
                fontSize=15, textColor=colors.HexColor("#1a3a5c"),
                spaceBefore=18, spaceAfter=8)
            h2_style = ParagraphStyle("H2", parent=styles["Heading2"],
                fontSize=12, textColor=colors.HexColor("#2c5f8a"),
                spaceBefore=12, spaceAfter=6)
            h3_style = ParagraphStyle("H3", parent=styles["Heading3"],
                fontSize=11, textColor=colors.HexColor("#3a7abf"),
                spaceBefore=10, spaceAfter=4)
            body_style = ParagraphStyle("Body", parent=styles["Normal"],
                fontSize=9, leading=14, alignment=TA_JUSTIFY, spaceAfter=6)
            bullet_style = ParagraphStyle("Bullet", parent=styles["Normal"],
                fontSize=9, leading=13, leftIndent=16, spaceAfter=3)
            badge_style = ParagraphStyle("Badge", parent=styles["Normal"],
                fontSize=10, leading=14, textColor=colors.HexColor("#1a3a5c"),
                backColor=colors.HexColor("#e8f0fe"), borderPad=6,
                spaceAfter=12, alignment=TA_CENTER)
            footer_style = ParagraphStyle("Footer", parent=styles["Normal"],
                fontSize=7, textColor=colors.grey, alignment=TA_CENTER)

            story = []

            # Cover header
            story.append(Paragraph("Agentic Bioinformatics Research Assistant", subtitle_style))
            story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a3a5c")))
            story.append(Spacer(1, 0.3*cm))

            lines = markdown_text.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Skip empty
                if not line:
                    story.append(Spacer(1, 0.15*cm))
                    i += 1
                    continue

                # Badge line (starts with >)
                if line.startswith("> "):
                    badge_text = line[2:].replace("**", "").replace("🔴", "").replace("📊", "").replace("🏗️", "").replace("⚡", "").replace("💊", "")
                    story.append(Paragraph(f"🔬 {badge_text}", badge_style))
                    i += 1
                    continue

                # H1
                if line.startswith("# "):
                    text = self._sanitize(line[2:].strip())
                    story.append(Paragraph(text, title_style))
                    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2c5f8a")))
                    i += 1
                    continue

                # H2
                if line.startswith("## "):
                    text = self._sanitize(line[3:].strip())
                    story.append(Paragraph(text, h1_style))
                    i += 1
                    continue

                # H3
                if line.startswith("### "):
                    text = self._sanitize(line[4:].strip())
                    story.append(Paragraph(text, h2_style))
                    i += 1
                    continue

                # H4
                if line.startswith("#### "):
                    text = self._sanitize(line[5:].strip())
                    story.append(Paragraph(text, h3_style))
                    i += 1
                    continue

                # Horizontal rule
                if line in ("---", "***", "___"):
                    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
                    i += 1
                    continue

                # TABLE — detect markdown table
                if line.startswith("|") and i + 1 < len(lines):
                    table_lines = []
                    j = i
                    while j < len(lines) and lines[j].strip().startswith("|"):
                        table_lines.append(lines[j].strip())
                        j += 1

                    table_element = self._build_table(table_lines)
                    if table_element:
                        story.append(table_element)
                        story.append(Spacer(1, 0.3*cm))
                    i = j
                    continue

                # Bullet
                if line.startswith("- ") or line.startswith("* "):
                    text = self._sanitize(line[2:].strip())
                    story.append(Paragraph(f"• {text}", bullet_style))
                    i += 1
                    continue

                # Numbered list
                if re.match(r"^\d+\. ", line):
                    text = self._sanitize(line)
                    story.append(Paragraph(text, bullet_style))
                    i += 1
                    continue

                # Regular paragraph
                story.append(Paragraph(self._sanitize(line), body_style))
                i += 1

            # Footer
            story.append(Spacer(1, 0.5*cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
            story.append(Paragraph(
                f"Generated by Agentic Bioinformatics Research Assistant | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                footer_style))

            doc.build(story)
            logger.info("PDF saved: %s", output_path)
            return str(output_path)

        except ImportError:
            logger.error("ReportLab not installed")
            raise
        except Exception as exc:
            logger.error("PDF generation failed: %s", exc)
            raise

    def _build_table(self, table_lines: list) -> object:
        """Build a properly formatted ReportLab table from markdown table lines."""
        try:
            from reportlab.platypus import Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.units import cm

            rows = []
            is_header_row = True

            for line in table_lines:
                # Skip separator rows (---|---|---)
                if re.match(r"^\|[\s\-\|:]+\|$", line):
                    continue

                cells = [cell.strip() for cell in line.strip("|").split("|")]
                cells = [self._sanitize(c) for c in cells]

                if is_header_row:
                    rows.append(cells)
                    is_header_row = False
                else:
                    rows.append(cells)

            if not rows or len(rows) < 1:
                return None

            # Calculate column widths based on page width
            from reportlab.lib.pagesizes import A4
            page_width = A4[0] - 4*cm  # subtract margins
            num_cols = max(len(row) for row in rows)

            # Normalize all rows to same column count
            for row in rows:
                while len(row) < num_cols:
                    row.append("")

            col_width = page_width / num_cols

            # Build table
            table = Table(rows, colWidths=[col_width] * num_cols, repeatRows=1)
            table.setStyle(TableStyle([
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                # Data rows
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.HexColor("#f8fafc"), colors.HexColor("#edf2f7")]),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#2c5f8a")),
            ]))
            return table

        except Exception as exc:
            logger.warning("Table build failed: %s", exc)
            return None

    @staticmethod
    def _sanitize(text: str) -> str:
        """Convert markdown to ReportLab-safe XML."""
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        # Code
        text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
        # Links — show text only
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        # Bare ampersands
        text = re.sub(r"&(?!amp;|lt;|gt;|quot;|#)", "&amp;", text)
        # Remove emojis that ReportLab can't render
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F9FF"
            u"\U00002600-\U000027BF"
            u"\U0001F1E0-\U0001F1FF"
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub("", text)
        return text.strip()


pdf_service = PDFService()