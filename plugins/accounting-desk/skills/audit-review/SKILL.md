---
name: audit-review
description: Review the Accounting Desk books for errors and risk, such as duplicates, unbalanced or invalid entries, abnormal balances, suspense balances, round amounts and weekend postings, and write up findings with recommended corrections. Use when the user asks for a review, audit, health check or second opinion on the books, or before closing a period.
---

# Audit review

Ledger tool: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py"`.

The reviewer reads and reports. You don't change the books during a review; corrections are proposed and then recorded with the bookkeeping skill once the user approves them.

## Steps

1. `acct.py validate`: structural errors come first.
2. `acct.py audit` (use `--round-threshold` to change the default 1,000 for round-amount flags). Checks:

   | Check | What it means | Usual follow-up |
   | --- | --- | --- |
   | invalid | A line or entry fails validation | Fix before anything else |
   | duplicate | Two entries with the same date, accounts and amounts | Confirm whether both happened; reverse the extra one |
   | suspense-balance | A suspense or clearing account isn't zero | Reclassify to the correct accounts |
   | abnormal-balance | An asset, liability or revenue account has the opposite of its normal balance | Look for misposting or a missing entry |
   | round-amount | A large entry that is an exact multiple of 1,000 | Check support, since round numbers are often estimates |
   | weekend | Posted on a Saturday or Sunday | Confirm the date |
   | no-memo | No description on any line | Add context through a documented correction |

3. Analytical review: compare `acct.py income-statement` for this period with the prior one and ask about large or unexpected movements.
4. Cash: make sure each bank account has a current reconciliation (bank-reconciliation skill).
5. Write up findings ordered by severity, each with the evidence (entry ids, amounts, command output), the risk, and a recommended correcting entry. A finding is something to look at, not proof of an error.
