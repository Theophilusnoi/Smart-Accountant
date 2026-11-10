#!/usr/bin/env python3
"""Accounting Desk ledger tool. Python 3.8+ standard library only.

Works on plain CSV books so the numbers are always reproducible:

  chart_of_accounts.csv   code,name,type          (type: asset, liability,
                                                   equity, revenue, expense)
  journal.csv             date,entry_id,account,debit,credit,memo
  bank statement CSV      date,description,amount  (deposits positive), or
                          date,description,deposit,withdrawal

Paths come from flags, then from `.accounting-desk.json` (searched for in the
current directory and its parents), then from the defaults under `books/`.

Commands: init, validate, trial-balance, ledger, income-statement,
balance-sheet, reconcile, audit, lock. Add --json for machine-readable output.

Exit codes: 0 success, 1 the books have errors (validate) or the
reconciliation does not tie out, 2 usage or file problems.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
from collections import OrderedDict, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CONFIG_NAME = ".accounting-desk.json"
ACCOUNT_TYPES = ("asset", "liability", "equity", "revenue", "expense")
DEBIT_NORMAL = ("asset", "expense")
JOURNAL_COLUMNS = ("date", "entry_id", "account", "debit", "credit", "memo")
COA_COLUMNS = ("code", "name", "type")
CENT = Decimal("0.01")
ZERO = Decimal("0")


class BooksError(Exception):
    """A problem that stops a command from running (missing file, bad header)."""


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------

def parse_date(text):
    try:
        return dt.date.fromisoformat(text.strip())
    except (ValueError, AttributeError):
        raise ValueError("date %r is not YYYY-MM-DD" % (text,))


def parse_amount(text):
    text = (text or "").strip().replace(",", "")
    if text == "":
        return ZERO
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.lstrip("$")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("amount %r is not a number" % (text,))
    if not value.is_finite():
        raise ValueError("amount %r is not a number" % (text,))
    if value != value.quantize(CENT):
        raise ValueError("amount %r has more than 2 decimal places" % (text,))
    return -value if negative else value


def money(value):
    value = value.quantize(CENT, rounding=ROUND_HALF_UP)
    if value < 0:
        return "(" + format(-value, ",.2f") + ")"
    return format(value, ",.2f")


def read_csv(path, required):
    if not os.path.isfile(path):
        raise BooksError("file not found: %s" % path)
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = [h.strip().lower() for h in (reader.fieldnames or [])]
        missing = [c for c in required if c not in header]
        if missing:
            raise BooksError("%s is missing column(s): %s" % (path, ", ".join(missing)))
        rows = []
        for line_no, raw in enumerate(reader, start=2):
            row = {}
            for key, value in raw.items():
                if key is None:
                    continue
                row[key.strip().lower()] = (value or "").strip()
            if not any(row.values()):
                continue
            rows.append((line_no, row))
        return rows


# --------------------------------------------------------------------------
# Books model
# --------------------------------------------------------------------------

class Books:
    def __init__(self, coa_path, journal_path, locked_through=None):
        self.coa_path = coa_path
        self.journal_path = journal_path
        self.locked_through = locked_through
        self.accounts = OrderedDict()   # code -> {"name", "type"}
        self.lines = []                 # dicts: line, date, entry_id, account, debit, credit, memo
        self.errors = []                # (file, line, message)
        self._load_coa()
        self._load_journal()

    def _error(self, path, line, message):
        self.errors.append((os.path.basename(path), line, message))

    def _load_coa(self):
        for line_no, row in read_csv(self.coa_path, COA_COLUMNS):
            code, name, kind = row["code"], row["name"], row["type"].lower()
            if not code:
                self._error(self.coa_path, line_no, "account code is blank")
                continue
            if code in self.accounts:
                self._error(self.coa_path, line_no, "duplicate account code %s" % code)
                continue
            if kind not in ACCOUNT_TYPES:
                self._error(self.coa_path, line_no,
                            "account %s has type %r; use one of %s"
                            % (code, row["type"], ", ".join(ACCOUNT_TYPES)))
                continue
            self.accounts[code] = {"name": name or code, "type": kind}

    def _load_journal(self):
        entries = defaultdict(list)
        for line_no, row in read_csv(self.journal_path, JOURNAL_COLUMNS[:5]):
            problems = []
            try:
                date = parse_date(row["date"])
            except ValueError as exc:
                problems.append(str(exc))
                date = None
            try:
                debit = parse_amount(row["debit"])
                credit = parse_amount(row["credit"])
            except ValueError as exc:
                problems.append(str(exc))
                debit = credit = ZERO
            entry_id = row["entry_id"]
            account = row["account"]
            if not entry_id:
                problems.append("entry_id is blank")
            if account not in self.accounts:
                problems.append("account %r is not in the chart of accounts" % account)
            if debit < 0 or credit < 0:
                problems.append("debit and credit must not be negative")
            elif (debit > 0) == (credit > 0):
                problems.append("each line needs exactly one of debit or credit")
            for problem in problems:
                self._error(self.journal_path, line_no, problem)
            if problems:
                continue
            line = {
                "line": line_no, "date": date, "entry_id": entry_id,
                "account": account, "debit": debit, "credit": credit,
                "memo": row.get("memo", ""),
            }
            self.lines.append(line)
            entries[entry_id].append(line)

        for entry_id, lines in entries.items():
            dates = {l["date"] for l in lines}
            first = lines[0]["line"]
            if len(dates) > 1:
                self._error(self.journal_path, first,
                            "entry %s has lines on different dates" % entry_id)
            if len(lines) < 2:
                self._error(self.journal_path, first,
                            "entry %s has only one line" % entry_id)
            dr = sum(l["debit"] for l in lines)
            cr = sum(l["credit"] for l in lines)
            if dr != cr:
                self._error(self.journal_path, first,
                            "entry %s does not balance: debits %s, credits %s"
                            % (entry_id, money(dr), money(cr)))
        self.lines.sort(key=lambda l: (l["date"], l["entry_id"], l["line"]))

    # -- queries ------------------------------------------------------------

    def select(self, start=None, end=None, account=None):
        for line in self.lines:
            if start and line["date"] < start:
                continue
            if end and line["date"] > end:
                continue
            if account and line["account"] != account:
                continue
            yield line

    def totals(self, start=None, end=None):
        result = OrderedDict((code, [ZERO, ZERO]) for code in self.accounts)
        for line in self.select(start, end):
            result[line["account"]][0] += line["debit"]
            result[line["account"]][1] += line["credit"]
        return result

    def natural_balance(self, code, debit, credit):
        if self.accounts[code]["type"] in DEBIT_NORMAL:
            return debit - credit
        return credit - debit

    def entries(self):
        grouped = OrderedDict()
        for line in self.lines:
            grouped.setdefault(line["entry_id"], []).append(line)
        return grouped


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

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


def load_config(path):
    if not path:
        return {}, os.getcwd()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise BooksError("cannot read %s: %s" % (path, exc))
    if not isinstance(data, dict):
        raise BooksError("%s must contain a JSON object" % path)
    return data, os.path.dirname(os.path.abspath(path))


def resolve(args):
    config_path = args.config or find_config(os.getcwd())
    config, base = load_config(config_path)

    def pick(flag, key, default):
        if flag:
            return os.path.abspath(flag)
        value = config.get(key, default)
        return value if os.path.isabs(value) else os.path.normpath(os.path.join(base, value))

    coa = pick(args.coa, "chart_of_accounts", "books/chart_of_accounts.csv")
    journal = pick(args.journal, "journal", "books/journal.csv")
    locked = config.get("locked_through")
    if locked:
        try:
            locked = parse_date(locked)
        except ValueError as exc:
            raise BooksError("locked_through in %s: %s" % (config_path, exc))
    return {"config": config_path, "config_data": config, "base": base,
            "coa": coa, "journal": journal, "locked_through": locked,
            "currency": config.get("currency", "")}


def load_books(ctx):
    return Books(ctx["coa"], ctx["journal"], ctx["locked_through"])


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def emit(args, data, text_lines):
    if args.json:
        print(json.dumps(data, indent=2, default=_json_default))
    else:
        print("\n".join(text_lines))


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value.quantize(CENT))
    if isinstance(value, dt.date):
        return value.isoformat()
    raise TypeError(repr(value))


def table(headers, rows, align):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(row):
        cells = []
        for i, cell in enumerate(row):
            cells.append(cell.rjust(widths[i]) if align[i] == "r" else cell.ljust(widths[i]))
        return "  ".join(cells).rstrip()

    out = [fmt(headers), "  ".join("-" * w for w in widths)]
    out.extend(fmt(r) for r in rows)
    return out


def error_lines(books):
    return ["  %s:%s  %s" % (f, l, m) for f, l, m in books.errors]


def require_clean(books, args):
    """Reports must not be built on books that fail validation."""
    if books.errors:
        lines = ["The books have %d error(s); fix them first (run `validate`):" % len(books.errors)]
        lines.extend(error_lines(books))
        emit(args, {"ok": False, "errors": _errors_json(books)}, lines)
        return False
    return True


def _errors_json(books):
    return [{"file": f, "line": l, "message": m} for f, l, m in books.errors]


def opt_date(text, name):
    if text is None:
        return None
    try:
        return parse_date(text)
    except ValueError as exc:
        raise BooksError("--%s: %s" % (name, exc))


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

TEMPLATE_COA = """code,name,type
1000,Cash - Operating,asset
1100,Accounts Receivable,asset
1500,Equipment,asset
2000,Accounts Payable,liability
2100,Sales Tax Payable,liability
3000,Owner's Equity,equity
3900,Retained Earnings,equity
4000,Sales Revenue,revenue
5000,Cost of Goods Sold,expense
6000,Rent Expense,expense
6100,Bank Fees,expense
"""
TEMPLATE_JOURNAL = "date,entry_id,account,debit,credit,memo\n"


def cmd_init(args, ctx):
    target = os.path.abspath(args.dir)
    os.makedirs(target, exist_ok=True)
    created, kept = [], []
    files = {
        os.path.join(target, "chart_of_accounts.csv"): TEMPLATE_COA,
        os.path.join(target, "journal.csv"): TEMPLATE_JOURNAL,
    }
    config_path = os.path.join(os.getcwd(), CONFIG_NAME)
    rel = os.path.relpath(target, os.getcwd())
    files[config_path] = json.dumps({
        "chart_of_accounts": os.path.join(rel, "chart_of_accounts.csv"),
        "journal": os.path.join(rel, "journal.csv"),
        "currency": args.currency,
        "locked_through": None,
    }, indent=2) + "\n"
    for path, content in files.items():
        if os.path.exists(path):
            kept.append(path)
            continue
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        created.append(path)
    lines = ["Created: %s" % p for p in created] + ["Kept existing: %s" % p for p in kept]
    emit(args, {"created": created, "kept": kept}, lines or ["Nothing to do."])
    return 0


def cmd_validate(args, ctx):
    books = load_books(ctx)
    data = {
        "ok": not books.errors,
        "accounts": len(books.accounts),
        "lines": len(books.lines),
        "entries": len(books.entries()),
        "locked_through": ctx["locked_through"],
        "errors": _errors_json(books),
    }
    if books.errors:
        lines = ["FAIL: %d error(s)" % len(books.errors)] + error_lines(books)
    else:
        lines = ["OK: %d accounts, %d entries, %d lines; every entry balances."
                 % (data["accounts"], data["entries"], data["lines"])]
        if ctx["locked_through"]:
            lines.append("Books are locked through %s." % ctx["locked_through"])
    emit(args, data, lines)
    return 0 if not books.errors else 1


def cmd_trial_balance(args, ctx):
    books = load_books(ctx)
    if not require_clean(books, args):
        return 1
    as_of = opt_date(args.as_of, "as-of")
    rows, data_rows = [], []
    total_dr = total_cr = ZERO
    for code, (dr, cr) in books.totals(end=as_of).items():
        if dr == 0 and cr == 0 and not args.all:
            continue
        net = dr - cr
        bal_dr, bal_cr = (net, ZERO) if net >= 0 else (ZERO, -net)
        total_dr += bal_dr
        total_cr += bal_cr
        acct = books.accounts[code]
        rows.append([code, acct["name"], acct["type"],
                     money(bal_dr) if bal_dr else "", money(bal_cr) if bal_cr else ""])
        data_rows.append({"code": code, "name": acct["name"], "type": acct["type"],
                          "debit": bal_dr, "credit": bal_cr})
    rows.append(["", "TOTAL", "", money(total_dr), money(total_cr)])
    balanced = total_dr == total_cr
    title = "Trial balance" + (" as of %s" % as_of if as_of else "")
    lines = [title, ""] + table(["Code", "Account", "Type", "Debit", "Credit"],
                                rows, "lllrr")
    lines.append("")
    lines.append("In balance." if balanced else "OUT OF BALANCE by %s" % money(total_dr - total_cr))
    emit(args, {"as_of": as_of, "accounts": data_rows, "total_debit": total_dr,
                "total_credit": total_cr, "balanced": balanced}, lines)
    return 0 if balanced else 1


def cmd_ledger(args, ctx):
    books = load_books(ctx)
    if not require_clean(books, args):
        return 1
    if args.account not in books.accounts:
        raise BooksError("account %s is not in the chart of accounts" % args.account)
    start, end = opt_date(args.start, "from"), opt_date(args.end, "to")
    code = args.account
    opening = ZERO
    if start:
        for line in books.select(end=start - dt.timedelta(days=1), account=code):
            opening += books.natural_balance(code, line["debit"], line["credit"])
    balance = opening
    rows = [["", "", "Opening balance", "", "", money(opening)]]
    data_lines = []
    for line in books.select(start, end, code):
        balance += books.natural_balance(code, line["debit"], line["credit"])
        rows.append([line["date"].isoformat(), line["entry_id"], line["memo"],
                     money(line["debit"]) if line["debit"] else "",
                     money(line["credit"]) if line["credit"] else "", money(balance)])
        data_lines.append({"date": line["date"], "entry_id": line["entry_id"],
                           "memo": line["memo"], "debit": line["debit"],
                           "credit": line["credit"], "balance": balance})
    acct = books.accounts[code]
    lines = ["General ledger: %s %s (%s)" % (code, acct["name"], acct["type"]), ""]
    lines += table(["Date", "Entry", "Memo", "Debit", "Credit", "Balance"], rows, "lllrrr")
    emit(args, {"account": code, "name": acct["name"], "opening": opening,
                "lines": data_lines, "closing": balance}, lines)
    return 0


def _section(books, totals, kind):
    items, total = [], ZERO
    for code, (dr, cr) in totals.items():
        if books.accounts[code]["type"] != kind:
            continue
        amount = books.natural_balance(code, dr, cr)
        if amount == 0:
            continue
        items.append({"code": code, "name": books.accounts[code]["name"], "amount": amount})
        total += amount
    return items, total


def _section_lines(title, items, total):
    out = [title]
    for item in items:
        out.append("  %-6s %-34s %14s" % (item["code"], item["name"][:34], money(item["amount"])))
    out.append("  %-41s %14s" % ("Total " + title.lower(), money(total)))
    return out


def cmd_income_statement(args, ctx):
    books = load_books(ctx)
    if not require_clean(books, args):
        return 1
    start, end = opt_date(args.start, "from"), opt_date(args.end, "to")
    if start and end and start > end:
        raise BooksError("--from is after --to")
    totals = books.totals(start, end)
    revenue, rev_total = _section(books, totals, "revenue")
    expenses, exp_total = _section(books, totals, "expense")
    net = rev_total - exp_total
    period = "%s to %s" % (start or "beginning", end or "latest")
    lines = ["Income statement, %s" % period, ""]
    lines += _section_lines("Revenue", revenue, rev_total) + [""]
    lines += _section_lines("Expenses", expenses, exp_total) + [""]
    lines.append("  %-41s %14s" % ("NET INCOME" if net >= 0 else "NET LOSS", money(net)))
    emit(args, {"from": start, "to": end, "revenue": revenue, "total_revenue": rev_total,
                "expenses": expenses, "total_expenses": exp_total, "net_income": net}, lines)
    return 0


def cmd_balance_sheet(args, ctx):
    books = load_books(ctx)
    if not require_clean(books, args):
        return 1
    as_of = opt_date(args.as_of, "as-of")
    totals = books.totals(end=as_of)
    assets, a_total = _section(books, totals, "asset")
    liabilities, l_total = _section(books, totals, "liability")
    equity, e_total = _section(books, totals, "equity")
    _, rev = _section(books, totals, "revenue")
    _, exp = _section(books, totals, "expense")
    earnings = rev - exp
    if earnings:
        equity = equity + [{"code": "", "name": "Earnings not yet closed", "amount": earnings}]
        e_total += earnings
    balanced = a_total == l_total + e_total
    lines = ["Balance sheet as of %s" % (as_of or "latest"), ""]
    lines += _section_lines("Assets", assets, a_total) + [""]
    lines += _section_lines("Liabilities", liabilities, l_total) + [""]
    lines += _section_lines("Equity", equity, e_total) + [""]
    lines.append("  %-41s %14s" % ("Liabilities + equity", money(l_total + e_total)))
    lines.append("")
    lines.append("Balances." if balanced else
                 "DOES NOT BALANCE: difference %s" % money(a_total - l_total - e_total))
    emit(args, {"as_of": as_of, "assets": assets, "total_assets": a_total,
                "liabilities": liabilities, "total_liabilities": l_total,
                "equity": equity, "total_equity": e_total, "balanced": balanced}, lines)
    return 0 if balanced else 1


def read_bank(path):
    if not os.path.isfile(path):
        raise BooksError("file not found: %s" % path)
    with open(path, newline="", encoding="utf-8-sig") as handle:
        header = [h.strip().lower() for h in (csv.DictReader(handle).fieldnames or [])]
    if "amount" in header:
        rows = read_csv(path, ("date", "description", "amount"))
    else:
        rows = read_csv(path, ("date", "description", "deposit", "withdrawal"))
    items, errors = [], []
    for line_no, row in rows:
        try:
            date = parse_date(row["date"])
            if "amount" in row:
                amount = parse_amount(row["amount"])
            else:
                amount = parse_amount(row["deposit"]) - parse_amount(row["withdrawal"])
        except ValueError as exc:
            errors.append("%s:%d  %s" % (os.path.basename(path), line_no, exc))
            continue
        items.append({"line": line_no, "date": date, "description": row["description"],
                      "amount": amount})
    if errors:
        raise BooksError("bank statement has errors:\n  " + "\n  ".join(errors))
    if not items:
        raise BooksError("bank statement %s has no transactions" % path)
    return items


def cmd_reconcile(args, ctx):
    books = load_books(ctx)
    if not require_clean(books, args):
        return 1
    code = args.account
    if code not in books.accounts:
        raise BooksError("account %s is not in the chart of accounts" % code)
    if books.accounts[code]["type"] != "asset":
        raise BooksError("account %s is not an asset account" % code)
    bank = read_bank(args.bank)
    window = dt.timedelta(days=args.window)
    as_of = opt_date(args.as_of, "as-of") or max(b["date"] for b in bank)
    start = opt_date(args.start, "from") or (min(b["date"] for b in bank) - window)
    bank = [b for b in bank if b["date"] <= as_of]

    book = [dict(l, amount=l["debit"] - l["credit"])
            for l in books.select(start, as_of, code)]
    used = set()
    matched, bank_only = [], []
    # Exact amount, nearest date within the window, earliest book line on ties.
    for item in sorted(bank, key=lambda b: (b["date"], b["line"])):
        best = None
        for i, line in enumerate(book):
            if i in used or line["amount"] != item["amount"]:
                continue
            gap = abs((line["date"] - item["date"]).days)
            if gap > args.window:
                continue
            if best is None or gap < best[0]:
                best = (gap, i)
        if best is None:
            bank_only.append(item)
        else:
            used.add(best[1])
            matched.append({"bank": item, "book": book[best[1]]})
    book_only = [l for i, l in enumerate(book) if i not in used]

    book_balance = sum((l["debit"] - l["credit"] for l in books.select(end=as_of, account=code)), ZERO)
    adjusted_book = book_balance + sum((b["amount"] for b in bank_only), ZERO)
    data = {
        "account": code, "from": start, "as_of": as_of, "window_days": args.window,
        "matched": len(matched),
        "bank_only": [{"date": b["date"], "description": b["description"], "amount": b["amount"]}
                      for b in bank_only],
        "book_only": [{"date": l["date"], "entry_id": l["entry_id"], "memo": l["memo"],
                       "amount": l["amount"]} for l in book_only],
        "book_balance": book_balance,
        "adjusted_book_balance": adjusted_book,
    }
    lines = ["Bank reconciliation: %s %s, %s to %s"
             % (code, books.accounts[code]["name"], start, as_of), "",
             "Matched: %d" % len(matched), ""]
    lines.append("On the statement, not in the books (record these): %d" % len(bank_only))
    for b in bank_only:
        lines.append("  %s  %-40s %14s" % (b["date"], b["description"][:40], money(b["amount"])))
    lines.append("")
    lines.append("In the books, not on the statement (timing or error): %d" % len(book_only))
    for l in book_only:
        lines.append("  %s  %-8s %-31s %14s" % (l["date"], l["entry_id"], l["memo"][:31], money(l["amount"])))
    lines.append("")
    lines.append("  %-50s %14s" % ("Book balance", money(book_balance)))
    lines.append("  %-50s %14s" % ("Adjusted book balance (+ statement-only items)", money(adjusted_book)))
    status = 0
    if args.statement_balance is not None:
        try:
            statement = parse_amount(args.statement_balance)
        except ValueError as exc:
            raise BooksError("--statement-balance: %s" % exc)
        adjusted_bank = statement + sum((l["amount"] for l in book_only), ZERO)
        difference = adjusted_bank - adjusted_book
        data.update(statement_balance=statement, adjusted_bank_balance=adjusted_bank,
                    difference=difference, reconciled=difference == 0)
        lines.append("  %-50s %14s" % ("Statement balance", money(statement)))
        lines.append("  %-50s %14s" % ("Adjusted bank balance (+ book-only items)", money(adjusted_bank)))
        lines.append("")
        if difference == 0:
            lines.append("RECONCILED.")
        else:
            lines.append("NOT RECONCILED: unexplained difference %s" % money(difference))
            status = 1
    else:
        lines.append("")
        lines.append("Pass --statement-balance to prove the reconciliation ties out.")
    emit(args, data, lines)
    return status


def cmd_audit(args, ctx):
    books = load_books(ctx)
    findings = []

    def add(kind, entry_id, date, detail):
        findings.append({"check": kind, "entry_id": entry_id, "date": date, "detail": detail})

    for f, l, m in books.errors:
        add("invalid", "", None, "%s:%s %s" % (f, l, m))

    threshold = parse_amount(args.round_threshold)
    signatures = defaultdict(list)
    for entry_id, lines in books.entries().items():
        date = lines[0]["date"]
        sig = (date, tuple(sorted((l["account"], l["debit"], l["credit"]) for l in lines)))
        signatures[sig].append(entry_id)
        amount = sum(l["debit"] for l in lines)
        if amount >= threshold and amount % 1000 == 0:
            add("round-amount", entry_id, date, "round amount %s" % money(amount))
        if date.weekday() >= 5:
            add("weekend", entry_id, date, "posted on a %s" % date.strftime("%A"))
        if not any(l["memo"] for l in lines):
            add("no-memo", entry_id, date, "no line has a memo")
    for (date, _), ids in signatures.items():
        if len(ids) > 1:
            add("duplicate", ", ".join(ids), date, "identical entries")

    for code, (dr, cr) in books.totals().items():
        name = books.accounts[code]["name"].lower()
        balance = books.natural_balance(code, dr, cr)
        if ("suspense" in name or "clearing" in name) and balance != 0:
            add("suspense-balance", "", None, "%s %s carries %s" % (code, books.accounts[code]["name"], money(balance)))
        elif balance < 0 and books.accounts[code]["type"] in ("asset", "liability", "revenue"):
            add("abnormal-balance", "", None, "%s %s has an abnormal balance of %s"
                % (code, books.accounts[code]["name"], money(balance)))

    order = ["invalid", "duplicate", "suspense-balance", "abnormal-balance",
             "round-amount", "weekend", "no-memo"]
    findings.sort(key=lambda f: (order.index(f["check"]), str(f["date"] or ""), f["entry_id"]))
    lines = ["Audit review: %d finding(s)" % len(findings)]
    for f in findings:
        lines.append("  [%s] %s %s %s" % (f["check"], f["date"] or "", f["entry_id"], f["detail"]))
    if not findings:
        lines.append("  No exceptions found.")
    lines.append("")
    lines.append("Findings are prompts for review, not proof of error.")
    emit(args, {"findings": findings}, lines)
    return 0


def cmd_lock(args, ctx):
    if not ctx["config"]:
        raise BooksError("no %s found; run `init` first" % CONFIG_NAME)
    through = opt_date(args.through, "through")
    current = ctx["locked_through"]
    if current and through < current and not args.reopen:
        raise BooksError("books are locked through %s; moving the lock back to %s reopens "
                         "closed periods. Pass --reopen if the user approved that."
                         % (current, through))
    books = load_books(ctx)
    if books.errors:
        raise BooksError("the books have %d error(s); fix them before locking" % len(books.errors))
    config = dict(ctx["config_data"])
    config["locked_through"] = through.isoformat()
    tmp = ctx["config"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, ctx["config"])
    emit(args, {"locked_through": through, "previous": current},
         ["Books locked through %s (was %s)." % (through, current or "unlocked")])
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="acct.py", description=__doc__.split("\n")[0])
    parser.add_argument("--config", help="path to %s" % CONFIG_NAME)
    parser.add_argument("--coa", help="chart of accounts CSV")
    parser.add_argument("--journal", help="journal CSV")
    parser.add_argument("--json", action="store_true", help="print JSON")
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    p = sub.add_parser("init", help="create template books and config")
    p.add_argument("--dir", default="books")
    p.add_argument("--currency", default="USD")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("validate", help="check the books for errors")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("trial-balance", help="trial balance")
    p.add_argument("--as-of")
    p.add_argument("--all", action="store_true", help="include zero-balance accounts")
    p.set_defaults(func=cmd_trial_balance)

    p = sub.add_parser("ledger", help="general ledger for one account")
    p.add_argument("--account", required=True)
    p.add_argument("--from", dest="start")
    p.add_argument("--to", dest="end")
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("income-statement", help="profit and loss for a period")
    p.add_argument("--from", dest="start")
    p.add_argument("--to", dest="end")
    p.set_defaults(func=cmd_income_statement)

    p = sub.add_parser("balance-sheet", help="balance sheet at a date")
    p.add_argument("--as-of")
    p.set_defaults(func=cmd_balance_sheet)

    p = sub.add_parser("reconcile", help="match a bank statement to a cash account")
    p.add_argument("--account", required=True)
    p.add_argument("--bank", required=True, help="bank statement CSV")
    p.add_argument("--statement-balance", help="ending balance printed on the statement")
    p.add_argument("--from", dest="start")
    p.add_argument("--as-of")
    p.add_argument("--window", type=int, default=3, help="days of date tolerance (default 3)")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("audit", help="flag entries that deserve a second look")
    p.add_argument("--round-threshold", default="1000")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("lock", help="lock the books through a date")
    p.add_argument("--through", required=True)
    p.add_argument("--reopen", action="store_true", help="allow moving the lock earlier")
    p.set_defaults(func=cmd_lock)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        ctx = resolve(args)
        return args.func(args, ctx)
    except BooksError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
