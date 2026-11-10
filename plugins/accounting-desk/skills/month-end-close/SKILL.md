---
name: month-end-close
description: Run the month-end or year-end close for the Accounting Desk books, from reconciliations and accruals to the closing review and locking the period. Use when the user asks to close the month, quarter or year, or asks what still has to happen before the books are final.
---

# Month-end close

Ledger tool: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py"`.

Work through the checklist in order and report its status as a table (step, status, evidence). A step is done only when there is tool output or a user confirmation to show for it.

## Checklist

1. **Books are valid.** `acct.py validate` prints `OK`.
2. **Every cash account is reconciled** to its statement with the bank-reconciliation skill, with zero unexplained difference.
3. **Receivables.** `acct.py ledger --account <AR code> --to <period end>` and confirm the balance matches open invoices. Ask the user about anything old or disputed.
4. **Payables.** Same for Accounts Payable against unpaid bills. Ask about bills received but not entered.
5. **Accruals and deferrals.** Ask about expenses incurred but not billed (utilities, wages, interest) and amounts paid or received in advance. Record adjusting entries dated the last day of the period.
6. **Depreciation and amortization** for the period, if the business has fixed assets or intangibles.
7. **Sales tax.** The Sales Tax Payable balance should equal the tax collected but not yet remitted.
8. **Trial balance.** `acct.py trial-balance --as-of <period end>` prints `In balance.`
9. **Review.** `acct.py audit` and walk the user through each finding; record corrections in the open period.
10. **Statements.** Produce the income statement for the period and the balance sheet at period end with the financial-statements skill. The balance sheet must print `Balances.`
11. **Year end only: closing entry.** Move every revenue and expense balance to Retained Earnings with one entry dated the last day of the year, so that `acct.py income-statement` for the next year starts at zero.
12. **Lock the period.** Only after the user approves the statements: `acct.py lock --through <period end>`. From then on the plugin's hook asks before any change dated in the closed period.

## Reopening

Reopening a locked period is the user's decision. If they ask for it, run `acct.py lock --through <earlier date> --reopen`, make the change, rerun steps 1, 8 and 10, and lock the period again.
