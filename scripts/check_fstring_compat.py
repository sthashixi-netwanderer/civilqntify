#!/usr/bin/env python3
"""Find f-string constructs that are SyntaxErrors on Python < 3.12.

PEP 701 (Python 3.12) relaxed f-string grammar. Two changes matter:

1. Backslashes inside the expression part ``{...}`` of an f-string
   became legal ("f-string expression part cannot include a backslash").
2. Reusing the enclosing f-string's single-character delimiter inside
   the expression part became legal (e.g. ``f"{d["key"]}"``). Note that
   triple-quoted f-strings already allowed inner single quotes pre-3.12.

Source using these features parses fine on 3.12+ but is a SyntaxError on
3.11 and older — which silently breaks builds on those versions (e.g.
PyInstaller cannot compile the module and drops it from the bundle with
only a warning).

Detector: uses the tokenizer's FSTRING_START/END tokens (PEP 701) to
know each f-string's exact delimiter, then inspects everything between
each outermost ``{``...``}`` pair for backslashes or delimiter reuse.

Requires Python 3.12+ to run (uses the new f-string tokens).
Run from the project root:  python scripts/check_fstring_compat.py
"""

from __future__ import annotations

import io
import pathlib
import tokenize

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ["app", "concrete_mix", "material_quantify", "history", "main.py", "main_cli.py"]


def _violations_in(source: str, filename: str) -> list[str]:
    problems: list[str] = []
    lines = source.splitlines()

    stack: list[dict] = []  # entries: {"delim": str, "depth": int, "expr_start": tuple[int, int] | None}

    def check_expr(entry: dict, end_line: int, end_col: int) -> None:
        expr_start = entry.get("expr_start")
        delim = entry.get("delim")
        if expr_start is None or delim is None:
            return
        sl, sc = expr_start
        if sl == end_line:
            text = lines[sl - 1][sc:end_col]
        else:
            text = lines[sl - 1][sc:] + "\n" + "\n".join(lines[sl:end_line - 1] + [lines[end_line - 1][:end_col]])
        if "\\" in text:
            problems.append(f"{filename}:{sl}: backslash in f-string expression: {text.splitlines()[0][:90]}")
        elif len(delim) == 1 and delim in text:
            problems.append(
                f"{filename}:{sl}: reuses f-string delimiter {delim} in expression: {text.splitlines()[0][:90]}"
            )
        entry["expr_start"] = None

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        return [f"{filename}: tokenize failed ({exc}) — check manually"]

    for tok in tokens:
        ttype, tstr = tok.type, tok.string
        if ttype == tokenize.FSTRING_START:
            q = tstr[-1]
            delim = q * 3 if tstr.endswith(q * 3) else q
            stack.append({"delim": delim, "depth": 0, "expr_start": None})
        elif ttype == tokenize.FSTRING_END:
            if stack:
                stack.pop()
        elif stack:
            cur = stack[-1]
            if ttype == tokenize.OP and tstr == "{":
                cur["depth"] += 1
                if cur["depth"] == 1:
                    cur["expr_start"] = (tok.start[0], tok.start[1])
            elif ttype == tokenize.OP and tstr == "}":
                if cur["depth"] == 1:
                    check_expr(cur, tok.start[0], tok.start[1])
                cur["depth"] = max(0, cur["depth"] - 1)
    return problems


def main() -> int:
    total = 0
    for pkg in PACKAGES:
        p = ROOT / pkg
        files = p.rglob("*.py") if p.is_dir() else ([p] if p.exists() else [])
        for f in sorted(files):
            if "__pycache__" in f.parts:
                continue
            src = f.read_text(encoding="utf-8")
            for msg in _violations_in(src, str(f.relative_to(ROOT))):
                print(msg)
                total += 1
    if total:
        print(f"\n{total} violation(s) — all are SyntaxErrors on Python 3.11 and older.")
        return 1
    print("OK — no Python <3.12-incompatible f-strings found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
