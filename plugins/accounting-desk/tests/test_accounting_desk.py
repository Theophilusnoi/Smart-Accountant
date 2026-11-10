"""Tests for the Accounting Desk ledger tool and period-lock hook.

Run from the repository root:  python3 -m unittest discover -s plugins/accounting-desk/tests
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import acct  # noqa: E402

HOOK = os.path.join(ROOT, "hooks", "period_lock.py")
EXAMPLES = os.path.join(ROOT, "examples")


class BooksCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(os.path.join(EXAMPLES, "books"), os.path.join(self.tmp, "books"))
        shutil.copy(os.path.join(EXAMPLES, ".accounting-desk.json"), self.tmp)
        self.journal = os.path.join(self.tmp, "books", "journal.csv")
        self.config = os.path.join(self.tmp, ".accounting-desk.json")
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp)

    def run_acct(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = acct.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def run_json(self, *argv):
        code, out, err = self.run_acct("--json", *argv)
        return code, json.loads(out) if out.strip() else None

    def append(self, text):
        with open(self.journal, "a", encoding="utf-8") as handle:
            handle.write(text)


class LedgerToolTests(BooksCase):
    def test_example_books_validate(self):
        code, data = self.run_json("validate")
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        self.assertEqual(data["entries"], 10)

    def test_trial_balance_balances(self):
        code, data = self.run_json("trial-balance")
        self.assertEqual(code, 0)
        self.assertTrue(data["balanced"])
        self.assertEqual(data["total_debit"], "29320.00")

    def test_income_statement(self):
        code, data = self.run_json("income-statement", "--from", "2026-09-01", "--to", "2026-09-30")
        self.assertEqual(code, 0)
        self.assertEqual(data["total_revenue"], "4000.00")
        self.assertEqual(data["total_expenses"], "3579.00")
        self.assertEqual(data["net_income"], "421.00")

    def test_balance_sheet_balances(self):
        code, data = self.run_json("balance-sheet", "--as-of", "2026-09-30")
        self.assertEqual(code, 0)
        self.assertTrue(data["balanced"])
        self.assertEqual(data["total_assets"], "25741.00")

    def test_ledger_running_balance(self):
        code, data = self.run_json("ledger", "--account", "1000", "--from", "2026-09-15")
        self.assertEqual(code, 0)
        self.assertEqual(data["opening"], "23200.00")
        self.assertEqual(data["closing"], "20691.00")

    def test_reconciliation_ties_out(self):
        code, data = self.run_json("reconcile", "--account", "1000",
                                   "--bank", "books/bank_statement_2026-09.csv",
                                   "--statement-balance", "22096.00")
        self.assertEqual(code, 0)
        self.assertTrue(data["reconciled"])
        self.assertEqual(data["matched"], 5)
        self.assertEqual([b["amount"] for b in data["bank_only"]], ["-15.00"])
        self.assertEqual(sorted(l["entry_id"] for l in data["book_only"]), ["JE-009", "JE-010"])

    def test_reconciliation_reports_difference(self):
        code, data = self.run_json("reconcile", "--account", "1000",
                                   "--bank", "books/bank_statement_2026-09.csv",
                                   "--statement-balance", "22000.00")
        self.assertEqual(code, 1)
        self.assertFalse(data["reconciled"])
        self.assertEqual(data["difference"], "-96.00")

    def test_unbalanced_entry_fails_validation_and_blocks_reports(self):
        self.append("2026-10-01,JE-011,6000,100.00,,Rent\n2026-10-01,JE-011,1000,,90.00,Rent\n")
        code, data = self.run_json("validate")
        self.assertEqual(code, 1)
        self.assertTrue(any("does not balance" in e["message"] for e in data["errors"]))
        code, _, _ = self.run_acct("balance-sheet")
        self.assertEqual(code, 1)

    def test_bad_lines_are_reported(self):
        self.append("2026-13-01,JE-011,6000,5,,x\n"
                    "2026-10-02,JE-012,9999,5,,x\n"
                    "2026-10-02,JE-012,1000,5,5,x\n"
                    "2026-10-03,JE-013,6000,1.234,,x\n")
        code, data = self.run_json("validate")
        self.assertEqual(code, 1)
        messages = " ".join(e["message"] for e in data["errors"])
        self.assertIn("YYYY-MM-DD", messages)
        self.assertIn("not in the chart of accounts", messages)
        self.assertIn("exactly one of debit or credit", messages)
        self.assertIn("more than 2 decimal places", messages)

    def test_audit_flags_duplicates_and_suspense(self):
        with open(os.path.join(self.tmp, "books", "chart_of_accounts.csv"), "a") as handle:
            handle.write("1999,Suspense,asset\n")
        self.append("2026-10-05,JE-011,6000,1800.00,,Rent\n2026-10-05,JE-011,1000,,1800.00,Rent\n"
                    "2026-10-05,JE-012,6000,1800.00,,Rent\n2026-10-05,JE-012,1000,,1800.00,Rent\n"
                    "2026-10-06,JE-013,1999,50.00,,Unknown\n2026-10-06,JE-013,1000,,50.00,Unknown\n")
        code, data = self.run_json("audit")
        self.assertEqual(code, 0)
        checks = {f["check"] for f in data["findings"]}
        self.assertIn("duplicate", checks)
        self.assertIn("suspense-balance", checks)
        self.assertIn("weekend", checks)
        self.assertIn("round-amount", checks)

    def test_lock_moves_forward_but_not_back_without_reopen(self):
        code, _, _ = self.run_acct("lock", "--through", "2026-09-30")
        self.assertEqual(code, 0)
        with open(self.config) as handle:
            self.assertEqual(json.load(handle)["locked_through"], "2026-09-30")
        code, _, err = self.run_acct("lock", "--through", "2026-08-31")
        self.assertEqual(code, 2)
        self.assertIn("--reopen", err)
        code, _, _ = self.run_acct("lock", "--through", "2026-08-31", "--reopen")
        self.assertEqual(code, 0)

    def test_init_creates_books_without_overwriting(self):
        target = tempfile.mkdtemp()
        try:
            os.chdir(target)
            code, _, _ = self.run_acct("init")
            self.assertEqual(code, 0)
            code, _, _ = self.run_acct("validate")
            self.assertEqual(code, 0)
            code, data = self.run_json("init")
            self.assertEqual(data["created"], [])
        finally:
            os.chdir(self.tmp)
            shutil.rmtree(target)

    def test_missing_files_exit_2(self):
        code, _, err = self.run_acct("--journal", "nope.csv", "validate")
        self.assertEqual(code, 2)
        self.assertIn("file not found", err)

    def test_runs_as_script(self):
        result = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "acct.py"), "validate"],
                                cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)


class PeriodLockHookTests(BooksCase):
    def hook(self, tool, tool_input):
        event = {"tool_name": tool, "tool_input": tool_input, "cwd": self.tmp,
                 "hook_event_name": "PreToolUse"}
        result = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        if not result.stdout.strip():
            return None
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "ask")
        return output["permissionDecisionReason"]

    def set_lock(self, date):
        with open(self.config) as handle:
            config = json.load(handle)
        config["locked_through"] = date
        with open(self.config, "w") as handle:
            json.dump(config, handle)

    def current_journal(self):
        with open(self.journal) as handle:
            return handle.read()

    def test_appending_in_open_period_is_silent(self):
        self.set_lock("2026-09-30")
        new = self.current_journal() + "2026-10-01,JE-011,6000,1.00,,x\n2026-10-01,JE-011,1000,,1.00,x\n"
        self.assertIsNone(self.hook("Write", {"file_path": self.journal, "content": new}))

    def test_editing_locked_line_asks(self):
        self.set_lock("2026-09-30")
        reason = self.hook("Edit", {"file_path": self.journal,
                                    "old_string": "2026-09-02,JE-002,6000,1800.00",
                                    "new_string": "2026-09-02,JE-002,6000,1900.00"})
        self.assertIn("locked through 2026-09-30", reason)
        self.assertIn("edits 1 journal line", reason)

    def test_backdated_entry_asks(self):
        self.set_lock("2026-09-30")
        new = self.current_journal() + "2026-09-15,JE-011,6000,1.00,,x\n2026-09-15,JE-011,1000,,1.00,x\n"
        reason = self.hook("Write", {"file_path": "books/journal.csv", "content": new})
        self.assertIn("adds 2 journal line", reason)

    def test_multiedit_deleting_locked_line_asks(self):
        self.set_lock("2026-09-30")
        reason = self.hook("MultiEdit", {"file_path": self.journal, "edits": [
            {"old_string": "2026-09-28,JE-008,6200,129.00,,Accounting software - September\n",
             "new_string": ""}]})
        self.assertIn("removes 1 journal line", reason)

    def test_unlocked_books_are_silent(self):
        self.set_lock(None)
        self.assertIsNone(self.hook("Write", {"file_path": self.journal, "content": "date\n"}))

    def test_moving_lock_back_asks_forward_is_silent(self):
        self.set_lock("2026-09-30")
        back = json.dumps({"journal": "books/journal.csv", "locked_through": "2026-08-31"})
        self.assertIn("reopens", self.hook("Write", {"file_path": self.config, "content": back}))
        forward = json.dumps({"journal": "books/journal.csv", "locked_through": "2026-10-31"})
        self.assertIsNone(self.hook("Write", {"file_path": self.config, "content": forward}))

    def test_bash_write_to_journal_asks_read_is_silent(self):
        self.set_lock("2026-09-30")
        self.assertIsNotNone(self.hook("Bash", {"command": "sed -i 's/1800/1900/' books/journal.csv"}))
        self.assertIsNotNone(self.hook("Bash", {"command": "echo x >> books/journal.csv"}))
        self.assertIsNone(self.hook("Bash", {"command": "grep JE-002 books/journal.csv"}))
        self.assertIsNone(self.hook("Bash", {"command": "ls -la"}))

    def test_other_files_and_tools_are_silent(self):
        self.set_lock("2026-09-30")
        self.assertIsNone(self.hook("Write", {"file_path": os.path.join(self.tmp, "notes.md"),
                                              "content": "hi"}))
        self.assertIsNone(self.hook("Read", {"file_path": self.journal}))

    def test_garbage_input_is_silent(self):
        result = subprocess.run([sys.executable, HOOK], input="not json",
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
