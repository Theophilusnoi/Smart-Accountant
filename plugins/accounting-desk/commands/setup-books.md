---
description: Set up Accounting Desk books (chart of accounts, journal and config) in this project
argument-hint: "[folder, default books]"
---

Set up Accounting Desk books for this project using the bookkeeping skill.

1. If `.accounting-desk.json` already exists here or in a parent folder, don't create new books. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py" validate` and report the result instead.
2. Otherwise run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py" init --dir "${ARGUMENTS:-books}"` from the project root.
3. Ask the user about the business (what it sells, whether it holds inventory, collects sales tax or VAT, has employees, its currency) and adjust the template chart of accounts to fit, keeping codes in ranges: 1000s assets, 2000s liabilities, 3000s equity, 4000s revenue, 5000s and up expenses. Set `currency` in `.accounting-desk.json`.
4. Offer to record opening balances as one entry dated the day before the books start.
5. Finish with `acct.py validate` and show its output.
