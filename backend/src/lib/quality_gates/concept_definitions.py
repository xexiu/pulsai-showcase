"""One concept, one definition: find a definition that repeats one another module already owns.

IMPORTERS/CALLERS: scripts/check_touched_debt.py (the ``duplicate-definition`` touch row),
scripts/verify.sh (``--tree`` ratchet), .claude/hooks/one_definition_guard.py (PreToolUse, at the
moment the definition is written), src/lib/quality_gates/recompute_in_loop.py and explicit_any.py (the shared
tree door ``ratchet_over_head``), tests/scripts/test_concept_definitions.py and test_control_flow_idioms.py. AFFECTED
API: none (library + CLI; ``--tree`` exits 1 when the count rises or falls unrecorded, 2 when the control-flow canary
fails; ``--idioms`` lists every loop that sleeps). DATA SCHEMAS: reads scripts/concept_owners.json (``concepts[]``:
concept, owner, also_owned_by, functions, enum_members, structures -- an idiom row owns ``poll-loop`` and the like).

WHY (owner, 2026-09-24): "Could be that I'm observing LOTS of duplicates for certifications ... No
SoT, centralized, shared? ... why hook wasnt fired for DRY, SoT, SRP violations ... FIX, proactive,
NOT only your case, future cases". Measured that day: seven forward-gate evaluators with different
math, four ``WARMING_UP`` enums, a 21-line badge builder in two files. Every DRY gate in the repo
compared TEXT (jscpd lines, gortex MinHash) or new FILE NAMES (reinvent_wheel_guard); the same idea
re-written in different code matched none of them, so none fired.

WHAT IT DETECTS, with no per-case wiring (the part that catches FUTURE cases):

* the same PUBLIC top-level function name defined in two or more modules of ``src/`` (product
  code AND the lab: one name, one meaning -- see ``GENERIC_NAME_SCOPE`` for why the lab joined it);
* an Enum whose member NAMES equal another module's Enum (>= 3 members) -- a mirror
  (``PortfolioBookCertState`` == ``ForwardPaperCertState``);
* a REGISTERED concept (concept_owners.json) defined outside its owner, by function name
  (leading underscores ignored, so ``_evaluate_gates`` is still the concept) or by an Enum carrying
  the concept's members. The registry is how a known concept names its home, so the refusal can
  say "import it from X" instead of only "this collides".

``main`` and ``hyp`` are exempt: every script's argparse entry point is ``main`` and every hypothesis module's
``@hypothesis`` plugin entry point is ``hyp``, one per file by convention. So are the live engine's plug-in names
(``PLUG_IN``: ``latest_candidate``, ``for_symbol``, ``run_replay``), one strategy per script core behind one interface.
Everything else that exists today is a measured baseline, paid down by the touch rule.

REUSE-AUDIT: considered scripts/check_duplicate_lines.py (copied LINES -- blind to a rewritten idea,
which is this module's whole subject), scripts/check_clone_baseline.py (gortex MinHash clusters,
same blindness, daemon-dependent), .claude/hooks/reinvent_wheel_guard.py (new file NAMES only) and
src/lib/quality_gates/tier_decision_baseline.py (money-tier words in research only). None reads definitions.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from src.lib.quality_gates.control_flow_idioms import CANARY_PATH, SleepSite, canary_holds, idiom_tags, node_name, sleep_sites, tag_idiom
from src.lib.quality_gates.ratchet_touch import ARCHIVE_SEGMENT, git, text_key, write_json_atomic

_API = Path(__file__).resolve().parents[3]

#: Where a concept may be (re)defined and so where the rule applies. Tests are excluded: a test
#: re-declaring a fixture helper is not a second home for a production concept.
SCOPE_PREFIXES: tuple[str, ...] = ("apps/api/src/", "apps/api/scripts/")
#: ``_archive/`` (ARCHIVE-EXEMPT, ratchet_touch.ARCHIVE_SEGMENT): KILL evidence is out of every tree ratchet that reads
#: through ``in_scope`` -- this one, expression clones, standards rules, recompute-in-loop and explicit Any.
EXCLUDED_SEGMENTS: tuple[str, ...] = ("/artifacts/", "/__pycache__/", ARCHIVE_SEGMENT)
#: The live engine's plug-in names (mexc_demo.engine_scripts.Script: candidate / for_symbol / replay): each script core
#: fills them with its own strategy, one per module by design -- the shape of `main` (LIVE28, 2026-10-17: 12 findings,
#: 12 definitions, 11 findings, none payable but by a rename the registry forbids).
PLUG_IN: frozenset[str] = frozenset({"latest_candidate", "for_symbol", "run_replay"})
ENTRYPOINT_NAMES: frozenset[str] = frozenset({"main", "hyp"}) | PLUG_IN
#: Where the GENERIC same-name rule applies: all of src/, the lab included (owner, 2026-10-16: "should look on all src/*
#: folder and files"). It used to be product code only -- measured 2026-09-24: 100 in src/, 956 in src/research -- on the
#: reasoning that a lab rename satisfies the rule while fixing nothing. The cost of that carve-out was measured on
#: 2026-10-16 (DRY-AUDIT): the SOL v2 grade the owner was deciding real money on ran three graders and 13 money-simulator
#: sites (Kelly f* defined as `kelly` in two lab modules among them), and no door saw one. Blind is worse than gameable.
GENERIC_NAME_SCOPE: tuple[str, ...] = ("apps/api/src/",)
#: The lab root, as the gate tooling spells it (rule_spec, standards_rules and check_commit_pattern_statement read it).
GENERIC_NAME_LAB: str = "apps/api/src/research/"


def _generic(path: str) -> bool:
    return path.startswith(GENERIC_NAME_SCOPE)


#: The SoT layer. A public top-level function here OWNS its name across the whole scope, lab included and leading
#: underscores ignored, with no registry row (owner, 2026-09-30: "auto detect DRY ... for EVERYTHING"). Measured that
#: day: 61 same-named copies of the 386 public src/shared helpers (ema x12, max_drawdown x6, bars_per_day x4, utc_now x4)
#: that no door saw -- private names, or in the lab, and never registered.
SHARED_OWNER_SCOPE: tuple[str, ...] = ("apps/api/src/shared/",)
ENUM_BASES: frozenset[str] = frozenset({"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag"})
MIN_ENUM_MEMBERS = 3
REGISTRY_PATH = _API / "scripts" / "concept_owners.json"
REGISTRY_REL = REGISTRY_PATH.relative_to(_API.parents[1]).as_posix()
#: Findings over the whole scope, measured 2026-09-24 when this gate was written. A RATCHET: it
#: may only fall, and ``--tree`` fails when it falls unrecorded so a paid debt cannot become
#: headroom. The touch rule (check_touched_debt) is what drives it down.
#: 2026-09-24: 66 -> 58, measured on the committed tree (the scan excludes tests, the only
#: uncommitted file): FORWARD-GATE-SOT-1 (7d9ade896) plus the two duplicates FEE-ZERO-1 and
#: OHLCV-FRESH-1 paid on touch (slim_capital_cert_from_inventory_report, registered_keys).
#: 2026-09-25: 58 -> 55, all three paid on touch in 1155857fd: arena's compare handler renamed
#: compare_models_head_to_head (a different endpoint that only shared models.py's name; its
#: operationId pinned), which clears both of the pair's rows, and the arena_helpers
#: get_model_storage pass-through deleted.
#: 2026-09-30: 53 -> 99, NOT new debt -- existing debt newly SEEN: SHARED_OWNER_SCOPE made every public src/shared
#: function own its name, and 46 top-level same-named copies surfaced (35 lab / ops scripts, 11 product code: _repo_root
#: x5, _wf_rank_ic x4, _bars_per_day x3, ema / _ema, max_drawdown, per_period_sharpe ...). Paid down on touch.
#: 2026-10-02: 99 -> 95, measured by `--tree` on a clean checkout of 1730d9e0a (1b0f0554f merged two mirrored
#: trade-action enums into SignalAction; the rest paid down on touch).
#: 2026-10-02: 95 -> 93, measured by verify on 2056b5819: the training-job sync_get_by_id became
#: sync_get_training_job_by_id, so neither it nor backtest_repository's copy is a finding any more.
#: 2026-10-03: 93 -> 92, measured by verify on ddab09c72: funding_rate_fetcher._timeframe_hours re-defined
#: model_deploy_policy.timeframe_hours and now imports it (325f02bab).
#: 2026-10-04: 92 -> 91, measured by verify on 4e18b6d37 and `--tree` on 0de6a7c0e: MONEY-ONE-SOT (0cf906971)
#: deleted the metric escalation helpers, one of which repeated another module's concept.
#: 2026-10-05: 91 -> 82, measured by `--tree` at origin/master 2ad861b6a (91) and by verify on 2e1df8d4e (82):
#: the batch 2ad861b6a..2e1df8d4e (lab-debt merge, god-file splits) removed nine repeated definitions.
#: 69 -> 68 on the P1-0 commit (feat(cert) risk-sized book: capital_cert_headline's _max_drawdown named for what it does -- it reads a field).
# 82 -> 76 by verify 2026-10-05; 76 -> 75 on 4a4831f84; 75 -> 74 on 8ee516ec8; 74 -> 69 by verify on fe1fe32fb;
# 68 -> 66 on 2026-10-09 (P3-0d: the connection service's dead copy of require_non_free_tier_for_exchange_connect).
# 66 -> 67 on 2026-10-12, NOT new debt -- existing debt newly SEEN: RECONNECT_LOOP made the websocket reconnect loop a
# registered structure (owner exchange/trade_stream.py), and binance_kline_websocket_stream's loop predates it. Paid on
# touch: that stream becomes a TradeProtocol (or a reader on TradeStream's loop) when it is next changed.
# 67 -> 65 (2026-10-16, GATE-RED: measured at c9f50859d; paid on touch, never locked).
# 65 -> 1075 (2026-10-16, ONE-DEF-LAB), NOT new debt -- existing debt newly SEEN: the lab joined the same-name rule (998
# lab findings; 77 product / scripts, a product name copied into the lab now counts on both sides). `hyp` exempt like
# `main` (237 @hypothesis entry points), _archive/ out of it (21 unpayable). Top copies: run_tf x107 (a per-script
# runner where hunt_loop_runner is the home), ann_sr x29, dsr x21, sharpe x13, maxdd x10. Paid on touch.
# 1075 -> 1076 the same commit, also newly SEEN: the discrete Kelly row in concept_owners.json makes
# position_sizers.kelly_notional_usd a finding (same f* as the domain's half_kelly: 0.182143 both on one sample).
# 1076 -> 1075 (MONEY-ONE): +1 newly SEEN -- money_paths' registry rows make growth87.kelly a finding (the same mean /
# variance f*, on day returns with the population variance; cert87 imports growth87, so growth87 cannot import
# money_paths while that import stands); -2 paid -- cert87.first_day_at, a different question from capacity_a87's
# (compounded equity reaching a target, not one day's P&L), renamed first_day_equity_reaches.
# 1075 -> 1062 at 888fc82c1 / 324f974f5 (2026-10-17), paid and locked late: coin_required's two copies became one
# (engine_scripts) and the LIGHTER-GRADE commit paid its own; 1062 -> 1051 (LIVE28 4/n): the live engine's plug-in
# names (PLUG_IN: 12 definitions, 11 findings) are exempt like `main` -- one strategy per script core, one interface.
# 1043 -> 1037 (2026-10-18): the 10-17 slices' unlocked fall, measured by `--tree` at 781ecc088 (PANDAS-OUT 1/2's
# chart_summary / draw_chart / buy_and_hold_curve renames and the S1 engine split), locked in SAME-VALUE.
# 1037 -> 1036 (2026-10-18, BACKTEST-ONE S2b: the engine's kelly_notional_usd calls the domain's discrete_kelly_fraction).
#: -> 1031 (10-18, GIT-CLEAN 2: binance_vision_metrics / data_1m / sltp_multicoin / arm87_model paid on touch; clean tree).
#: -> 1020 (10-18, STOP-GAP: the EMA's one home, prod_xs_regime_fifo_source, load_shortlist and buy-and-hold one each; the
#: lab's ccxt column extractor named ohlcv_column_lists, not kline_columns' ohlcv_columns; clean tree).
#: -> 1018 (10-19, 8b-RSI + 8b-ATR, measured at the commit's own HEAD): the RSI concept row names the RSI copies, so the 15
#: the owner's scope cut left in place (chart_indicators, tv_rule_primitives, the *_sa scripts, ...) now read as second homes
#: (+15, existing debt newly seen, paid on touch in 8b INDICATORS-HOME) while 3 same-name findings went (-3). 8b-RSI's
#: 1006 was read off the previous HEAD's blobs (this ratchet reads HEAD, not the working tree), so it never held.
#: -> 1014 (10-19, 8b-ATR part 2, at the commit's own tree): tv_rule_primitives._ema gone, ts_rule_zoo's per_year and
#: hyp_ts_rule_zoo renamed to what they compute (sharpe_and_return_by_year, ts_rule_zoo_cells) beside the shim.
#: -> 1011 (10-19, 8b-EMA part 1 at the commit's own tree: chart / target / shared EMA copies gone, titan's dead one too).
#: -> 1006 (10-19, GIT-CLEAN-1 article_ml / gb_pine at the commit's own tree: gb_pine's refit named for what it refits,
#: the arm's scorer and bar loader one home each in article_ml).
#: -> 1002 (10-19, SOL-RESTART-DIVERGENCE lock, measured at the commit's own tree).
#: -> 998 (10-20, HEAD-RED: the legacy training-job routes that repeated admin/training's are deleted; commit's own tree).
#: -> 995 (10-20, 8f FIFO-BLIND: DETECTOR_CANNOT_RUN, HLCV_COLUMNS and UNLOADABLE_BUNDLE_ERRORS one home each; commit's own tree).
#: -> 994 (10-21, SOL-5M-V2-FEATURES: the training CLI's build_parser named build_training_parser; commit's own tree).
#: -> 990 (10-22, SOL-SHORTLIST-RECIPE: the training catalog reads UI_TRAINING_MODEL_TYPES, its own _UI_TYPES copy gone).
#: -> 988 (10-23, SOL-SWITCH C1: leadlag_core's candidate_frame is lag_candidates on book87.candidate_frame, and
#: leadlag_replay's parity is trade_differences; working tree measured before the commit).
#: -> 982 (10-23, SWITCH-LUCK-CHECK: rolling_origin_cadence_validator imports build_panel / annualized_sharpe and
#: forward_paper_certification the drawdown, block_bootstrap.max_drawdown renamed; commit's own tree).
#: -> 977 (10-24 lock, LIVE-SOL-BOTH's gate run, measured on the tree that commit carries).
#: -> 974 (10-28 ENGINE-PERF-BUGS lock: f635c7da1 already read 974, a fall left unlocked; the commit's tree reads the same).
#: -> 973 (10-29 NEWS-ARMS lock: MEASURED on HEAD 1351d919d by verify --fast 2f-def, a fall since the 10-28 lock left
#: unlocked; this commit's tree reads the same).
#: -> 1044 (11-07 GATE-IDIOMS), NOT new debt -- existing debt newly SEEN: every loop that sleeps is a structure now
#: (control_flow_idioms), and the four idiom rows (poll / retry / pace / schedule) make 77 hand-written loops outside their
#: homes findings, one per loop; the other 967 are the same-name / registry findings (973 at the last lock, the fall since
#: never locked). Measured by `--list` over the working tree the commit carries. Paid on touch, a timing test with each.
#: -> 1037 (11-08 WORDS-WRITTEN 1, the cross-coin batch: engine_loop.Engine.run's schedule loop moved onto
#: scheduling.run_then_wait with its timing test; the other 6 a fall left unlocked; measured on HEAD with only this
#: commit's diff applied, in a scratch worktree).
BASELINE_FINDINGS = 1034


#: A STRUCTURE the registry can own, matched by shape rather than name (owner, 2026-10-12: "ready for future exchanges?
#: bitget, okx"): a websocket reconnect loop -- `while True` around `async with ...`, an `except`, and a `.sleep(` back
#: off. The first MEXC trade stream carried its own in a venue module; name and body detectors see only a SECOND copy,
#: and a renamed one not even then. Its owner is trade_stream.TradeStream; a venue supplies a TradeProtocol, not a loop.
RECONNECT_LOOP = "websocket-reconnect-loop"
#: A one-line CONVERSION the registry can own by shape (EPOCH-MS-HOME, owner 2026-10-12: "why hooks, verify, etc didnt
#: catched your DRY ... violations"): pandas times -> epoch ms. Its home had a name and it was still re-derived inline 8
#: times -- a copy inside another function has no name, no block and no body for the other detectors to compare, and
#: the ns-assuming divide is the copy that corrupted 220 cached parquets and every bar LTF-GRID built.
EPOCH_MS_CONVERSION = "epoch-ms-conversion"
NS_PER_MS = 1_000_000


@dataclass(frozen=True)
class Definitions:
    """The concept-bearing definitions one module makes."""

    functions: frozenset[str]
    enums: tuple[tuple[str, frozenset[str]], ...]
    structures: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Concept:
    """One registered concept: its name, the module(s) that own it, and the functions, Enum members and code shapes that
    mark a second home of it."""

    concept: str
    owners: frozenset[str]
    functions: frozenset[str]
    enum_members: frozenset[str]
    structures: frozenset[str] = frozenset()
    #: The row's declared owner -- the home a refusal names; its `also_owned_by` modules are homes but never named.
    home: str = ""


def _is_reconnect_loop(loop: ast.While) -> bool:
    if not (isinstance(loop.test, ast.Constant) and loop.test.value is True):
        return False
    inner = list(ast.walk(loop))
    sleeps = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "sleep" for n in inner)
    return sleeps and any(isinstance(n, ast.AsyncWith) for n in inner) and any(isinstance(n, ast.ExceptHandler) for n in inner)


def _is_as_unit_ms(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "as_unit"
            and any(isinstance(a, ast.Constant) and a.value == "ms" for a in node.args))  # fmt: skip


def _is_astype_int64(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "astype"
            and any(isinstance(a, ast.Constant) and a.value == "int64" for a in node.args))  # fmt: skip


def _is_epoch_ms_conversion(node: ast.AST) -> bool:
    """`.as_unit("ms")` read out as integers (`.asi8` / `.astype("int64")`), or the divide that assumes nanoseconds."""
    if isinstance(node, ast.Attribute) and node.attr == "asi8":
        return _is_as_unit_ms(node.value)
    if _is_astype_int64(node) and isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _is_as_unit_ms(node.func.value)
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.FloorDiv)):
        return False
    divides_ns = isinstance(node.right, ast.Constant) and node.right.value == NS_PER_MS
    as_integers = (isinstance(node.left, ast.Attribute) and node.left.attr == "asi8") or _is_astype_int64(node.left)
    return divides_ns and as_integers


def _structures(tree: ast.Module, lines: Sequence[str] = ()) -> frozenset[str]:
    """The code shapes a registry row can own: the reconnect loop, the epoch-ms conversion, and one tag per loop that
    sleeps (control_flow_idioms, GATE-IDIOMS: ``poll-loop@OilPart._served``) -- a reconnect loop is never also a retry."""
    found: set[str] = {EPOCH_MS_CONVERSION} if any(_is_epoch_ms_conversion(node) for node in ast.walk(tree)) else set()
    if _reconnect_loops(tree):
        found.add(RECONNECT_LOOP)
    return frozenset(found) | idiom_tags(idiom_sites(tree, lines))


def _reconnect_loops(tree: ast.Module) -> list[ast.While]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.While) and _is_reconnect_loop(node)]


def idiom_sites(tree: ast.Module, lines: Sequence[str]) -> list[SleepSite]:
    """Every loop that sleeps (control_flow_idioms), the websocket reconnect loops left out -- RECONNECT_LOOP owns them;
    the one call both the gate's tags and ``--idioms`` read, so the listing can never disagree with the gate."""
    return sleep_sites(tree, lines, skip=_reconnect_loops(tree))


def in_scope(path: str) -> bool:
    """Whether a repo-relative path is a Python file this detector judges (inside SCOPE_PREFIXES, no excluded segment)."""
    return path.endswith(".py") and path.startswith(SCOPE_PREFIXES) and not any(s in path for s in EXCLUDED_SEGMENTS)


def definitions_in(source: str) -> Definitions:
    """Top-level public functions and Enum member-name sets; an unparseable text defines nothing."""
    try:
        tree = ast.parse(source)
    except SyntaxError, ValueError:
        return Definitions(frozenset(), ())
    functions: set[str] = set()
    enums: list[tuple[str, frozenset[str]]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.add(node.name)
        elif isinstance(node, ast.ClassDef) and ENUM_BASES & {node_name(b) for b in node.bases}:
            members = frozenset(
                target.id
                for stmt in node.body
                if isinstance(stmt, ast.Assign)
                for target in stmt.targets
                if isinstance(target, ast.Name) and not target.id.startswith("_")
            )
            enums.append((node.name, members))
    return Definitions(frozenset(functions), tuple(enums), _structures(tree, source.splitlines()))


def load_registry(path: Path = REGISTRY_PATH) -> tuple[Concept, ...]:
    """The concept registry on disk (concept_owners.json)."""
    return parse_registry(path.read_text(encoding="utf-8"))


def registry_at_ref(repo: Path, ref: str) -> tuple[Concept, ...]:
    """The registry as committed at ``ref`` -- judge a commit's sources by that commit's owners."""
    return parse_registry(git(repo, "show", f"{ref}:{REGISTRY_REL}").decode("utf-8"))


def parse_registry(text: str) -> tuple[Concept, ...]:
    """The registry JSON as Concepts; an owner's `also_owned_by` modules count as its homes too."""
    document = json.loads(text)
    return tuple(
        Concept(
            concept=str(item["concept"]),
            owners=frozenset([str(item["owner"]), *map(str, item.get("also_owned_by", []))]),
            functions=frozenset(map(str, item.get("functions", []))),
            enum_members=frozenset(map(str, item.get("enum_members", []))),
            structures=frozenset(map(str, item.get("structures", []))),
            home=str(item["owner"]),
        )
        for item in document["concepts"]
    )


def _public(name: str) -> bool:
    return not name.startswith("_") and name not in ENTRYPOINT_NAMES


def _shared_copies(path: str, defs: Definitions, others: Mapping[str, Definitions], reported: set[str]) -> list[str]:
    """Definitions in ``path`` that re-define a public src/shared function by name (leading underscores ignored).

    Names the generic rule already reported for this file are skipped, so a public product-code copy counts once.
    """
    if path.startswith(SHARED_OWNER_SCOPE):
        return []
    owners = {name: other for other, d in others.items() if other.startswith(SHARED_OWNER_SCOPE) for name in d.functions if _public(name)}
    copies = sorted(n for n in defs.functions if n.lstrip("_") in owners and n not in reported)
    return [
        f"{path}: {name} re-defines {owners[name.lstrip('_')]}::{name.lstrip('_')} -- import it; if it computes "
        "something different, name that difference (CODING_STANDARDS 2.2: similar code != same responsibility)"
        for name in copies
    ]


def findings_for(path: str, defs: Definitions, index: Mapping[str, Definitions], registry: Iterable[Concept]) -> list[str]:
    """Every definition in ``path`` that repeats another module's, or a registered concept's home."""
    found: list[str] = []
    others = {other: d for other, d in index.items() if other != path}
    generic = _generic(path)
    reported: set[str] = set()
    for name in sorted(n for n in defs.functions if generic and _public(n)):
        homes = sorted(other for other, d in others.items() if _generic(other) and name in d.functions)
        if homes:
            found.append(f"{path}: def {name} is also defined in {', '.join(homes[:3])}")
            reported.add(name)
    found.extend(_shared_copies(path, defs, others, reported))
    for enum_name, members in defs.enums:
        if len(members) < MIN_ENUM_MEMBERS:
            continue
        mirrors = sorted(f"{other}::{n}" for other, d in others.items() for n, m in d.enums if m == members)
        if mirrors:
            found.append(f"{path}: enum {enum_name} mirrors {', '.join(mirrors[:3])} (same members)")
    for concept in registry:
        if path in concept.owners:
            continue
        named = sorted(n for n in defs.functions if n.lstrip("_") in concept.functions)
        carried = sorted(n for n, m in defs.enums if concept.enum_members and concept.enum_members <= m)
        shaped = sorted(s for s in defs.structures if tag_idiom(s) in concept.structures)
        home = concept.home or sorted(concept.owners)[0]
        found.extend(f"{path}: {name} re-defines '{concept.concept}', which lives in {home} -- import it" for name in named + carried + shaped)
    return found


#: The parsed-definitions cache (check_touched_debt passes git_cache_file(repo, DEFINITIONS_CACHE)): text hash -> row.
#: v2 (GATE-IDIOMS): rows now carry one structure tag per sleeping loop, so a v1 row of an unchanged text would hide them.
DEFINITIONS_CACHE = "pulsai-concept-definitions-v2.json"
#: Below this many unparsed texts the parse runs inline; a process pool costs more than it saves.
PARSE_POOL_FROM = 200


def _row(d: Definitions) -> list[object]:
    return [sorted(d.functions), [[name, sorted(members)] for name, members in d.enums], sorted(d.structures)]


#: One cached row as JSON holds it: (functions, [(enum, members)], structures) -- asserted at this one boundary.
_Row = tuple[list[str], list[tuple[str, list[str]]], list[str]]


def _from_row(row: object) -> Definitions:
    functions, enums, structures = cast("_Row", row)
    return Definitions(frozenset(functions), tuple((name, frozenset(members)) for name, members in enums), frozenset(structures))


def _read_cache(path: Path) -> dict[str, Definitions]:
    try:
        return {key: _from_row(row) for key, row in json.loads(path.read_text(encoding="utf-8")).items()}
    except OSError, ValueError, TypeError, AttributeError:
        return {}


def _write_cache(path: Path, rows: Mapping[str, Definitions]) -> None:
    write_json_atomic(path, {key: _row(d) for key, d in rows.items()})


def index_from_sources(sources: Mapping[str, str], cache: Path | None = None) -> dict[str, Definitions]:
    """Every in-scope module's Definitions. With `cache` (a file), an unchanged text is read back instead of parsed --
    measured 2026-10-13: parsing all 3,707 modules was 35 s of check_touched_debt's 54 s on every commit."""
    scoped = {path: text for path, text in sources.items() if in_scope(path)}
    if cache is None:
        return {path: definitions_in(text) for path, text in scoped.items()}
    keys = {path: text_key(text) for path, text in scoped.items()}
    known = _read_cache(cache)
    missing = {key: scoped[path] for path, key in keys.items() if key not in known}
    if len(missing) < PARSE_POOL_FROM:
        known.update({key: definitions_in(text) for key, text in missing.items()})
    else:
        with ProcessPoolExecutor() as pool:
            known.update(zip(missing, pool.map(definitions_in, missing.values(), chunksize=32), strict=True))
    wanted = set(keys.values())
    if missing or len(known) != len(wanted):
        _write_cache(cache, {key: known[key] for key in wanted})
    return {path: known[key] for path, key in keys.items()}


def sources_at_ref(repo: Path, ref: str) -> dict[str, str]:
    """Every in-scope file's text at ``ref``, in one ``git cat-file --batch`` round trip."""
    listing = git(repo, "ls-tree", "-r", "-z", "--name-only", ref, "--", *SCOPE_PREFIXES).decode().split("\0")
    paths = [p for p in listing if p and in_scope(p)]
    if not paths:
        return {}
    raw = git(repo, "cat-file", "--batch", stdin="".join(f"{ref}:{p}\n" for p in paths).encode())
    texts: dict[str, str] = {}
    cursor = 0
    for path in paths:
        header_end = raw.index(b"\n", cursor)
        size = int(raw[cursor:header_end].split()[2])
        start = header_end + 1
        texts[path] = raw[start : start + size].decode("utf-8", errors="replace")
        cursor = start + size + 1
    return texts


def ratchet_over_head(repo: Path, label: str, floor: int, verdict: Callable[[dict[str, str]], tuple[int, list[str]]]) -> int:
    """The door the whole-tree ratchets share (recompute-in-loop, explicit Any): read every in-scope file at HEAD,
    refuse a scan of fewer than ``floor`` files -- a scope mistake reads as a clean tree -- then print ``verdict``'s
    report and return its exit code."""
    sources = sources_at_ref(repo, "HEAD")
    if len(sources) < floor:
        print(f"{label}: read {len(sources)} files at HEAD (< {floor}) -- the scope is wrong, nothing was measured")
        return 1
    code, lines = verdict(sources)
    print("\n".join(lines))
    return code


def sources_on_disk(repo: Path) -> dict[str, str]:
    """Every in-scope file's text in the working tree, by repo-relative path."""
    texts: dict[str, str] = {}
    for prefix in SCOPE_PREFIXES:
        for file in (repo / prefix).rglob("*.py"):
            rel = str(file.relative_to(repo))
            if in_scope(rel):
                texts[rel] = file.read_text(encoding="utf-8", errors="replace")
    return texts


def tree_findings(index: Mapping[str, Definitions], registry: Iterable[Concept]) -> list[str]:
    """Every second home over the whole index, file by file in path order."""
    concepts = tuple(registry)
    found: list[str] = []
    for path in sorted(index):
        found.extend(findings_for(path, index[path], index, concepts))
    return found


def ratchet_tree(repo: Path, baseline: int = BASELINE_FINDINGS) -> int:
    """The HEAD ratchet: 1 when the finding count moved off `baseline` either way (a rise is a new second home, a fall must
    be locked), 0 when it holds; 2 when the idiom canary fails -- the count would then be measuring nothing."""
    if not canary_holds():
        print(f"one definition: the control-flow canary ({CANARY_PATH.name}) no longer reads as three polls -- this run measured nothing")
        return 2
    found = tree_findings(index_from_sources(sources_at_ref(repo, "HEAD")), registry_at_ref(repo, "HEAD"))
    print(f"one definition: {len(found)} findings (baseline {baseline})")
    if len(found) > baseline:
        print("A concept gained a second home -- import the one that exists (see --list), never raise the baseline.")
        return 1
    if len(found) < baseline:
        print(f"below baseline -- lower BASELINE_FINDINGS to {len(found)} in src/lib/quality_gates/concept_definitions.py to lock the gain")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI: --list prints every finding over the working tree; otherwise the HEAD ratchet's exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--tree", action="store_true", help="ratchet the total over HEAD (verify.sh)")
    parser.add_argument("--list", action="store_true", help="print every finding over the working tree")
    parser.add_argument("--idioms", action="store_true", help="print every loop that sleeps, unclassified ones included")
    parser.add_argument("--repo-root", type=Path, default=_API.parents[1])
    args = parser.parse_args(argv)
    if args.idioms:
        for path, text in sorted(sources_on_disk(args.repo_root).items()):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for site in idiom_sites(tree, text.splitlines()):
                print(f"{path}:{site.line} {site.idiom} {site.function}")
        return 0
    if args.list:
        for line in tree_findings(index_from_sources(sources_on_disk(args.repo_root)), load_registry()):
            print(line)
        return 0
    return ratchet_tree(args.repo_root)


if __name__ == "__main__":
    sys.exit(main())
