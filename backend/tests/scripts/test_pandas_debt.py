"""pandas_debt: the ONE measure behind the pandas hook, the touched-file row and the tree ratchet -- a code line whose
pandas RUNS (never a type) and that no verified edge excuses.

IMPORTERS/CALLERS: pytest. AFFECTED API: none. DATA SCHEMAS: none.
"""

from __future__ import annotations

from pathlib import Path

from src.lib.quality_gates import pandas_debt as debt

HERE = "apps/api/src/x.py"


def test_each_runtime_pandas_line_counts_once_and_types_need_no_marker() -> None:
    src = "\n".join([
        "from __future__ import annotations",
        "from typing import TYPE_CHECKING",
        "if TYPE_CHECKING:",
        "    import pandas as pd",                                # type-only: runs nothing
        "def f(x: pd.DataFrame) -> pd.Series:",                   # an annotation: runs nothing
        "    y = pd.concat([x, x]).apply(len)",                   # one line, two uses: counts once
        "    z = pd.Timestamp(0)  # PANDAS-OK: free text",        # a reason that names no callee excuses nothing
        "    return y",
    ])  # fmt: skip
    assert debt.runtime_debt(HERE, src) == 2


def test_a_pep695_type_parameter_or_type_alias_is_a_type_not_a_runtime_use() -> None:
    """Found moving htf_known (2026-10-16): `def f[T: (pd.Series, pd.DataFrame)]` read as pandas that runs. PEP 695 bounds,
    constraints, defaults and `type` alias values are evaluated lazily -- they never run, like any annotation."""
    src = "\n".join([
        "from __future__ import annotations",
        "from typing import TYPE_CHECKING",
        "if TYPE_CHECKING:",
        "    import pandas as pd",
        "def f[T: (pd.Series, pd.DataFrame)](x: T) -> T:",        # constraints
        "    return x",
        "class Box[F: pd.DataFrame = pd.DataFrame]:",             # a bound and a default
        "    pass",
        "type Frame = pd.DataFrame",                               # a type alias value
        "y = pd.Series([1])",                                      # canary: a runtime use still counts
    ])  # fmt: skip
    assert debt.runtime_debt(HERE, src) == 1


def test_prose_in_a_docstring_is_not_a_call() -> None:
    """Found by the hook itself (2026-10-14): this module's own docstring names `pd.concat` and was refused as a call.
    Lines inside a triple-quoted string are text -- also in an Edit fragment that does not parse."""
    src = '"""Uses pd.concat in prose.\n\nAlso df.apply( here.\n"""\nimport pandas as pd\nx = pd.concat(a)\ny = """one-line pd.read_csv"""\n'
    assert debt.runtime_debt(HERE, src) == 1
    assert debt.unexcused(debt.ROW_WISE, '    and df.apply( in a docstring\'s middle line\n    """\nz = s.apply(f)\n') == 2  # a fragment cannot tell


def test_a_marker_on_another_line_excuses_nothing() -> None:
    assert debt.runtime_debt(HERE, "# PANDAS-OK: all of it\nimport pandas as pd\nq = pd.Series(v)\n") == 1


def test_pandas_loop_sites_are_the_row_wise_and_growth_in_loop_shapes() -> None:
    """The pdperf-style shapes no ruff code covers (pdperf PPO001-005 / 007, MIT -- the design reference, not a
    dependency): row iteration, row-wise apply, a frame or array GROWN inside a loop (quadratic), index churn and scalar
    .loc / .iloc / .at / .iat access inside a loop, chained-index assignment."""
    import ast

    src = "\n".join([
        "for i, r in df.iterrows(): pass",                    # 1 iterrows
        "rows = [t for t in df.itertuples()]",                # 2 itertuples
        "s = df.apply(f, axis=1)",                            # 3 row-wise apply
        "g = df.groupby('k').apply(f)",                       # 4 groupby().apply (the inner .apply is the same call)
        "for x in xs:",
        "    out = pd.concat([out, x])",                      # 5 a frame GROWN by its own accumulator: quadratic
        "    arr = np.append(arr, x)",                        # 6 an array grown the same way
        "    v = df.loc[x, 'c'] + df.iat[0, 1]",              # 7 row access by the loop's own variable; [0, 1] is not
        "    part = pd.concat([a[x], b[x]])",                 #   one concat per iteration, nothing accumulated: not quadratic
        "    w = f.loc[lo:hi]",                               #   a slice per iteration (a fold, a window) is vectorised
        "    p.loc[test.index] = preds",                      #   a label-set write per fold is vectorised
        "    df = df.reset_index()",                          #   per-iteration preparation, not per-row work
        "report['columns'][col] = {}",                        #   chained subscript on dicts is not pandas
        "ok = pd.concat(parts)",                              #   outside a loop: one concat is the fix
        "lst = []",
        "for x in xs:",
        "    lst.append(x)",                                  #   a list append is PERF401's, not a frame's
        "for i in range(n):",
        "    if c.iloc[i] < st.iloc[i]: pass",                # 8, 9 the classic per-bar scalar read
    ])  # fmt: skip
    assert [kind for _, kind in debt.loop_sites(ast.parse(src))].count("row access by the loop variable") == 3
    assert debt.pandas_loop_sites(ast.parse(src), src) == 9


def test_the_tree_total_sums_every_runtime_python_file(tmp_path: Path) -> None:
    (tmp_path / "apps/api/src/a").mkdir(parents=True)
    (tmp_path / "apps/api/scripts").mkdir(parents=True)
    (tmp_path / "apps/api/tests").mkdir(parents=True)
    (tmp_path / "apps/api/src/a/m.py").write_text("import pandas as pd\nx = pd.Series([1])\n")
    (tmp_path / "apps/api/scripts/s.py").write_text("import pandas as pd\nrows = pd.read_csv(p).itertuples()\n")
    (tmp_path / "apps/api/tests/t.py").write_text("import pandas as pd\nx = pd.Series([1])\n")  # tests are not the runtime
    # the runtime lines only (an import runs nothing); row-wise shapes are the pandas-loop row's (pandas_loop_sites)
    assert debt.tree_debt(tmp_path) == {"apps/api/src/a/m.py": 1, "apps/api/scripts/s.py": 1}


def test_only_pandas_that_runs_is_counted_not_types() -> None:
    """EDGE-MARKER (2026-10-14): annotations, TYPE_CHECKING imports and quoted cast targets run no pandas."""
    from src.lib.quality_gates.pandas_debt import runtime_pandas_lines

    source = "\n".join([
        "from typing import TYPE_CHECKING, cast",          # 1
        "if TYPE_CHECKING:",                              # 2
        "    import pandas as pd",                         # 3 type-only
        "def f(x: pd.DataFrame) -> pd.Series:",            # 4 type-only
        "    y = cast('pd.Timestamp', x)",                 # 5 a string, not pandas
        "    z = pd.concat([x, x])",                       # 6 RUNS
        "    return z.to_pandas()",                        # 7 RUNS (a polars -> pandas conversion)
        "import pandas",                                   # 8 an import alone runs nothing (F401 if unused)
    ])  # fmt: skip
    assert runtime_pandas_lines(source) == {6, 7}


def test_a_marker_excuses_only_by_naming_a_pandas_typed_callee_on_its_line(tmp_path: Path) -> None:
    from src.lib.quality_gates.pandas_debt import verified_edge

    (tmp_path / "lab.py").write_text("import pandas as pd\ndef walk(f: pd.DataFrame) -> int: ...\ndef plain(x: int) -> int: ...\n")
    here = tmp_path / "engine.py"
    source = "import lab as L\n"
    assert verified_edge("    t = L.walk(x.to_pandas())  # PANDAS-OK: L.walk", source, here)
    assert not verified_edge("    t = L.walk(x.to_pandas())  # PANDAS-OK: the lab hands pandas", source, here)  # a phrase
    assert not verified_edge("    t = L.plain(x.to_pandas())  # PANDAS-OK: L.plain", source, here)  # no pandas in its signature
    assert not verified_edge("    t = x.to_pandas()  # PANDAS-OK: L.walk", source, here)  # named but not called here


def test_an_existing_pandas_api_keeps_its_contract_and_a_new_one_does_not(tmp_path: Path) -> None:
    """A function that already took / returned pandas BEFORE the edit may build the frames its callers read; a def
    annotated `-> pd.DataFrame` in the same edit buys nothing."""
    from src.lib.quality_gates.pandas_debt import pandas_apis, unexcused_runtime_lines

    before = "import pandas as pd\n\ndef features(f: pd.DataFrame) -> pd.DataFrame:\n    return f\n"
    after = "import pandas as pd\n\ndef features(f: pd.DataFrame) -> pd.DataFrame:\n    return pd.DataFrame(g(f), index=f.index)\n"
    here = tmp_path / "m.py"
    assert not unexcused_runtime_lines(after, here, apis=pandas_apis(before))
    sneaky = after + "\ndef new(x) -> pd.DataFrame:\n    return pd.concat([x])\n"
    assert sum(unexcused_runtime_lines(sneaky, here, apis=pandas_apis(before)).values()) == 1
