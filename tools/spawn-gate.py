#!/usr/bin/env python3
"""Assert what this repository may and may not do with processes.

The 0.2.0 removal took out a one-click button that built a command from mined
GitHub ticket text and ran it. The gate that replaced it was a grep for the two
words the deleted code happened to use, over one of fifteen Python files — it
would have passed `os.posix_spawn`, `importlib.import_module("sub"+"process")`,
or the same feature rebuilt one directory down. A deny-list can only recognise
the crime it has already seen.

So this asserts the property instead, over every tracked Python file:

1. `observatory.py` — the process that reads mined GitHub text — imports nothing
   that can start a process. Not a word search: an AST walk of its imports and
   of every `os.<attr>` it touches. It may still CALL induction, which spawns;
   that is why claim 3 exists and why the README says "no mined text reaches an
   argv" rather than "nothing spawns".
2. Nowhere in the tree: `shell=True`, `Popen`, `os.system`, `os.popen`,
   `os.exec*`, `os.fork`, `os.posix_spawn`, `pty.spawn`, or asyncio's subprocess
   creators. These are the primitives a reintroduction would reach for.
3. Every surviving spawn passes a FIXED argument list — each element a string
   literal or a bare local name, never a subscript, call, f-string, or
   concatenation. That is the shape mined text arrives in (`art["title"]`,
   f"...{title}"), so this is the check that actually stands between a ticket
   and an argv.

What it does not prove: that a bare name holds what you think it holds, or
anything about a non-Python child. Stated here so the next reader does not
mistake a green tick for more than it is.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules that hand you a child process. importlib/runpy/ctypes are here because
# each is a way to reach the others without naming them.
SPAWN_MODULES = {
    "subprocess", "multiprocessing", "pty", "importlib", "runpy", "ctypes",
    "asyncio.subprocess", "posix", "commands", "popen2", "pipes",
}
# os attributes that fork or exec. Prefix-matched, so os.execve/execvp/spawnl
# are all covered without listing every variant the stdlib has ever had.
OS_SPAWN_PREFIXES = ("exec", "spawn", "posix_spawn", "fork", "system", "popen")
# The module that must not be able to spawn at all.
SEALED = "observatory.py"
# Offline analysis scripts, run by hand, reachable from nothing the plugin
# starts — they build `gh api graphql -f k=v` argv in loops, which claim 3
# cannot distinguish from a mined-text argv. They are exempt from claim 3 ONLY;
# claims 1 and 2 still apply to them, and every exemption is printed on each run
# so it cannot quietly grow. Add a path here only after confirming the plugin
# runtime (observatory.py, induction.py, BarWidget.qml, bin/, app/) cannot reach
# it — grep before you extend this list.
ARGV_EXEMPT_PREFIXES = ("reports/", "tools/")


def tracked_python() -> list[Path]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                         capture_output=True, text=True, timeout=30)
    names = [n for n in out.stdout.split("\0") if n]
    files = [ROOT / n for n in names if n.endswith(".py")]
    # Extensionless scripts with a python shebang count too — a new spawn would
    # sit in bin/ just as happily as in a .py file.
    for n in names:
        p = ROOT / n
        if p.suffix or not p.is_file():
            continue
        try:
            if p.read_bytes()[:2] == b"#!" and b"python" in p.read_bytes()[:80]:
                files.append(p)
        except OSError:
            pass
    return sorted(set(files))


def argv_is_fixed(node: ast.AST) -> bool:
    """Is this call's argument list literal enough that no mined text fits in it?"""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return False           # a bare name or a built-up list: not provably fixed
    for el in node.elts:
        if isinstance(el, ast.Constant) and isinstance(el.value, str):
            continue
        if isinstance(el, ast.Name):
            continue           # a local holding an executable path
        return False           # subscript, call, f-string, concat — mined text fits
    return True


def check(path: Path) -> list[str]:
    rel = path.relative_to(ROOT)
    try:
        tree = ast.parse(path.read_text(), filename=str(rel))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [f"{rel}: could not parse ({exc})"]

    problems: list[str] = []
    sealed = path.name == SEALED

    for node in ast.walk(tree):
        # ---- claim 1: the sealed module imports nothing that can spawn
        if sealed and isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in SPAWN_MODULES:
                    problems.append(
                        f"{rel}:{node.lineno}: imports {a.name} — the module that "
                        f"reads mined ticket text must not be able to spawn")
        if sealed and isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in SPAWN_MODULES:
                problems.append(
                    f"{rel}:{node.lineno}: imports from {node.module} — the module "
                    f"that reads mined ticket text must not be able to spawn")

        # ---- claim 2: nobody reaches a raw fork/exec/shell primitive
        if isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name):
                if base.id == "os" and node.attr.startswith(OS_SPAWN_PREFIXES):
                    problems.append(f"{rel}:{node.lineno}: os.{node.attr}")
                if base.id == "pty" and node.attr == "spawn":
                    problems.append(f"{rel}:{node.lineno}: pty.spawn")
                if base.id == "subprocess" and node.attr == "Popen":
                    problems.append(
                        f"{rel}:{node.lineno}: subprocess.Popen — a detached child; "
                        f"use subprocess.run with a fixed argv")
                if node.attr.startswith("create_subprocess"):
                    problems.append(f"{rel}:{node.lineno}: asyncio {node.attr}")

        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "shell" and getattr(kw.value, "value", False) is True:
                    problems.append(f"{rel}:{node.lineno}: shell=True")

            # ---- claim 3: every surviving spawn carries a fixed argv
            fn = node.func
            spawns = (isinstance(fn, ast.Attribute)
                      and isinstance(fn.value, ast.Name)
                      and fn.value.id == "subprocess"
                      and fn.attr in ("run", "call", "check_call", "check_output",
                                      "Popen"))
            exempt = str(rel).startswith(ARGV_EXEMPT_PREFIXES)
            if spawns and node.args and not exempt \
                    and not argv_is_fixed(node.args[0]):
                problems.append(
                    f"{rel}:{node.lineno}: subprocess.{fn.attr} argv is not a fixed "
                    f"list of literals — mined text could reach it")
    return problems


def main() -> int:
    files = tracked_python()
    if not any(f.name == SEALED for f in files):
        print(f"spawn-gate: {SEALED} is not tracked — refusing to pass")
        return 1
    problems = [p for f in files for p in check(f)]
    if problems:
        print(f"spawn-gate: {len(problems)} problem(s) across {len(files)} tracked "
              f"python file(s)")
        for p in problems:
            print(f"  {p}")
        return 1
    exempt = sorted(str(f.relative_to(ROOT)) for f in files
                    if str(f.relative_to(ROOT)).startswith(ARGV_EXEMPT_PREFIXES))
    print(f"spawn-gate: {len(files)} tracked python file(s); {SEALED} imports no "
          f"spawn primitive, no shell/fork/exec anywhere, every argv fixed")
    if exempt:
        print(f"  argv-shape exemption ({len(exempt)} offline analysis scripts, "
              f"not reachable from the plugin runtime): {', '.join(exempt)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
