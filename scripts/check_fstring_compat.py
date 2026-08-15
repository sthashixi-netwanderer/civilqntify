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

    fstring_delim: str | None = None   # delimiter of the f-string we are inside
    depth = 0                          # brace nesting depth inside the f-string
    expr_start: tuple[int, int] | None = None

    def check_expr(end_line: int, end_col: int) -> None:
        nonlocal expr_start
        if expr_start is None or fstring_delim is None:
            return
        sl, sc = expr_start
        lines = source.splitlines()
        if sl == end_line:
            text = lines[sl - 1][sc:end_col]
        else:
            text = lines[sl - 1][sc:] + "\n" + "\n".join(lines[sl:end_line - 1] + [lines[end_line - 1][:end_col]])
        if "\\" in text:
            problems.append(f"{filename}:{sl}: backslash in f-string expression: {text.splitlines()[0][:90]}")
        elif len(fstring_delim) == 1 and fstring_delim in text:
            problems.append(
                f"{filename}:{sl}: reuses f-string delimiter {fstring_delim} in expression: {text.splitlines()[0][:90]}"
            )
        expr_start = None

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        return [f"{filename}: tokenize failed ({exc}) — check manually"]

    for tok in tokens:
        ttype, tstr = tok.type, tok.string
        if ttype == tokenize.FSTRING_START:
            # Opener like f" / rf' / F''' — delimiter is the trailing quote run
            q = tstr[-1]
            fstring_delim = q * 3 if tstr.endswith(q * 3) else q
            depth = 0
        elif ttype == tokenize.FSTRING_END:
            fstring_delim = None
            depth = 0
            expr_start = None
        elif fstring_delim is not None:
            if ttype == tokenize.OP and tstr == "{":
                depth += 1
                if depth == 1:
                    expr_start = (tok.start[0], tok.start[1])
            elif ttype == tokenize.OP and tstr == "}":
                if depth == 1:
                    check_expr(tok.start[0], tok.start[1])
                depth = max(0, depth - 1)
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
