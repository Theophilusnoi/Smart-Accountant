---
name: tax-preparation
description: Organize the Accounting Desk books for tax filings, including sales tax and VAT returns, income tax workpapers, deductible expense schedules and contractor payment summaries. Use when the user asks what they owe, wants to prepare a sales tax or VAT return, or wants tax-ready schedules for an accountant.
---

# Tax preparation

You prepare workpapers from the books. You don't file returns or give definitive tax advice: rules depend on the jurisdiction, entity type and year, so every output ends with a reminder to confirm with a qualified tax professional before filing.

Ledger tool: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py"`.

## Before anything else

Ask for, or read from `.accounting-desk.json` or an earlier conversation: the jurisdiction (country and state or province), the entity type, the tax year or filing period, and the accounting method (cash or accrual). Don't assume any of them.

## Sales tax or VAT return

1. The period's books must validate, and should be reconciled and ideally locked (month-end-close skill).
2. `acct.py ledger --account <sales tax payable code> --from <start> --to <end>` gives tax collected (credits) and remitted (debits).
3. `acct.py income-statement --from <start> --to <end>` gives taxable sales. Ask which revenue is exempt or zero-rated.
4. Check that tax collected is close to sales times the rate. Explain any gap (exempt sales, rate changes, errors) before going on.
5. Present: taxable sales, exempt sales, tax collected, input tax or credits if applicable, net amount due, and due date if the user knows it.
6. When the user confirms the payment, record it with the bookkeeping skill (debit Sales Tax Payable, credit Cash).

## Income tax workpapers

- Income statement for the tax year, mapped line by line to the categories the user's return uses. Ask the user or their accountant for the mapping instead of guessing it.
- Flag items that are commonly limited or non-deductible (meals, entertainment, fines, personal expenses, capital purchases that must be depreciated) for the professional to review.
- Contractor summary: total paid per payee from the ledger of the relevant expense accounts, for information returns where the jurisdiction requires them.
- Save workpapers as CSV or Markdown files next to the books, with the period and the date prepared in the file name.
