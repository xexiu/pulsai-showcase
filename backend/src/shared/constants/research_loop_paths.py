"""Canonical repo paths for research-loop orchestration (SoT)."""

from __future__ import annotations

from pathlib import Path

from src.shared.constants.fees import FeeSchedule
from src.shared.constants.paths import API_ROOT_PATH, ARTIFACT_ROOT_REL, RESEARCH_ROOT_REL


def _resolve_repo_root() -> Path:
    """Repo root, resolved defensively so this module can never fail to import.

    Local monorepo: ``<root>/apps/api/src/shared/constants/this.py`` — the root carries ``.git``, so
    walking up to it reproduces the previous ``parents[5]`` behaviour. The prod container flattens the
    tree to ``/app/src/...`` (no ``.git``, fewer parents), where the hard-coded ``parents[5]`` raised
    ``IndexError`` at import and took the whole app down. Fall back to the shallowest safe parent.

    Artifact files under ``apps/api/src/research/...`` must use :func:`resolve_apps_api_rel` /
    :func:`api_package_root` — joining ``apps/api/...`` onto this root yields ``/apps/api/...`` in
    Docker (wrong); the image ships them at ``/app/src/research/...``.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    parents = here.parents
    return parents[min(5, len(parents) - 1)]


_REPO_ROOT = _resolve_repo_root()
_APPS_API_PREFIX = "apps/api/"
#: `RESEARCH_ROOT_REL` / `ARTIFACT_ROOT_REL`, apps/api-ROOT-relative (with the "apps/api/" prefix
#: every other `*_REL` constant below uses). Every constant in this module composes from one of
#: these two — the root itself is spelled ONCE, in shared.constants.paths.
_RESEARCH_ROOT_APPS_API_REL = f"{_APPS_API_PREFIX}{RESEARCH_ROOT_REL}"
_ARTIFACT_ROOT_APPS_API_REL = f"{_APPS_API_PREFIX}{ARTIFACT_ROOT_REL}"
#: Same name with a trailing slash, for startswith()/removeprefix() prefix-drift normalisation
#: (registry_leaf_capital_cert_rows.py's known-drift anchor table).
RESEARCH_SCRIPTS_DIR_PREFIX = f"{RESEARCH_ROOT_REL}/"


def api_package_root() -> Path:
    """``apps/api`` in the monorepo, ``/app`` in the flattened Docker image.

    Same fact as ``paths.API_ROOT_PATH`` — one parents[N] implementation, not a fork.
    """
    return API_ROOT_PATH


def resolve_apps_api_rel(rel: str) -> Path:
    """Resolve a monorepo-relative ``apps/api/...`` path (or pass through other rels via repo root)."""
    if rel.startswith(_APPS_API_PREFIX):
        return api_package_root() / rel.removeprefix(_APPS_API_PREFIX)
    return _REPO_ROOT / rel


# THESE TWO STAY AT THE REPO ROOT, OUTSIDE THE IMAGE, DELIBERATELY. Measured 2026-09-14, both
# targets named: prod answers `queue_source=no_record` while localhost answers `container_disk`
# with 6 entries, because the `apps/api` Docker build context (the Dockerfile declares it in its
# own header) cannot reach a repo-root path. Moving them under `src/research/artifacts/` would
# put them in the image and was tried and REVERTED the same hour: the queue is a WORK QUEUE the
# checker writes status transitions into, classified role 2 (runtime-written) in
# tests/unit/infrastructure/test_runtime_artifacts_ship.py on 2026-09-04 with the reason that a
# baked copy would replay finished work. That classification still holds.
#
# What prod is therefore owed is NOT a baked file: the worker must READ the queue from the shared
# `research_loop_corpus` row it already writes, so curated input and advancing state live in one
# place that survives a container restart. Until then a prod tick answers SKIPPED_NO_QUEUED, which
# is why the status endpoint naming that absence (rather than rendering it as an empty queue) is
# load-bearing.
HYPOTHESIS_QUEUE_REL = "artifacts/oos_hunt/HYPOTHESIS_QUEUE.json"
LOOP_STATE_REL = "artifacts/oos_hunt/LOOP_STATE.md"
LAST_RESEARCH_LOOP_TICK_REL = "artifacts/oos_hunt/last_research_loop_tick.json"

EDGE_BOOK_FORWARD_ENTRY_PREFIX = "edge-book"
XS_OI_FORWARD_ENTRY_PREFIX = "xs-oi"
XS_TREND_FORWARD_ENTRY_PREFIX = "xs-trend"
VT_17_MOMENTUM_FORWARD_ENTRY_PREFIX = "vt-17-momentum"
VRP_FORWARD_ENTRY_PREFIX = "vrp-short-vol"

# Paper-forward JSONL tapes (research scripts). Edge-book admin certification uses DB tape.
EDGE_BOOK_FORWARD_TAPE_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/oos_hunt/edge_book_forward_tape.jsonl"
XS_OI_FORWARD_TAPE_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/oos_hunt/xs_oi_momentum_forward_tape.jsonl"
XS_TREND_FORWARD_TAPE_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/xs_trend_portfolio/forward_tape.jsonl"
VT_17_MOMENTUM_FORWARD_TAPE_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vt_17_momentum/forward_tape.jsonl"
VRP_FORWARD_TAPE_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vol_risk_premium/forward_tape.jsonl"
XS_TREND_FROZEN_CONFIG_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/xs_trend_portfolio/frozen_config.json"
VT_17_MOMENTUM_FROZEN_CONFIG_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vt_17_momentum/frozen_config.json"
VT_17_MOMENTUM_FROZEN_BY_TIMEFRAME_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vt_17_momentum/frozen_by_timeframe.json"
FUNDING_ML_CARRY_FROZEN_CONFIG_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/funding_ml_carry/frozen_config.json"
VRP_FROZEN_CONFIG_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vol_risk_premium/frozen_config.json"
FUNDING_ML_CARRY_FROZEN_CONFIG_AR_LAGS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/funding_ml_carry/frozen_config_ar_lags.json"
FUNDING_ML_CARRY_FORWARD_TAPE_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/funding_ml_carry/forward_tape.jsonl"
FUNDING_ML_CARRY_FORWARD_TAPE_AR_LAGS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/funding_ml_carry/forward_tape_ar_lags.jsonl"
FUNDING_ML_CARRY_FORWARD_STATUS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/funding_ml_carry/forward_status.json"
FUNDING_ML_CARRY_FORWARD_ENTRY_PREFIX = "funding-ml-carry"
FUNDING_ML_CARRY_AR_LAGS_FORWARD_ENTRY_PREFIX = "funding-ml-carry-ar-lags"
EDGE_HUNT_MODELS_REGISTRY_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_hunt_models/registry.json"
#: apps/api-side "champion validation" artifacts (F3b regime coverage, ML staging shortlist).
F3B_REGIME_MATRIX_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_lab/champion_validation/F3B_REGIME_MATRIX.json"
STAGING_SHORTLIST_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_lab/champion_validation/STAGING_SHORTLIST.json"
#: Forward-status artifacts for the rules-based portfolio books not covered by a dedicated
#: constant above (portfolio_books.py). funding_ml_carry/vt_17_momentum already have theirs.
XS_TREND_FORWARD_STATUS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/xs_trend_portfolio/forward_status.json"
VRP_FORWARD_STATUS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vol_risk_premium/forward_status.json"
#: The shared funding-carry cryptobacktester-style cert artifact every funding leaf is graded
#: from (registry_leaf_capital_cert_rows.py's `_funding_lane_disclosure` / `_apply_funding_verdict`).
FUNDING_TARGET_CARRY_PORTFOLIO_CERT_REL = f"{_RESEARCH_ROOT_APPS_API_REL}/edge_hunt/results/funding_target_carry_portfolio_v2.json"
#: The ONE registry leaf that artifact measured: `funding_ml_carry_portfolio_backtest` builds its
#: ledger from `wf_ridge_scores_1d`, the ridge on the core features. Every other funding leaf holds
#: different weights, so this artifact's money is not theirs (CARRY-COMBO-CERT-1).
FUNDING_TARGET_CARRY_PORTFOLIO_CERT_MODEL_ID = "funding_target_carry__1d__ridge_core"
#: The money-ledger doc money_ledger.main splices its generated tables into.
CERT_INVENTORY_DOC_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_lab/CERT_INVENTORY.md"
#: Money-ledger CLI + HTTP door — one script, never a second parents[N] copy in application/.
GEN_MONEY_LEDGER_REL = f"{_RESEARCH_ROOT_APPS_API_REL}/edge_hunt/gen_money_ledger.py"
L2_BOOK_FORWARD_LOG_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/l2_order_book/binance_book_ticker_forward_log.jsonl"
VRP_SURFACE_FORWARD_LOG_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vol_risk_premium/deribit_surface_forward_log.jsonl"
#: Where hypothesis-level capital certs land — the SECOND cert corpus.
#:
#: A tier can be certified two different ways and only one was ever wired. ModelSpec cells get
#: `apps/api/models/<key>/<type>/vN/capital_certification.json`. Hunt-loop cells fit in-memory
#: per fold and never persist a version dir, so they cannot take that route at all; their certs
#: are written HERE, keyed by the `hypothesis` field inside the artifact
#: (e.g. `dvs_polarity_full_cert_findbest_2017.json` -> `hypothesis: "dvs_polarity"`).
#: Measured 2026-08-09: 54 combinatorial + 11 lane-only certs in this directory, and the
#: registry reported 0 of 20 rows certified because nothing ever looked here.
CAPITAL_CERT_INVENTORY_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_lab/inventory_cryptobacktest"
#: `CAPITAL_CERT_INVENTORY_REL` without the `apps/api/` prefix -- money_ledger.py globs relative
#: to `API_ROOT_PATH` (already the apps/api dir), not the repo root, so its glob patterns need
#: this anchor rather than the repo-relative one every other `*_REL` constant here uses.
CAPITAL_CERT_INVENTORY_APPS_API_REL = CAPITAL_CERT_INVENTORY_REL.removeprefix(_APPS_API_PREFIX)
#: money_ledger.py's PRECOMMIT_GLOB / HYPOTHESIS_CERT_GLOB / LEVERED_RETURN_CERT_GLOB -- the three
#: corpora `compute_money_standings` folds, each a filename pattern under the inventory dir above.
SELECT_CONFIRM_GLOB_REL = f"{CAPITAL_CERT_INVENTORY_APPS_API_REL}/select_confirm_*.json"
#: NOT a path -- the one name in the select-confirm SUBPROCESS CONTRACT, shared by
#: `select_confirm_tasks._run_select_confirm_subprocess` (which sets it) and
#: `run_select_confirm_cert.main` (which reads it). It lives here because this module is already
#: the only vocabulary both sides import; a second spelling is a mirror, and mirrors drift.
#:
#: WHY IT EXISTS, measured 2026-09-15: a `dry_run: true` select-confirm answered
#: `"applied": false` and still rewrote `models/.../v42/metadata.json`, replacing a FROZEN
#: pre-commitment (`perp_8x/tpsl_7_5` -> `perp_4x/breakeven`). `dry_run` was consumed in the task,
#: where it gates `_apply_candidate_ship`, while the write happened one process further down in a
#: subprocess that was handed nothing about it -- so the flag could not reach the write even in
#: principle. Set to "1" the subprocess records its measurement and leaves the shipped artifact
#: alone.
SELECT_CONFIRM_DRY_RUN_ENV = "PULSAI_SELECT_CONFIRM_DRY_RUN"
#: A PREFIX, never a suffix: `SELECT_CONFIRM_GLOB_REL` is `select_confirm_*.json`, so any suffix
#: would still be folded into the money corpus by `compute_money_standings`. Applied by
#: `select_confirm_artifact_name(dry_run=True)`, which both the writer and the reader go through.
SELECT_CONFIRM_DRY_RUN_NAME_PREFIX = "dryrun_"
#: NOT a path -- the fee schedule a cert-engine SUBPROCESS charges (ADR-029 Decision 1). Set by the
#: cert-run and select-confirm doors, read once per cell by the engine (`fee_schedule.cert_fee_schedule`).
#: Unset means `standard`. Lives here for the same reason as SELECT_CONFIRM_DRY_RUN_ENV: it is the one
#: vocabulary both sides of the subprocess contract import.
CERT_FEE_SCHEDULE_ENV = "PULSAI_CERT_FEE_SCHEDULE"
HYPOTHESIS_CAPITAL_X_EXIT_GLOB_REL = f"{CAPITAL_CERT_INVENTORY_APPS_API_REL}/*_hypothesis_capital_x_exit.json"
LEVERED_RETURN_CERT_GLOB_REL = f"{CAPITAL_CERT_INVENTORY_APPS_API_REL}/*_levered_return_cert.json"
ML_SHORTLIST_FORWARD_STATUS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_lab/ml_shortlist_forward/forward_status.json"
LANE_B_FORWARD_STATUS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_lab/lane_b_elasticnet_4h_forward/forward_status.json"
LANE_B_FORWARD_KILL_STATE_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/edge_lab/lane_b_elasticnet_4h_forward/kill_state.json"
VT_17_FORWARD_STATUS_REL = f"{_ARTIFACT_ROOT_APPS_API_REL}/vt_17_momentum/forward_status.json"

FORWARD_TAPE_BY_ENTRY_PREFIX: tuple[tuple[str, str], ...] = (
    (EDGE_BOOK_FORWARD_ENTRY_PREFIX, EDGE_BOOK_FORWARD_TAPE_REL),
    (XS_OI_FORWARD_ENTRY_PREFIX, XS_OI_FORWARD_TAPE_REL),
    (XS_TREND_FORWARD_ENTRY_PREFIX, XS_TREND_FORWARD_TAPE_REL),
    (VT_17_MOMENTUM_FORWARD_ENTRY_PREFIX, VT_17_MOMENTUM_FORWARD_TAPE_REL),
    (VRP_FORWARD_ENTRY_PREFIX, VRP_FORWARD_TAPE_REL),
    (FUNDING_ML_CARRY_FORWARD_ENTRY_PREFIX, FUNDING_ML_CARRY_FORWARD_TAPE_REL),
    (FUNDING_ML_CARRY_AR_LAGS_FORWARD_ENTRY_PREFIX, FUNDING_ML_CARRY_FORWARD_TAPE_AR_LAGS_REL),
)


def repo_root() -> Path:
    return _REPO_ROOT


def hypothesis_queue_path() -> Path:
    return _REPO_ROOT / HYPOTHESIS_QUEUE_REL


def loop_state_path() -> Path:
    return _REPO_ROOT / LOOP_STATE_REL


def last_research_loop_tick_path() -> Path:
    return _REPO_ROOT / LAST_RESEARCH_LOOP_TICK_REL


def forward_tape_jsonl_path_for_entry(entry_id: str) -> Path | None:
    for prefix, rel in FORWARD_TAPE_BY_ENTRY_PREFIX:
        if entry_id.startswith(prefix):
            return resolve_apps_api_rel(rel)
    return None


def forward_tape_jsonl_rel_for_entry(entry_id: str) -> str | None:
    for prefix, rel in FORWARD_TAPE_BY_ENTRY_PREFIX:
        if entry_id.startswith(prefix):
            return rel
    return None


def xs_trend_frozen_config_path() -> Path:
    return resolve_apps_api_rel(XS_TREND_FROZEN_CONFIG_REL)


def vt_17_momentum_frozen_config_path() -> Path:
    return resolve_apps_api_rel(VT_17_MOMENTUM_FROZEN_CONFIG_REL)


def vt_17_momentum_frozen_by_timeframe_path() -> Path:
    return resolve_apps_api_rel(VT_17_MOMENTUM_FROZEN_BY_TIMEFRAME_REL)


def funding_ml_carry_frozen_config_path() -> Path:
    return resolve_apps_api_rel(FUNDING_ML_CARRY_FROZEN_CONFIG_REL)


def funding_ml_carry_frozen_config_ar_lags_path() -> Path:
    return resolve_apps_api_rel(FUNDING_ML_CARRY_FROZEN_CONFIG_AR_LAGS_REL)


def funding_ml_carry_forward_status_path() -> Path:
    return resolve_apps_api_rel(FUNDING_ML_CARRY_FORWARD_STATUS_REL)


def edge_hunt_models_registry_path() -> Path:
    return resolve_apps_api_rel(EDGE_HUNT_MODELS_REGISTRY_REL)


def gen_money_ledger_path() -> Path:
    """Absolute path to ``gen_money_ledger.py`` (CLI fold + HTTP money standings)."""
    return resolve_apps_api_rel(GEN_MONEY_LEDGER_REL)


def gen_money_ledger_repo_rel() -> str:
    """``GEN_MONEY_LEDGER_REL`` without the ``apps/api/`` prefix.

    The spelling used in apps/api-relative generated-doc prose (money_ledger.py's tier-counter
    comment, money_ledger_table.py's money-table comment) -- both name the script for a human
    reader, never resolve it, so they need the apps/api-rooted form rather than the repo-rooted
    constant every ``*_path()`` function here resolves against.
    """
    return GEN_MONEY_LEDGER_REL.removeprefix(_APPS_API_PREFIX)


def cert_inventory_doc_path() -> Path:
    """Absolute path to the generated CERT_INVENTORY.md (money_ledger.main splices into this)."""
    return resolve_apps_api_rel(CERT_INVENTORY_DOC_REL)


def l2_book_forward_log_path() -> Path:
    """Append-only Binance bookTicker forward log."""
    return resolve_apps_api_rel(L2_BOOK_FORWARD_LOG_REL)


def vrp_surface_forward_log_path() -> Path:
    """Append-only Deribit vol-surface forward log."""
    return resolve_apps_api_rel(VRP_SURFACE_FORWARD_LOG_REL)


def capital_cert_inventory_root() -> Path:
    """Directory holding hypothesis-level capital certs (apps/api locally, /app in Docker)."""
    return resolve_apps_api_rel(CAPITAL_CERT_INVENTORY_REL)


#: HOW THE CERT ENGINE IS LAUNCHED, in one place. The engine became a package on 2026-09-17 and
#: `run_edge_capital_x_exit_grid.py` is now a pure re-export FACADE with no `__main__` -- running
#: it as a script prints nothing and exits 0. `cert_run_tasks` was updated to `-m`; the
#: select->confirm harness was not, so its subprocess "succeeded" silently and the door reported
#: "grid produced no artifact path" (measured 2026-09-17 on task c393060f: 0 bytes of output,
#: rc=0). Two launchers that must agree is exactly the drift this module exists to stop, so the
#: module name lives here and both import it.
CERT_ENGINE_MODULE = "src.cert"


def fee_sensitivity_artifact_name(standard_name: str, fee_schedule: FeeSchedule) -> str:
    """The name the SAME select->confirm run takes under a non-standard ``fee_schedule`` -- the 0%-fee result shown BESIDE
    the standard tier (owner, 2026-10-09). A sensitivity is always a dry run (the door forces it), so this is
    ``select_confirm_artifact_name(..., dry_run=True, fee_schedule=...)`` for the same window, derived from the standard
    name the money ledger already holds; a test pins the two agreeing.
    """
    return f"{SELECT_CONFIRM_DRY_RUN_NAME_PREFIX}fee_{fee_schedule.value}_{standard_name}"


def select_confirm_artifact_name(
    *,
    slug: str,
    split: str,
    end: str | None = None,
    lane: str | None = None,
    dry_run: bool = False,
    fee_schedule: FeeSchedule = FeeSchedule.STANDARD,
) -> str:
    """Name a select->confirm artifact by the window it CONFIRMED, not just where it split.

    MEASURED 2026-09-05 by losing a result to it. Two pre-commitments on the same model with the
    same ``split`` but different confirm ENDS both wrote
    ``select_confirm_btcusdt_1d_33_lightgbm_2025-06-01.json``: the open-ended one ($18,700, 164
    trades, measurable) and a bounded sub-window ($11,574, 27 trades, ``thin_sample: True``). The
    second replaced the first, so the corpus kept the WORSE and unmeasurable of the two under a
    name that claims to be both.

    Same root cause as the cert-artifact collision fixed in ``95c6630f5``; this is the second
    writer that fix did not reach.

    This function exists because the name is a MIRROR: ``run_select_confirm_cert._record`` writes
    it and ``select_confirm_tasks._artifact_path`` reads it back to answer the endpoint. Two
    f-strings that must agree character-for-character is a drift waiting to happen, and when they
    drift the API reports ``artifact_found: false`` for a run that actually succeeded.

    An OPEN-ENDED confirm keeps the legacy ``_{split}.json`` name -- every artifact on disk was
    written that way, and the reader must keep finding them. Only an explicitly bounded window
    takes ``_to{end}``, which is precisely the case that collides.

    ``dry_run`` moves the file out of the COMMITTED corpus entirely, and the prefix is deliberate
    rather than a suffix. MEASURED 2026-09-15: a dry-run replay of `1d:42:lightgbm` overwrote the
    frozen `perp_8x/tpsl_7_5` pre-commitment recorded on 2026-08-12 with a fresh `perp_4x` one,
    because a re-run re-selects on a window that has since GROWN. The envelope must still be
    written -- ``run_select_confirm_sync`` reads it back to compute ``precommit_tier``, so a dry run
    that wrote nothing could not answer what it was asked -- but it must not be written HERE.

    A PREFIX, because ``SELECT_CONFIRM_GLOB_REL`` is ``select_confirm_*.json``: any suffix would
    still match, and ``compute_money_standings`` would fold a dry run into the money corpus as
    though it were a pre-commitment. ``dryrun_select_confirm_...`` cannot match that glob.
    """
    suffix = f"_to{end}" if end else ""
    # A PINNED lane is a different measurement, for exactly the reason `end` is: v42 holds a
    # `perp_4x` pre-commitment written by the unpinned door, and a `perp_3x` run sharing this
    # path would overwrite the record a retraction rests on. It stays a SUFFIX, not a prefix,
    # because a lane-pinned run IS a pre-commitment and must keep matching the money glob.
    lane_suffix = f"_lane{lane}" if lane else ""
    prefix = SELECT_CONFIRM_DRY_RUN_NAME_PREFIX if dry_run else ""
    # A NON-STANDARD fee schedule is a sensitivity, never a pre-commitment money-standings may grade
    # (ADR-029 Decision 1), so it takes a PREFIX for the dry-run's reason: a suffix would still match
    # `select_confirm_*.json`. `standard` keeps every existing name.
    if fee_schedule is not FeeSchedule.STANDARD:
        prefix = f"{prefix}fee_{fee_schedule.value}_"
    return f"{prefix}select_confirm_{slug}_{split}{suffix}{lane_suffix}.json"


def ml_shortlist_forward_status_path() -> Path:
    return resolve_apps_api_rel(ML_SHORTLIST_FORWARD_STATUS_REL)


def lane_b_forward_status_path() -> Path:
    return resolve_apps_api_rel(LANE_B_FORWARD_STATUS_REL)


def lane_b_forward_kill_state_path() -> Path:
    return resolve_apps_api_rel(LANE_B_FORWARD_KILL_STATE_REL)


def vt_17_forward_status_path() -> Path:
    return resolve_apps_api_rel(VT_17_FORWARD_STATUS_REL)


def vrp_frozen_config_path() -> Path:
    return resolve_apps_api_rel(VRP_FROZEN_CONFIG_REL)


__all__ = [
    "ARTIFACT_ROOT_REL",
    "CAPITAL_CERT_INVENTORY_APPS_API_REL",
    "CAPITAL_CERT_INVENTORY_REL",
    "CERT_INVENTORY_DOC_REL",
    "EDGE_BOOK_FORWARD_ENTRY_PREFIX",
    "EDGE_BOOK_FORWARD_TAPE_REL",
    "EDGE_HUNT_MODELS_REGISTRY_REL",
    "F3B_REGIME_MATRIX_REL",
    "FUNDING_ML_CARRY_AR_LAGS_FORWARD_ENTRY_PREFIX",
    "FUNDING_ML_CARRY_FORWARD_ENTRY_PREFIX",
    "FUNDING_ML_CARRY_FORWARD_STATUS_REL",
    "FUNDING_ML_CARRY_FORWARD_TAPE_AR_LAGS_REL",
    "FUNDING_ML_CARRY_FORWARD_TAPE_REL",
    "FUNDING_ML_CARRY_FROZEN_CONFIG_AR_LAGS_REL",
    "FUNDING_ML_CARRY_FROZEN_CONFIG_REL",
    "FUNDING_TARGET_CARRY_PORTFOLIO_CERT_REL",
    "GEN_MONEY_LEDGER_REL",
    "HYPOTHESIS_CAPITAL_X_EXIT_GLOB_REL",
    "HYPOTHESIS_QUEUE_REL",
    "L2_BOOK_FORWARD_LOG_REL",
    "LANE_B_FORWARD_KILL_STATE_REL",
    "LANE_B_FORWARD_STATUS_REL",
    "LEVERED_RETURN_CERT_GLOB_REL",
    "LOOP_STATE_REL",
    "ML_SHORTLIST_FORWARD_STATUS_REL",
    "RESEARCH_ROOT_REL",
    "RESEARCH_SCRIPTS_DIR_PREFIX",
    "SELECT_CONFIRM_GLOB_REL",
    "STAGING_SHORTLIST_REL",
    "VRP_FORWARD_ENTRY_PREFIX",
    "VRP_FORWARD_STATUS_REL",
    "VRP_FORWARD_TAPE_REL",
    "VRP_FROZEN_CONFIG_REL",
    "VRP_SURFACE_FORWARD_LOG_REL",
    "VT_17_FORWARD_STATUS_REL",
    "VT_17_MOMENTUM_FORWARD_ENTRY_PREFIX",
    "VT_17_MOMENTUM_FORWARD_TAPE_REL",
    "VT_17_MOMENTUM_FROZEN_BY_TIMEFRAME_REL",
    "VT_17_MOMENTUM_FROZEN_CONFIG_REL",
    "XS_OI_FORWARD_ENTRY_PREFIX",
    "XS_OI_FORWARD_TAPE_REL",
    "XS_TREND_FORWARD_ENTRY_PREFIX",
    "XS_TREND_FORWARD_STATUS_REL",
    "XS_TREND_FORWARD_TAPE_REL",
    "XS_TREND_FROZEN_CONFIG_REL",
    "api_package_root",
    "capital_cert_inventory_root",
    "cert_inventory_doc_path",
    "edge_hunt_models_registry_path",
    "fee_sensitivity_artifact_name",
    "forward_tape_jsonl_path_for_entry",
    "forward_tape_jsonl_rel_for_entry",
    "funding_ml_carry_forward_status_path",
    "funding_ml_carry_frozen_config_ar_lags_path",
    "funding_ml_carry_frozen_config_path",
    "gen_money_ledger_path",
    "gen_money_ledger_repo_rel",
    "hypothesis_queue_path",
    "l2_book_forward_log_path",
    "lane_b_forward_kill_state_path",
    "lane_b_forward_status_path",
    "last_research_loop_tick_path",
    "loop_state_path",
    "ml_shortlist_forward_status_path",
    "repo_root",
    "resolve_apps_api_rel",
    "vrp_frozen_config_path",
    "vrp_surface_forward_log_path",
    "vt_17_forward_status_path",
    "vt_17_momentum_frozen_by_timeframe_path",
    "vt_17_momentum_frozen_config_path",
    "xs_trend_frozen_config_path",
]
