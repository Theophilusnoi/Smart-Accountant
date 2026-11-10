---
name: bookkeeping
description: Record business transactions as balanced double-entry journal entries in the Accounting Desk CSV books, set up new books, and validate them. Use when the user wants to record a sale, purchase, payment, payroll, owner draw or adjusting entry, set up a chart of accounts, or check that the books are valid.
---

# Bookkeeping

The books are plain CSV files that the ledger tool reads. Never keep balances in your head or in chat: write entries to the journal, then let the tool compute every number.

Ledger tool: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py"` (called `acct.py` below). Run it from the project directory; it finds `.accounting-desk.json` in the current directory or a parent.

## Files

| File | Columns | Notes |
| --- | --- | --- |
| `.accounting-desk.json` | `chart_of_accounts`, `journal`, `currency`, `locked_through` | Paths are relative to this file. |
| chart of accounts | `code,name,type` | `type` is one of asset, liability, equity, revenue, expense. |
| journal | `date,entry_id,account,debit,credit,memo` | One row per line. Dates are `YYYY-MM-DD`. Amounts have at most 2 decimals and no currency symbol. |

No books yet? Run `acct.py init` (creates `books/` and the config without overwriting anything), then tailor the chart of accounts with the user.

## Recording an entry

1. **Understand the transaction.** Confirm date, amount, counterparty, what was exchanged, and whether tax applies. Ask rather than guess when any of these is unclear.
2. **Pick accounts** that already exist in the chart of accounts. If one is missing, propose the new account (code, name, type) and add it to the chart only after the user agrees.
3. **Apply the debit/credit rules.**

   | Type | Increase | Decrease |
   | --- | --- | --- |
   | asset, expense | debit | credit |
   | liability, equity, revenue | credit | debit |

4. **Write the lines.** Use the next unused `entry_id` (the journal uses `JE-001`, `JE-002`, ... unless it already follows another scheme). Every line of one entry shares its `entry_id` and `date`, has exactly one of `debit` or `credit`, and has a memo saying what and who (include invoice or check numbers). Total debits must equal total credits.
5. **Append, don't rewrite.** Add new rows to the end of the journal. Do not edit or delete posted rows to fix a mistake; post a correcting entry instead (reverse the wrong entry, then post the right one), with memos that reference the original `entry_id`.
6. **Validate** with `acct.py validate`. It must print `OK`. If it reports errors, fix them and run it again before telling the user the entry is recorded.

## Common patterns

| Transaction | Debit | Credit |
| --- | --- | --- |
| Sale on credit with sales tax | Accounts Receivable (total) | Revenue (net), Sales Tax Payable (tax) |
| Customer pays invoice | Cash | Accounts Receivable |
| Buy inventory on credit | Inventory | Accounts Payable |
| Pay a supplier | Accounts Payable | Cash |
| Pay an expense now | Expense | Cash |
| Owner invests | Cash | Owner's Equity |
| Depreciation | Depreciation Expense | Accumulated Depreciation |
| Accrue an unpaid expense | Expense | Accrued Liabilities |

## Closed periods

If `locked_through` is set, entries dated on or before it belong to a closed period. Date corrections in the open period. The plugin's hook asks the user before any change to a locked period; do not try to get around it. Only the user can decide to reopen a period (`acct.py lock --through <earlier date> --reopen`).
