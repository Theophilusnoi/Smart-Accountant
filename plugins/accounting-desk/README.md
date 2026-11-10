# Accounting Desk

A Claude Code plugin that turns Claude into a small accounting team for Smart-Accountant. Six specialist agents share skills and slash commands for bookkeeping, bank reconciliation, month-end close, financial statements, tax preparation and audit review. Every number comes from `scripts/acct.py`, a ledger tool that uses only the Python standard library and works on plain CSV books, so results are exact and reproducible. A hook asks you before anything changes a closed period.

## Install

The repository is its own marketplace. Its `.claude/settings.json` already enables the plugin, so Claude Code offers to install it when you open the repo and trust it. Anywhere else:

```
/plugin marketplace add Theophilusnoi/Smart-Accountant
/plugin install accounting-desk@smart-accountant
```

Requires `python3` (3.8 or later) on the PATH.

## Quick start

```
/accounting-desk:setup-books                 create books/ and .accounting-desk.json
/accounting-desk:reconcile statement.csv     reconcile a bank statement
/accounting-desk:close-month 2026-09         run the close checklist, then lock the month
/accounting-desk:review-books                independent audit-style review
```

Or just ask: "record a $1,200 invoice to Brightline Co with 8% sales tax", "how did we do in September?", "prepare my Q3 sales tax return".

## What's inside

| Part | Contents |
| --- | --- |
| Agents | `controller` (lead), `bookkeeper`, `reconciliation-specialist`, `financial-analyst`, `tax-preparer`, `auditor` (read-only) |
| Skills | `bookkeeping`, `bank-reconciliation`, `month-end-close`, `financial-statements`, `tax-preparation`, `audit-review` |
| Commands | `setup-books`, `reconcile`, `close-month`, `review-books` |
| Hook | `period_lock.py`: asks before Write, Edit, MultiEdit or Bash changes a journal line dated on or before `locked_through`, or moves the lock back |
| Tool | `acct.py`: `init`, `validate`, `trial-balance`, `ledger`, `income-statement`, `balance-sheet`, `reconcile`, `audit`, `lock` (add `--json` to any command) |

## Books format

```
.accounting-desk.json   {"chart_of_accounts": "books/chart_of_accounts.csv", "journal": "books/journal.csv",
                         "currency": "USD", "locked_through": "2026-08-31"}
chart_of_accounts.csv   code,name,type        (asset | liability | equity | revenue | expense)
journal.csv             date,entry_id,account,debit,credit,memo
bank statement          date,description,amount   or   date,description,deposit,withdrawal
```

`examples/` has a complete September 2026 set. Try it:

```
cd plugins/accounting-desk/examples
python3 ../scripts/acct.py validate
python3 ../scripts/acct.py reconcile --account 1000 --bank books/bank_statement_2026-09.csv --statement-balance 22096.00
```

## Tests

```
python3 -m unittest discover -s plugins/accounting-desk/tests
```

## Limits

The desk prepares management accounts and tax workpapers. It doesn't file returns, sign audit opinions, or replace a qualified accountant's judgment.
