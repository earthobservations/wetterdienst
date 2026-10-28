# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every code a response warning can carry is told in the docs of the REST API (GH-3539)."""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

SRC = pathlib.Path(__file__).parent.parent / "src" / "wetterdienst"
DOCS = pathlib.Path(__file__).parent.parent / "docs" / "usage" / "restapi.md"
#: where the code is in the call of each function that raises a warning, by position (it may be given as `code=` too)
_CODE_ARGUMENT = {"warn_response": 1, "count_response_warning": 0}


def _constants(trees: list[ast.Module]) -> dict[str, str]:
    """Give the module-level names that are a text, by name: the constants a code is spelled by."""
    return {
        target.id: node.value.value
        for tree in trees
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def _code_of(node: ast.expr, constants: dict[str, str]) -> str | None:
    """Read the code a call is given as a text, a pattern with `*` where an f-string fills it in, or None if it can't.

    A text, a name or an attribute (`module.CONSTANT`) of a constant, an f-string.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.Attribute):
        return constants.get(node.attr)
    if isinstance(node, ast.JoinedStr):
        parts = [
            part.value if isinstance(part, ast.Constant) else "*"
            for part in node.values
            if isinstance(part, (ast.Constant, ast.FormattedValue))
        ]
        pattern = "".join(str(part) for part in parts)
        # a code that is filled in entirely (`f"{kind}"`) matches any documented code and so checks nothing
        return pattern if re.search(r"[a-z]", pattern) else None
    return None


def codes_in(trees: list[ast.Module]) -> tuple[set[str], list[int]]:
    """Give the codes of every call of `warn_response` and `count_response_warning`, and the lines of those not read."""
    constants = _constants(trees)
    codes: set[str] = set()
    unread: list[int] = []
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", None))
            if name not in _CODE_ARGUMENT:
                continue
            keyword = next((kw.value for kw in node.keywords if kw.arg == "code"), None)
            position = _CODE_ARGUMENT[name]
            argument = keyword if keyword is not None else node.args[position] if len(node.args) > position else None
            code = _code_of(argument, constants) if argument is not None else None
            if code is None:
                unread.append(node.lineno)
            else:
                codes.add(code)
    return codes, unread


def _source_trees() -> list[ast.Module]:
    return [ast.parse(path.read_text(encoding="utf-8")) for path in SRC.rglob("*.py")]


def test_every_warning_code_is_in_the_docs() -> None:
    """A client reads the codes it knows, so a code that is raised and not told there is one nobody can know."""
    codes, unread = codes_in(_source_trees())
    assert unread == [], "a code the scan cannot read is one the docs cannot be held to: spell it as a constant"
    assert {"unknown-station", "parameter-without-rows", "missing-value-marker"} <= codes, "the scan finds the codes"
    text = DOCS.read_text(encoding="utf-8")
    told = set(re.findall(r"`([a-z]+(?:-[a-z]+)+)`", text))
    missing = [
        code
        for code in sorted(codes)
        if not (any(re.fullmatch(code.replace("*", "[a-z-]+"), name) for name in told) if "*" in code else code in told)
    ]
    assert missing == []


# the scan reads every form a code is spelled in


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param('warn_response(log, "plain-code", "m")', {"plain-code"}, id="text"),
        pytest.param('warn_response(log, code="keyword-code", message="m")', {"keyword-code"}, id="keyword"),
        pytest.param('X = "named-code"\nwarn_response(log, X, "m")', {"named-code"}, id="constant"),
        pytest.param('X = "attribute-code"\nwarn_response(log, mod.X, "m")', {"attribute-code"}, id="attribute"),
        pytest.param('count_response_warning("counted-code", 1, "m")', {"counted-code"}, id="counted"),
        pytest.param(
            'count_response_warning(count=1, code="counted-keyword", message="m")', {"counted-keyword"}, id="k"
        ),
        pytest.param('warn_response(log, f"{kind}-skipped", "m")', {"*-skipped"}, id="f-string"),
        pytest.param('mod.warn_response(log, "method-code", "m")', {"method-code"}, id="called as an attribute"),
    ],
)
def test_the_scan_reads_each_form_a_code_is_spelled_in(source: str, expected: set[str]) -> None:
    """A text, a keyword, a constant by name or by attribute, a counted warning and an f-string are all read."""
    codes, unread = codes_in([ast.parse(source)])
    assert (codes, unread) == (expected, [])


def test_the_scan_reports_a_code_it_cannot_read() -> None:
    """A code that is computed is no code the docs can be held to, and the scan says where it is."""
    assert codes_in([ast.parse("warn_response(log, make_code(), 'm')")]) == (set(), [1])
    assert codes_in([ast.parse("warn_response(log)")]) == (set(), [1])
    # an f-string that is nothing but a field reads as any code, which checks nothing
    assert codes_in([ast.parse('warn_response(log, f"{kind}", "m")')]) == (set(), [1])
    assert codes_in([ast.parse('warn_response(log, f"{kind}-{other}", "m")')]) == (set(), [1])


def test_an_undocumented_code_is_found() -> None:
    """The check that holds the docs to the codes fails for a code the docs do not name."""
    codes, _ = codes_in([ast.parse('warn_response(log, "no-such-code-anywhere", "m")')])
    told = set(re.findall(r"`([a-z]+(?:-[a-z]+)+)`", DOCS.read_text(encoding="utf-8")))
    assert codes - told == {"no-such-code-anywhere"}


# the providers that tell the walk of a file they let go are the ones the docs name


def _names_of_the_note(tree: ast.Module) -> set[str]:
    """Give the names a module calls `note_skipped_download` by: its own name, and any `import ... as` alias of it."""
    names = {"note_skipped_download"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            names.update(alias.asname for alias in node.names if alias.name == "note_skipped_download" and alias.asname)
    return names


def _calls_the_note(tree: ast.Module) -> bool:
    """Tell whether a module calls `note_skipped_download` by name, by alias, or as an attribute of a module."""
    names = _names_of_the_note(tree)
    return any(
        isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in names
        for node in ast.walk(tree)
    )


def _providers_calling(trees_by_path: dict[pathlib.Path, ast.Module]) -> set[str]:
    """Give `provider/network` of every module under `provider/` that calls `note_skipped_download`."""
    return {
        "/".join(path.relative_to(SRC / "provider").parts[:2])
        for path, tree in trees_by_path.items()
        if _calls_the_note(tree)
    }


def _providers_documented(text: str) -> set[str]:
    """Give the `provider/network` the docs name between "This is done for" and the sentence on the other providers."""
    match = re.search(r"This\s+is\s+done\s+for\s+(.*?);\s+for\s+any\s+other\s+provider", text, flags=re.DOTALL)
    assert match, "the docs say which providers tell the walk of a file they let go"
    return set(re.findall(r"`([a-z_]+/[a-z_]+)`", match.group(1)))


def test_the_providers_that_let_a_file_go_are_the_ones_the_docs_name() -> None:
    """The claim and the code cannot drift: a provider that calls `note_skipped_download` is in the docs, and back.

    A helper outside `provider/` that calls it would hide which provider lets a file go, so there is none.
    """
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in SRC.rglob("*.py")}
    outside = sorted(
        str(path.relative_to(SRC))
        for path, tree in trees.items()
        if (SRC / "provider") not in path.parents and path.name != "response_warnings.py" and _calls_the_note(tree)
    )
    providers = {path: tree for path, tree in trees.items() if (SRC / "provider") in path.parents}
    called = _providers_calling(providers)
    documented = _providers_documented(DOCS.read_text(encoding="utf-8"))

    assert outside == [], (
        "a helper outside provider/ calls note_skipped_download: name its providers in the docs by hand"
    )
    assert len(called) >= 10, "the scan finds the providers"
    assert called == documented


def test_the_providers_scan_reads_each_call_and_the_docs_sentence() -> None:
    """A call by name or by attribute counts, a mention does not, and the docs sentence is read across its lines."""
    trees = {
        SRC / "provider" / "a" / "b" / "api.py": ast.parse(
            "from x import note_skipped_download\nnote_skipped_download()"
        ),
        SRC / "provider" / "c" / "d" / "api.py": ast.parse("mod.note_skipped_download(whole_request=True)"),
        SRC / "provider" / "e" / "f" / "api.py": ast.parse("from x import note_skipped_download"),
        SRC / "provider" / "g" / "h" / "api.py": ast.parse("from x import note_skipped_download as let_go\nlet_go()"),
    }
    assert _providers_calling(trees) == {"a/b", "c/d", "g/h"}
    assert _providers_documented("This is done for `a/b`,\n  `c/d` and `g/h`; for any other provider `x/y`") == {
        "a/b",
        "c/d",
        "g/h",
    }
