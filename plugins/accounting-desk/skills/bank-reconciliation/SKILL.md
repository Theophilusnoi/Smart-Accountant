---
name: bank-reconciliation
description: Reconcile a bank or card statement against a cash account in the Accounting Desk books, explain every difference, and propose the entries needed. Use when the user shares a bank statement CSV, asks whether the cash balance is right, or wants to find missing or duplicated transactions.
---

# Bank reconciliation

A reconciliation is finished only when the unexplained difference is exactly zero.

Ledger tool: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py"`.

## Statement format

CSV with `date,description,amount` (deposits positive, withdrawals negative), or `date,description,deposit,withdrawal`. Dates must be `YYYY-MM-DD`. If the bank's export looks different, convert it into one of these formats in a new file; never edit the original export.

## Steps

1. `acct.py validate` must pass first.
2. Get the statement's **ending balance** from the user or the statement itself.
3. Run:

   ```
   acct.py reconcile --account 1000 --bank <statement.csv> --statement-balance <ending balance>
   ```

   Options: `--window N` days of date tolerance for matching (default 3), `--from` and `--as-of` to set the period. The tool matches on exact amount, then nearest date.
4. Explain each unmatched item:
   - **On the statement, not in the books**: bank fees, interest, direct debits, deposits never recorded, or errors. Propose a journal entry for each (for example Bank Fees debit, Cash credit), and record it with the bookkeeping skill once the user agrees.
   - **In the books, not on the statement**: outstanding checks and deposits in transit (normal near month end), or entries posted to the wrong account or with the wrong amount.
   - A book item and a bank item with the same description but different amounts usually means a typo: show both and ask which is right.
5. After recording the agreed entries, run the reconciliation again. Report `RECONCILED.` only when the tool prints it. If a difference remains, say how much and list what is still unexplained.

## Notes

- The tool assumes earlier periods were reconciled. If the opening balance doesn't agree with the prior statement, reconcile that period first.
- Never post a plug entry to force the difference to zero. If the user wants a temporary suspense entry, label it clearly; `acct.py audit` flags any non-zero suspense balance.
