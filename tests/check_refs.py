#!/usr/bin/env python3
"""Every element the script reaches for must exist somewhere in the file.

This is the cheap half of the interface tests, and it catches the expensive
bug. The swarm page is one file where markup and script sit together, so
deleting a line of HTML can leave four live references behind — and
`$('#gone').onclick = …` is not a cosmetic gap, it is a TypeError at parse
time that stops the whole script and leaves a blank instrument. That is
exactly what deleting the header's "watching <repo>" line nearly did:
#dirBtn and #repoName were wired in four places.

No browser needed, so this runs wherever python does.

    python3 tests/check_refs.py [file ...]

Exits non-zero when a referenced id is defined nowhere in the file.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# $('#x'), querySelector('#x'), getElementById('x') — single or double quoted.
# The closing paren is required, so a selector assembled at runtime — $('#st-'+k)
# — is left alone: its id is not knowable by reading the file, and guessing would
# make this check cry wolf, which is how checks get ignored.
REF = re.compile(
    r"""(?:\$\(|querySelector(?:All)?\(|getElementById\()\s*['"]#?([A-Za-z][\w-]*)['"]\s*\)""")
# id="x" anywhere: static markup AND the template literals the script renders.
DEFN = re.compile(r"""\bid\s*=\s*["']([A-Za-z][\w-]*)["']""")
# ids the script creates through the DOM rather than through markup
CREATED = re.compile(r"""\.id\s*=\s*['"]([A-Za-z][\w-]*)['"]""")


def check(path):
    src = path.read_text()
    defined = set(DEFN.findall(src)) | set(CREATED.findall(src))
    bad = []
    for m in REF.finditer(src):
        name = m.group(1)
        # only id lookups: a $('.class') or $('nav') is not this check's business
        raw = m.group(0)
        if "getElementById" not in raw and "#" not in raw:
            continue
        if name not in defined:
            line = src.count("\n", 0, m.start()) + 1
            bad.append((line, name, raw.strip()))
    return bad


def main():
    targets = [pathlib.Path(a) for a in sys.argv[1:]] or [ROOT / "app" / "swarm.html"]
    failed = 0
    for path in targets:
        if not path.exists():
            print(f"  \033[31m✗\033[0m {path}: not found")
            failed = 1
            continue
        bad = check(path)
        if bad:
            failed = 1
            for line, name, raw in bad:
                print(f"  \033[31m✗\033[0m {path.name}:{line}  reaches for #{name}, "
                      f"which is defined nowhere in the file  —  {raw}")
        else:
            n = len(set(REF.findall(path.read_text())))
            print(f"  \033[32m✓\033[0m {path.name}: every element reference resolves ({n} ids)")
    return failed


if __name__ == "__main__":
    sys.exit(main())
