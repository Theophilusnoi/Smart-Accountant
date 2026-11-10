#!/usr/bin/env python3
"""Claude Code PreToolUse hook: protect closed accounting periods. Stdlib only.

If the project has a `.accounting-desk.json` with `locked_through` set, this
hook asks the user before any tool call that would:

  * add, change or remove a journal line dated on or before the lock date
    (Write, Edit or MultiEdit of the journal file),
  * move the lock date earlier or clear it (Write/Edit of the config file),
  * write to, move or delete the journal or config from a Bash command.

It only ever answers "ask" or stays silent, so it can never approve anything
on its own. Any other tool call, or a project without a lock, is untouched.
If something unexpected happens it stays silent rather than block your work;
`acct.py validate` and `acct.py lock` remain the source of truth.
"""
import csv
import datetime as dt
import io
import json
import os
import re
import sys
from collections import Counter

CONFIG_NAME = ".accounting-desk.json"
DEFAULT_JOURNAL = "books/journal.csv"
BASH_WRITE_RE = re.compile(
    r"(>{1,2}|\btee\b|\bsed\b[^|;&]*\s-i|\bperl\b[^|;&]*\s-[a-z]*i|\brm\b|\bmv\b|\bcp\b|"
    r"\btruncate\b|\bdd\b|\bshred\b|\bopen\([^)]*['\"][wa+])"
)


def find_config(start):
    current = os.path.abspath(start)
    while True:
        candidate = os.path.join(current, CONFIG_NAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def parse_lock(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def locked_rows(text, lock):
    """Journal rows dated on or before the lock date, as a multiset."""
    rows = Counter()
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    if not header:
        return rows
    header = [h.strip().lower() for h in header]
    if "date" not in header:
        raise ValueError("journal has no date column")
    date_col = header.index("date")
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        cell = row[date_col].strip() if date_col < len(row) else ""
        try:
            date = dt.date.fromisoformat(cell)
        except ValueError:
            # An unparseable date might be in the locked period; count it.
            date = lock
        if date <= lock:
            rows[tuple(c.strip() for c in row)] += 1
    return rows


def read_text(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""


def apply_edits(original, edits):
    text = original
    for edit in edits:
        old = edit.get("old_string", "")
        new = edit.get("new_string", "")
        if old == "":
            if text != "":
                return None  # Claude Code rejects this edit on a non-empty file.
            text = new
            continue
        if old not in text:
            return None
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return text


def proposed_content(tool, tool_input, current):
    if tool == "Write":
        return tool_input.get("content", "")
    if tool == "Edit":
        return apply_edits(current, [tool_input])
    if tool == "MultiEdit":
        return apply_edits(current, tool_input.get("edits", []))
    return None


def same_file(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def ask(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


def check(event):
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd") or os.getcwd()

    config_path = find_config(cwd)
    if not config_path:
        return None
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
    lock = parse_lock(config.get("locked_through"))
    if not lock:
        return None
    base = os.path.dirname(config_path)
    journal = config.get("journal") or DEFAULT_JOURNAL
    journal = journal if os.path.isabs(journal) else os.path.join(base, journal)

    if tool in ("Write", "Edit", "MultiEdit"):
        target = tool_input.get("file_path", "")
        if not target:
            return None
        target = target if os.path.isabs(target) else os.path.join(cwd, target)

        if same_file(target, config_path):
            current = read_text(config_path)
            new_text = proposed_content(tool, tool_input, current)
            if new_text is None:
                return None
            try:
                new_lock = parse_lock(json.loads(new_text).get("locked_through"))
            except (ValueError, AttributeError):
                return ("Accounting Desk: this change makes %s unreadable while the books "
                        "are locked through %s." % (CONFIG_NAME, lock))
            if new_lock is None or new_lock < lock:
                return ("Accounting Desk: this reopens closed periods (lock moves from %s to %s). "
                        "Only continue if you approved reopening the books."
                        % (lock, new_lock or "unlocked"))
            return None

        if same_file(target, journal):
            current = read_text(journal)
            new_text = proposed_content(tool, tool_input, current)
            if new_text is None:
                return None  # The edit will fail on its own; nothing to protect.
            try:
                before = locked_rows(current, lock)
                after = locked_rows(new_text, lock)
            except (ValueError, csv.Error):
                return ("Accounting Desk: cannot read the journal change to confirm it leaves "
                        "the period locked through %s untouched." % lock)
            if before != after:
                removed = sum((before - after).values())
                added = sum((after - before).values())
                if added and removed:
                    what = "edits %d journal line(s)" % max(added, removed)
                elif added:
                    what = "adds %d journal line(s)" % added
                else:
                    what = "removes %d journal line(s)" % removed
                return ("Accounting Desk: the books are locked through %s, and this change %s "
                        "dated in that closed period. Corrections normally go in the open "
                        "period as an adjusting entry." % (lock, what))
        return None

    if tool == "Bash":
        command = tool_input.get("command", "")
        names = {os.path.basename(journal), CONFIG_NAME}
        if any(name in command for name in names) and BASH_WRITE_RE.search(command):
            return ("Accounting Desk: this command may modify the journal or %s while the "
                    "books are locked through %s." % (CONFIG_NAME, lock))
    return None


def main():
    try:
        event = json.load(sys.stdin)
        reason = check(event)
    except Exception:  # Never break the session over a guard failure.
        return 0
    if reason:
        return ask(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
