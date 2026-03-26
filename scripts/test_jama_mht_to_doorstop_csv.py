#!/usr/bin/env python3
"""Tests for scripts/jama_mht_to_doorstop_csv.py."""

import sys
import os
import unittest

# Allow importing the script from the same directory
sys.path.insert(0, os.path.dirname(__file__))

from jama_mht_to_doorstop_csv import (
    _extract_office_dates,
    _extract_standalone_dates,
    parse_tables,
)


# ---------------------------------------------------------------------------
# _extract_office_dates
# ---------------------------------------------------------------------------


class TestExtractOfficeDates(unittest.TestCase):
    """Tests for _extract_office_dates()."""

    def test_extracts_both_dates(self):
        html = (
            "<html><head>"
            "<o:Created>2026-03-25T05:10:00Z</o:Created>"
            "<o:LastSaved>2026-03-25T05:11:00Z</o:LastSaved>"
            "</head></html>"
        )
        result = _extract_office_dates(html)
        self.assertEqual(result, {
            "created": "2026-03-25T05:10:00Z",
            "modified": "2026-03-25T05:11:00Z",
        })

    def test_extracts_created_only(self):
        html = "<o:Created>2026-01-01T00:00:00Z</o:Created>"
        result = _extract_office_dates(html)
        self.assertEqual(result, {"created": "2026-01-01T00:00:00Z"})

    def test_extracts_last_saved_only(self):
        html = "<o:LastSaved>2026-02-15T12:30:00Z</o:LastSaved>"
        result = _extract_office_dates(html)
        self.assertEqual(result, {"modified": "2026-02-15T12:30:00Z"})

    def test_empty_html_returns_empty_dict(self):
        result = _extract_office_dates("")
        self.assertEqual(result, {})

    def test_no_office_tags_returns_empty_dict(self):
        html = "<html><head><title>No dates here</title></head></html>"
        result = _extract_office_dates(html)
        self.assertEqual(result, {})

    def test_whitespace_around_value_is_stripped(self):
        html = "<o:Created>  2026-03-25T05:10:00Z  </o:Created>"
        result = _extract_office_dates(html)
        self.assertEqual(result["created"], "2026-03-25T05:10:00Z")


# ---------------------------------------------------------------------------
# _extract_standalone_dates
# ---------------------------------------------------------------------------


class TestExtractStandaloneDates(unittest.TestCase):
    """Tests for _extract_standalone_dates()."""

    def test_extracts_created_and_updated(self):
        text = (
            "Some preamble\n"
            "Created: 02/09/2025 09:23:45 PM UTC\n"
            "Updated: 03/23/2026 06:05:49 PM UTC\n"
        )
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {
            "created": "02/09/2025 09:23:45 PM UTC",
            "modified": "03/23/2026 06:05:49 PM UTC",
        })

    def test_modified_label(self):
        text = "Modified: 01/15/2025 10:00:00 AM UTC\n"
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {"modified": "01/15/2025 10:00:00 AM UTC"})

    def test_last_modified_label(self):
        text = "Last Modified: 01/15/2025 10:00:00 AM UTC\n"
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {"modified": "01/15/2025 10:00:00 AM UTC"})

    def test_last_updated_label(self):
        text = "Last Updated: 04/01/2026 08:00:00 AM UTC\n"
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {"modified": "04/01/2026 08:00:00 AM UTC"})

    def test_date_created_label(self):
        text = "Date Created: 06/01/2024 12:00:00 PM UTC\n"
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {"created": "06/01/2024 12:00:00 PM UTC"})

    def test_date_modified_label(self):
        text = "Date Modified: 07/01/2024 12:00:00 PM UTC\n"
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {"modified": "07/01/2024 12:00:00 PM UTC"})

    def test_only_first_occurrence_kept(self):
        text = (
            "Created: 01/01/2025 01:00:00 AM UTC\n"
            "Created: 02/02/2025 02:00:00 AM UTC\n"
        )
        result = _extract_standalone_dates(text)
        # Only the first occurrence should be kept
        self.assertEqual(result["created"], "01/01/2025 01:00:00 AM UTC")

    def test_empty_text_returns_empty_dict(self):
        result = _extract_standalone_dates("")
        self.assertEqual(result, {})

    def test_no_matching_labels_returns_empty_dict(self):
        text = "Nothing to see here.\nJust some random text.\n"
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {})

    def test_case_insensitive(self):
        text = "CREATED: 05/05/2025 05:05:05 AM UTC\n"
        result = _extract_standalone_dates(text)
        self.assertEqual(result, {"created": "05/05/2025 05:05:05 AM UTC"})


# ---------------------------------------------------------------------------
# parse_tables – date handling
# ---------------------------------------------------------------------------

# Requirement table HTML with no date rows but with Office XML dates in head.
_TABLE_NO_DATES = """
<html>
<head>
<o:Created>2026-03-25T05:10:00Z</o:Created>
<o:LastSaved>2026-03-25T05:11:00Z</o:LastSaved>
</head>
<body>
<table>
  <tr><td>Legacy ID</td><td>REQ-001</td></tr>
  <tr><td>Name</td><td>My requirement</td></tr>
  <tr><td>Description</td><td>Some text</td></tr>
</table>
</body>
</html>
"""

# Table WITH a "Created" row — only this per-requirement date should appear.
_TABLE_WITH_DATE_ROW = """
<html>
<head>
<o:Created>2026-03-25T05:10:00Z</o:Created>
<o:LastSaved>2026-03-25T05:11:00Z</o:LastSaved>
</head>
<body>
<table>
  <tr><td>Legacy ID</td><td>REQ-002</td></tr>
  <tr><td>Name</td><td>Another requirement</td></tr>
  <tr><td>Description</td><td>More text</td></tr>
  <tr><td>Created</td><td>01/01/2020 00:00:00 AM UTC</td></tr>
</table>
</body>
</html>
"""

# Table with standalone date lines outside the table (no table-row dates).
_TABLE_STANDALONE_DATES = """
<html>
<head>
<o:Created>2026-03-25T05:10:00Z</o:Created>
<o:LastSaved>2026-03-25T05:11:00Z</o:LastSaved>
</head>
<body>
Created: 02/09/2025 09:23:45 PM UTC
Updated: 03/23/2026 06:05:49 PM UTC
<table>
  <tr><td>Legacy ID</td><td>REQ-003</td></tr>
  <tr><td>Name</td><td>Third requirement</td></tr>
  <tr><td>Description</td><td>Even more text</td></tr>
</table>
</body>
</html>
"""


class TestParseTablesDates(unittest.TestCase):
    """Tests for date handling in parse_tables()."""

    def test_office_xml_dates_not_injected_into_requirements(self):
        """Office XML <o:Created>/<o:LastSaved> must NOT appear in records."""
        records = parse_tables(_TABLE_NO_DATES)
        self.assertEqual(len(records), 1)
        rec = records[0]
        # No date row in the table and no standalone dates → created/modified absent
        self.assertNotIn("created", rec)
        self.assertNotIn("modified", rec)
        # The Office XML export timestamp must not leak in
        self.assertNotEqual(rec.get("created"), "2026-03-25T05:10:00Z")
        self.assertNotEqual(rec.get("modified"), "2026-03-25T05:11:00Z")

    def test_table_row_date_is_captured(self):
        """Per-requirement date rows inside the table ARE captured."""
        records = parse_tables(_TABLE_WITH_DATE_ROW)
        self.assertEqual(len(records), 1)
        rec = records[0]
        # The table row "Created" value must be present
        self.assertEqual(rec["created"], "01/01/2020 00:00:00 AM UTC")
        # Office XML date must not replace the table-row date
        self.assertNotEqual(rec["created"], "2026-03-25T05:10:00Z")

    def test_standalone_dates_used_as_fallback(self):
        """Standalone date text outside tables IS used when no table-row dates exist."""
        records = parse_tables(_TABLE_STANDALONE_DATES)
        self.assertEqual(len(records), 1)
        rec = records[0]
        # Standalone dates should be captured as fallback
        self.assertEqual(rec["created"], "02/09/2025 09:23:45 PM UTC")
        self.assertEqual(rec["modified"], "03/23/2026 06:05:49 PM UTC")

    def test_table_row_date_takes_priority_over_standalone(self):
        """Table-row dates win over standalone dates when both are present."""
        html = """
        <html><body>
        Created: 01/01/2000 00:00:00 AM UTC
        Updated: 01/01/2000 00:00:00 AM UTC
        <table>
          <tr><td>Legacy ID</td><td>REQ-010</td></tr>
          <tr><td>Name</td><td>Priority test</td></tr>
          <tr><td>Description</td><td>Text</td></tr>
          <tr><td>Created</td><td>02/09/2025 09:23:45 PM UTC</td></tr>
        </table>
        </body></html>
        """
        records = parse_tables(html)
        self.assertEqual(len(records), 1)
        rec = records[0]
        # Table row date must win over the standalone fallback
        self.assertEqual(rec["created"], "02/09/2025 09:23:45 PM UTC")

    def test_standalone_fills_missing_field_when_table_has_partial_dates(self):
        """Standalone fills the missing field even when the table supplies the other."""
        html = """
        <html><body>
        Created: 01/01/2000 00:00:00 AM UTC
        Updated: 05/05/2025 08:00:00 AM UTC
        <table>
          <tr><td>Legacy ID</td><td>REQ-011</td></tr>
          <tr><td>Name</td><td>Partial date test</td></tr>
          <tr><td>Description</td><td>Text</td></tr>
          <tr><td>Created</td><td>02/09/2025 09:23:45 PM UTC</td></tr>
        </table>
        </body></html>
        """
        records = parse_tables(html)
        self.assertEqual(len(records), 1)
        rec = records[0]
        # Table row date for 'created' must win
        self.assertEqual(rec["created"], "02/09/2025 09:23:45 PM UTC")
        # 'modified' was not in the table, so standalone fallback must apply
        self.assertEqual(rec["modified"], "05/05/2025 08:00:00 AM UTC")

    def test_no_dates_when_table_has_no_date_rows_and_no_standalone(self):
        """When a requirement table has no date rows and no standalone dates, fields are absent."""
        html = """
        <html><body>
        <table>
          <tr><td>Legacy ID</td><td>REQ-004</td></tr>
          <tr><td>Name</td><td>Req four</td></tr>
          <tr><td>Description</td><td>Text</td></tr>
        </table>
        </body></html>
        """
        records = parse_tables(html)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertNotIn("created", rec)
        self.assertNotIn("modified", rec)

    def test_multiple_requirements_each_get_their_own_dates(self):
        """Different requirement tables each get the standalone dates from their own preceding text."""
        html = """
        <html><body>
        Created: 02/09/2025 09:23:45 PM UTC  Updated: 03/23/2026 06:05:49 PM UTC
        <table>
          <tr><td>Legacy ID</td><td>SYS-001</td></tr>
          <tr><td>Name</td><td>System Requirement 1</td></tr>
          <tr><td>Description</td><td>The system shall do X</td></tr>
        </table>
        Created: 03/15/2025 10:30:00 AM UTC  Updated: 03/25/2026 02:15:30 PM UTC
        <table>
          <tr><td>Legacy ID</td><td>SYS-002</td></tr>
          <tr><td>Name</td><td>System Requirement 2</td></tr>
          <tr><td>Description</td><td>The system shall do Y</td></tr>
        </table>
        </body></html>
        """
        records = parse_tables(html)
        self.assertEqual(len(records), 2)
        # First requirement
        rec1 = next(r for r in records if r.get("legacy_id") == "SYS-001")
        self.assertEqual(rec1["created"], "02/09/2025 09:23:45 PM UTC")
        self.assertEqual(rec1["modified"], "03/23/2026 06:05:49 PM UTC")
        # Second requirement — different timestamps
        rec2 = next(r for r in records if r.get("legacy_id") == "SYS-002")
        self.assertEqual(rec2["created"], "03/15/2025 10:30:00 AM UTC")
        self.assertEqual(rec2["modified"], "03/25/2026 02:15:30 PM UTC")
        # Dates must differ between the two records
        self.assertNotEqual(rec1["created"], rec2["created"])
        self.assertNotEqual(rec1["modified"], rec2["modified"])


if __name__ == "__main__":
    unittest.main()
