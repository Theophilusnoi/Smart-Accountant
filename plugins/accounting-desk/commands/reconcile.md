---
description: Reconcile a bank statement CSV against a cash account
argument-hint: "<statement.csv> [account code] [statement ending balance]"
---

Reconcile a bank statement using the bank-reconciliation skill. Arguments: $ARGUMENTS

- The first argument is the statement CSV. The second is the cash account code; if it's missing, use the only cash-like asset account, or ask when there are several. The third is the statement's ending balance; if it's missing, read it from the statement file or ask the user.
- Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py" reconcile --account <code> --bank <file> --statement-balance <balance>`.
- Explain every unmatched item, propose entries for the missing ones, record them only after the user agrees, then rerun until the tool prints `RECONCILED.` or the remaining difference is clearly reported.
