---
description: Run the month-end close checklist and, with approval, lock the period
argument-hint: "<YYYY-MM>"
---

Close the accounting period $ARGUMENTS using the month-end-close skill. If no month was given, ask which one.

Work from the first to the last day of that month. Run each checklist step with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acct.py"`, show a status table (step, status, evidence) as you go, and stop to ask the user wherever the skill calls for a decision. Lock the period only after the user explicitly approves the final statements.
