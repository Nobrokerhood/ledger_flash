from io import BytesIO
import unittest

import pandas as pd

from backend.services.ledger_service import clean_ledger_rows
from backend.services.pdf_parser import parse_ledger_names


class LedgerImportTests(unittest.TestCase):
    def test_reads_only_explicit_ledger_column(self):
        content = b"ledger_id,ledger_name,created_at\n1,Salary,2026-06-13\n2,Wages,2026-06-13\n"

        self.assertEqual(parse_ledger_names(content, "ledgers.csv"), ["Salary", "Wages"])

    def test_single_column_master_is_supported(self):
        content = b"Salary\nWages\nSecurity Charges\n"

        self.assertEqual(
            parse_ledger_names(content, "ledgers.csv"),
            ["Salary", "Wages", "Security Charges"],
        )

    def test_statement_uses_account_name_not_metadata_or_dates(self):
        frame = pd.DataFrame([
            ["STATEMENT OF ACCOUNT", ""],
            ["Society Name-Quality Gardenia Owners Association", ""],
            ["Account Name-Security salary", ""],
            ["Date", "Particulars"],
            ["2025-04-11 00:00:00", "SECURITY SALARY PAID"],
        ])
        buffer = BytesIO()
        frame.to_excel(buffer, index=False, header=False)

        self.assertEqual(
            parse_ledger_names(buffer.getvalue(), "statement.xlsx"),
            ["Security salary"],
        )

    def test_existing_polluted_rows_are_filtered(self):
        rows = [
            {"ledger_id": "1", "ledger_name": "Society Name-Test Society"},
            {"ledger_id": "2", "ledger_name": "Account Name-Security salary"},
            {"ledger_id": "3", "ledger_name": "Date"},
            {"ledger_id": "4", "ledger_name": "2025-04-11 00:00:00"},
        ]

        self.assertEqual(
            clean_ledger_rows(rows),
            [{"ledger_id": "2", "ledger_name": "Security salary"}],
        )


if __name__ == "__main__":
    unittest.main()
