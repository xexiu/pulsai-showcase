"""Control-flow idioms: every loop that sleeps is a poll, a retry, a pace or a schedule, and each idiom has one home.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: builds throwaway registries under tmp_path; the canary
tests read the real control_flow_idioms_canary.txt and the real scripts/concept_owners.json.

GATE-IDIOMS (owner, 2026-11-06: "not only for this use case, but also for other features uses cases? deep think of
everythings, edge cases"). Each shape below is one the repo holds: the three candle looks, lighter_orders.retried_read,
glassnode's 429 loop, the venue pacer, oil's hourly refresh, engine_watch.watch.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.lib.quality_gates import concept_definitions as cd
from src.lib.quality_gates.control_flow_idioms import (
    CANARY_FUNCTIONS,
    PACE,
    PAGE,
    POLL,
    RETRY,
    SCHEDULE,
    UNCLASSIFIED,
    canary_holds,
    idiom_tags,
    sleep_sites,
)

_API = Path(__file__).resolve().parents[2]
_SRC = "apps/api/src"


def _sites(source: str) -> list[tuple[str, str]]:
    return [(site.idiom, site.function) for site in sleep_sites(ast.parse(source), source.splitlines())]


_RETRY_IN_EXCEPT = """
async def retried_read(read, sleep=asyncio.sleep):
    limits = iter(WAITS)
    while True:
        try:
            return await read()
        except Exception as exc:
            wait = next(limits, None)
            if wait is None:
                raise
            await sleep(wait)
"""

_RETRY_ON_STATUS = """
async def get_with_429_retry(url):
    for attempt in range(MAX_TRIES):
        response = await client.get(url)
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS and attempt + 1 < MAX_TRIES:
            await asyncio.sleep(BACKOFF_S)
            continue
        break
    return response
"""

_PACER = """
class Pacer:
    async def wait(self):
        now = self._monotonic()
        slot = await self._slot_store.reserve(cost=1, now=now)
        delay = slot - now
        if delay > 0:
            await self._sleep(delay)
"""

_SCHEDULE_TO_DUE_TIME = """
class Oil:
    def _refresh_loop(self):
        while True:
            now = self._now()
            due = now.replace(minute=0) + step
            self._sleep((due - now).total_seconds())
            try:
                self.current()
            except Exception:
                LOG.exception("the hourly refresh failed")
"""

_POLL_WHILE_TRUE = """
def watch(spec, seconds, sleep=time.sleep, clock=time.monotonic):
    started = clock()
    while True:
        lines = wake(spec)
        if lines:
            return lines
        if clock() - started > seconds:
            return ["QUIET"]
        sleep(POLL_S)
"""


class TestEachIdiomIsReadFromHowTheLoopExits:
    def test_the_three_pre_fix_candle_looks_are_polls(self) -> None:
        """The case that produced GATE-IDIOMS: three hand-written polls no text, value, body or name gate saw."""
        text = (_API / "src/lib/quality_gates/control_flow_idioms_canary.txt").read_text(encoding="utf-8")

        assert _sites(text) == [(POLL, name) for name in CANARY_FUNCTIONS]

    def test_a_sleep_in_an_except_is_a_retry(self) -> None:
        assert _sites(_RETRY_IN_EXCEPT) == [(RETRY, "retried_read")]

    def test_a_sleep_on_a_failure_status_then_continue_is_a_retry(self) -> None:
        assert _sites(_RETRY_ON_STATUS) == [(RETRY, "get_with_429_retry")]

    def test_a_sleep_computed_from_a_clock_outside_a_loop_is_a_pace(self) -> None:
        assert _sites(_PACER) == [(PACE, "Pacer.wait")]

    def test_a_while_true_sleeping_to_a_due_time_is_a_schedule(self) -> None:
        assert _sites(_SCHEDULE_TO_DUE_TIME) == [(SCHEDULE, "Oil._refresh_loop")]

    def test_a_while_true_that_returns_on_an_answer_is_a_poll(self) -> None:
        assert _sites(_POLL_WHILE_TRUE) == [(POLL, "watch")]

    def test_a_while_test_on_the_read_answer_is_a_poll(self) -> None:
        """poll_until_answer's own shape: the exit is the loop's test, not an `if`."""
        source = "def poll(read, sleep):\n    found = read()\n    while found is None and now() < deadline:\n        sleep(step)\n        found = read()\n    return found\n"

        assert _sites(source) == [(POLL, "poll")]

    def test_a_stop_flag_exit_is_a_schedule_not_a_poll(self) -> None:
        source = "def run(self):\n    while True:\n        self.work()\n        if self._stop.is_set():\n            break\n        time.sleep(INTERVAL_S)\n"

        assert _sites(source) == [(SCHEDULE, "run")]

    def test_an_event_wait_in_the_loop_test_is_a_schedule(self) -> None:
        """Event.wait(timeout) sleeps without the word: `while not stop.wait(5)` is the classic periodic loop."""
        source = "def run(self):\n    while not self._stop.wait(INTERVAL_S):\n        self.work()\n"

        assert _sites(source) == [(SCHEDULE, "run")]

    def test_a_pace_inside_a_loop_over_work_is_a_pace(self) -> None:
        source = (
            "def fetch_all(pages):\n    last = time.monotonic()\n    for page in pages:\n"
            "        wait = GAP_S - (time.monotonic() - last)\n        if wait > 0:\n            time.sleep(wait)\n"
            "        get(page)\n        last = time.monotonic()\n"
        )

        assert _sites(source) == [(PACE, "fetch_all")]

    def test_a_loop_that_runs_while_pages_come_is_paging_not_a_poll(self) -> None:
        """marketing_newsletter_tasks' shape: it continues WHILE there is data; a poll waits UNTIL an answer arrives."""
        source = (
            "def send_all():\n    rows = page(None)\n    while rows:\n        send(rows)\n        time.sleep(PAUSE_S)\n"
            "        rows = page(rows[-1])\n"
        )

        assert _sites(source) == [(PAGE, "send_all")]

    def test_a_loop_that_ends_on_an_empty_page_is_paging(self) -> None:
        source = (
            "def fetch_all(start):\n    out = []\n    for _ in range(MAX_PAGES):\n        rows = get(start)\n"
            "        if not rows:\n            break\n        out += rows\n        start = rows[-1]\n        time.sleep(0.2)\n    return out\n"
        )

        assert _sites(source) == [(PAGE, "fetch_all")]

    def test_a_cursor_passed_inside_a_built_request_is_still_paging(self) -> None:
        """vrp_screen.fetch_dvol_daily's shape: the window start goes into a params dict before the read."""
        source = (
            "def fetch_all(start, end):\n    s = start\n    while s < end:\n        e = min(s + STEP, end)\n"
            "        params = {'start': s, 'end': e}\n        rows = read(params)\n        keep(rows)\n        s = e\n        time.sleep(0.25)\n"
        )

        assert _sites(source) == [(PAGE, "fetch_all")]

    def test_a_wait_for_something_to_go_is_a_poll_not_paging(self) -> None:
        """trade_engines.retire's shape: it ends on an ABSENT test, but it reads nothing it keeps -- a wait, not a pager."""
        source = "def retire(pid):\n    for _ in range(TRIES):\n        if not alive(pid):\n            return True\n        time.sleep(0.5)\n    return False\n"

        assert _sites(source) == [(POLL, "retire")]

    def test_a_poll_that_counts_its_wait_is_still_a_poll(self) -> None:
        """DemoAccount.filled's shape: ``waited += POLL_S`` is a timer, not kept data."""
        source = (
            "def filled(oid):\n    waited = 0.0\n    while True:\n        order = read(oid)\n        if order.state == FILLED:\n"
            "            return order\n        sleep(POLL_S)\n        waited += POLL_S\n"
        )

        assert _sites(source) == [(POLL, "filled")]

    def test_an_exit_unless_rate_limited_is_a_retry(self) -> None:
        """llm_agent_a1m.ask's shape: it breaks when the status is not 429 and backs off when it is."""
        source = (
            "def ask(prompt):\n    for _ in range(RETRIES):\n        response = post(prompt)\n"
            "        if response.status_code != HTTPStatus.TOO_MANY_REQUESTS:\n            break\n        time.sleep(WAIT_S)\n"
        )

        assert _sites(source) == [(RETRY, "ask")]

    def test_a_fixed_delay_between_items_is_unclassified(self) -> None:
        source = "def send_all(items):\n    for item in items:\n        send(item)\n        time.sleep(0.2)\n"

        assert _sites(source) == [(UNCLASSIFIED, "send_all")]


class TestTheSleepSpellings:
    @pytest.mark.parametrize(
        "call",
        ["time.sleep(1)", "await asyncio.sleep(1)", "self._sleep(1)", "clocks.sleep(1)", "sleep(1)", "self._stop.wait(1)",
         "cond.wait(timeout=1)", "cond.wait_for(ready, 1)"],
    )  # fmt: skip
    def test_each_sleeps(self, call: str) -> None:
        source = f"async def f():\n    while True:\n        x = read()\n        if x:\n            return x\n        {call}\n"

        assert _sites(source) == [(POLL, "f")]

    @pytest.mark.parametrize("call", ["await asyncio.wait_for(task, 5)", "await asyncio.wait(tasks, timeout=5)", "self._sleep_s()",
                                      "ev.wait()", "time.time()", "is_sleep(node)"])  # fmt: skip
    def test_none_of_these_sleeps(self, call: str) -> None:
        source = f"async def f():\n    while True:\n        x = read()\n        if x:\n            return x\n        {call}\n"

        assert _sites(source) == []


class TestTheEdgeCases:
    def test_two_polls_in_one_function_are_two_tags(self) -> None:
        loop = "    for _ in range(3):\n        if read():\n            return 1\n        time.sleep(1)\n"
        source = "def f():\n" + loop + loop + "    return 0\n"

        assert idiom_tags(sleep_sites(ast.parse(source), source.splitlines())) == frozenset({"poll-loop@f", "poll-loop@f#2"})

    def test_a_nested_function_is_named_inside_its_outer_one(self) -> None:
        source = "def outer():\n    def inner():\n        while True:\n            if read():\n                return 1\n            time.sleep(1)\n    return inner\n"

        assert _sites(source) == [(POLL, "outer.inner")]

    def test_a_sleep_in_a_nested_function_does_not_make_the_outer_loop_sleep(self) -> None:
        source = "def f(items):\n    for item in items:\n        def later():\n            time.sleep(1)\n        schedule(later)\n"

        assert _sites(source) == []

    def test_only_the_innermost_loop_holding_the_sleep_is_a_site(self) -> None:
        source = (
            "def f():\n    while True:\n        for attempt in range(3):\n            try:\n                return get()\n"
            "            except OSError:\n                time.sleep(1)\n"
        )

        assert _sites(source) == [(RETRY, "f")]

    def test_clone_ok_on_the_loop_line_exempts_it(self) -> None:
        source = "def f():\n    while True:  # CLONE-OK: a judged exception\n        if read():\n            return 1\n        time.sleep(1)\n"

        assert _sites(source) == []

    def test_a_renamed_copy_is_still_found(self) -> None:
        """The key is the SHAPE: renaming every name escapes nothing."""
        source = "def zz(q, nap):\n    while True:\n        k = q()\n        if k:\n            return k\n        nap(1)\n"

        assert _sites(source.replace("nap(1)", "nap_sleep(1)")) == [(POLL, "zz")]

    def test_unclassified_is_never_a_tag(self) -> None:
        source = "def send_all(items):\n    for item in items:\n        time.sleep(0.2)\n"

        assert idiom_tags(sleep_sites(ast.parse(source), source.splitlines())) == frozenset()


_POLL_HOME = f"{_SRC}/shared/utils/polling.py"


class TestTheDoorsSeeEachLoop:
    """The idioms feed concept_definitions, so the three doors already wired to it -- one_definition_guard (PreToolUse),
    check_touched_debt's duplicate-definition row and verify's --tree ratchet -- refuse, charge and count each loop."""

    def _registry(self, tmp_path: Path) -> tuple[cd.Concept, ...]:
        path = tmp_path / "owners.json"
        path.write_text(json.dumps({"concepts": [{"concept": "poll until answer", "owner": _POLL_HOME, "structures": [POLL]}]}))
        return cd.load_registry(path)

    def test_each_poll_outside_its_home_is_one_finding_naming_the_home(self, tmp_path: Path) -> None:
        gate = f"{_SRC}/research/engine/strategies/oil_gate_feed.py"
        text = (_API / "src/lib/quality_gates/control_flow_idioms_canary.txt").read_text(encoding="utf-8")
        index = cd.index_from_sources({gate: text})

        found = cd.findings_for(gate, index[gate], index, self._registry(tmp_path))

        assert len(found) == len(CANARY_FUNCTIONS)
        assert all(_POLL_HOME in line for line in found)
        assert any("poll-loop@OilPart._served" in line for line in found)

    def test_the_home_itself_is_clean(self, tmp_path: Path) -> None:
        index = cd.index_from_sources({_POLL_HOME: (_API / "src/shared/utils/polling.py").read_text(encoding="utf-8")})

        assert cd.findings_for(_POLL_HOME, index[_POLL_HOME], index, self._registry(tmp_path)) == []

    def test_a_reconnect_loop_is_not_also_a_retry(self) -> None:
        source = (
            "async def run(self):\n    while True:\n        try:\n            async with connect(URL) as ws:\n"
            "                await self.read(ws)\n        except OSError:\n            pass\n        await asyncio.sleep(delay)\n"
        )

        assert cd.definitions_in(source).structures == frozenset({cd.RECONNECT_LOOP})


class TestTheCanary:
    def test_it_holds_on_the_kept_fixture(self) -> None:
        assert canary_holds()

    def test_it_fails_when_the_detector_would_measure_nothing(self) -> None:
        assert not canary_holds("class OilPart:\n    def _served(self, hour):\n        return True\n")

    def test_the_tree_ratchet_exits_2_when_the_canary_fails(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr(cd, "canary_holds", lambda: False)

        assert cd.ratchet_tree(_API.parents[1]) == 2
        assert "measured nothing" in capsys.readouterr().out

    def test_every_idiom_row_names_a_home_that_exists_and_carries_its_shape(self) -> None:
        """A row whose home does not hold its own idiom would refuse every copy while pointing at nothing to import."""
        repo = _API.parents[1]
        rows = [c for c in cd.load_registry() if c.structures & {POLL, RETRY, PACE, SCHEDULE}]

        assert {s for c in rows for s in c.structures} == {POLL, RETRY, PACE, SCHEDULE}
        for concept in rows:
            home = cd.definitions_in((repo / concept.home).read_text(encoding="utf-8")).structures
            assert {tag.split("@")[0] for tag in home} >= concept.structures, concept.home
