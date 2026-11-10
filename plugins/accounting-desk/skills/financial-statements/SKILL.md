---
name: financial-statements
description: Produce and explain the trial balance, income statement (profit and loss), balance sheet and account ledgers from the Accounting Desk books, plus ratios and period comparisons. Use when the user asks how the business is doing, for a P&L or balance sheet, for an account's history, or for financial ratios.
---

# Financial statements

Every figure you give comes from the ledger tool's output for the stated dates; never estimate or carry numbers over from earlier in the conversation, since the books may have changed.

Ledger tool: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py"`. Add `--json` to any report when you need to calculate from it.

| Report | Command | Must print |
| --- | --- | --- |
| Trial balance | `acct.py trial-balance --as-of <date>` | `In balance.` |
| Income statement | `acct.py income-statement --from <start> --to <end>` | |
| Balance sheet | `acct.py balance-sheet --as-of <date>` | `Balances.` |
| Account ledger | `acct.py ledger --account <code> --from <start> --to <end>` | |

The tool refuses to report on books that fail validation. If a report doesn't print the required line, stop and investigate instead of presenting it.

## Presenting

- State the period, the currency (`currency` in `.accounting-desk.json`), and whether the period is locked (final) or still open (preliminary).
- Lead with what matters: revenue, net income, cash, and anything unusual. Then show the statement.
- Before the year-end closing entry, the balance sheet shows "Earnings not yet closed" in equity. That is expected.

## Analysis

Calculate from `--json` output with a short script rather than by hand, and show the formula:

- Gross margin = (revenue - cost of goods sold) / revenue
- Net margin = net income / revenue
- Current ratio = current assets / current liabilities (ask the user which accounts are current if the chart doesn't make it obvious)
- Period comparison: run the same report for both periods and show the change and percentage change for each line.

These are management reports from the books, not audited financial statements.
