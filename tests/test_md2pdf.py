"""The summary PDF has to survive being opened by someone else.

There is no PDF toolchain on this host, so bin/md2pdf.py writes the file byte
by byte. That means the usual failure is not an exception -- it is a file that
exists, has a plausible size, and opens to garbage. These tests check the
things that actually break: the object table, the text that must appear, and
the inline markup that would otherwise be printed literally.
"""
import re
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import md2pdf  # noqa: E402


def text_of(pdf: bytes) -> str:
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            body = zlib.decompress(m.group(1)).decode("latin-1")
        except Exception:
            continue
        out.extend(re.findall(r"\((.*?)\) Tj", body))
    return " ".join(out)


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.pdf = md2pdf.convert("# Judul\n\nIsi paragraf.\n", "uji")

    def test_it_is_a_pdf_with_a_trailer_and_xref(self):
        self.assertTrue(self.pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"\nxref\n", self.pdf)
        self.assertIn(b"/Root 1 0 R", self.pdf)
        self.assertTrue(self.pdf.rstrip().endswith(b"%%EOF"))

    def test_every_object_offset_points_at_its_object(self):
        # A wrong offset is the classic hand-rolled-PDF bug: readers either
        # repair it silently or refuse the file outright.
        start = self.pdf.index(b"\nxref\n") + len(b"\nxref\n")
        header = self.pdf[start:start + 40].split(b"\n")[0]
        count = int(header.split()[1])
        rows = self.pdf[start:].split(b"\n")[1:count + 1]
        for num, row in enumerate(rows):
            if row.endswith(b"f "):
                continue
            offset = int(row.split()[0])
            self.assertEqual(self.pdf[offset:offset + len(f"{num} 0 obj".encode())],
                             f"{num} 0 obj".encode(), f"object {num} offset is wrong")

    def test_pages_are_counted_and_linked(self):
        pdf = md2pdf.convert("# A\n\n" + ("kalimat panjang. " * 400), "uji")
        count = int(re.search(rb"/Count (\d+)", pdf).group(1))
        self.assertGreater(count, 1)
        self.assertEqual(len(re.findall(rb"/Type /Page[^s]", pdf)), count)


class ContentTests(unittest.TestCase):
    def test_headings_and_body_survive(self):
        body = text_of(md2pdf.convert("# Ringkasan\n\nAsisten ini tidak mengarang.\n"))
        self.assertIn("Ringkasan", body)
        self.assertIn("mengarang", body)

    def test_bold_markers_are_not_printed(self):
        body = text_of(md2pdf.convert("Ini **sangat** penting.\n"))
        self.assertIn("sangat", body)
        self.assertNotIn("**", body)

    def test_code_inside_bold_does_not_print_backticks(self):
        # Caught in the real document: "**menuju cabang `dev`**" rendered the
        # backticks, because the bold alternation matched first.
        body = text_of(md2pdf.convert("hanya menuju **cabang `dev`**.\n"))
        self.assertIn("dev", body)
        self.assertNotIn("`", body)

    def test_bullets_become_dashes_not_asterisks(self):
        body = text_of(md2pdf.convert("* satu\n* dua\n"))
        self.assertIn("satu", body)
        self.assertNotIn("*", body)

    def test_table_rows_are_rendered_without_pipes(self):
        md = "| Nama | Nilai |\n|---|---|\n| Asisten | aktif |\n"
        body = text_of(md2pdf.convert(md))
        self.assertIn("Asisten", body)
        self.assertIn("aktif", body)
        self.assertNotIn("|", body)

    def test_unsupported_glyphs_are_transliterated_not_dropped(self):
        body = text_of(md2pdf.convert("status → aktif ✅ selesai\n"))
        self.assertIn("->", body)
        self.assertIn("[OK]", body)
        self.assertNotIn("?", body)

    def test_footer_names_the_document_and_page(self):
        body = text_of(md2pdf.convert("# X\n\nisi\n", "Platform AI Nexora"))
        self.assertIn("Platform AI Nexora", body)
        self.assertIn("halaman 1 dari 1", body)


class WidthTests(unittest.TestCase):
    def test_no_line_exceeds_the_content_width(self):
        # An underestimated width is what makes words collide on the page.
        long_line = "Pemberitahuan otomatis dikirim setiap Jumat pagi ke Telegram owner"
        for line in md2pdf.wrap_runs(md2pdf.runs(long_line), md2pdf.BODY_SIZE,
                                     md2pdf.CONTENT_W):
            total = sum(md2pdf.width_of(t, md2pdf.BODY_SIZE, f == md2pdf.BOLD)
                        for t, f in line)
            self.assertLessEqual(total, md2pdf.CONTENT_W + 0.5)

    def test_known_helvetica_widths_are_exact(self):
        self.assertAlmostEqual(md2pdf.width_of("I", 1000), 278, places=6)
        self.assertAlmostEqual(md2pdf.width_of("W", 1000), 944, places=6)
        self.assertAlmostEqual(md2pdf.width_of(" ", 1000), 278, places=6)


if __name__ == "__main__":
    unittest.main()
