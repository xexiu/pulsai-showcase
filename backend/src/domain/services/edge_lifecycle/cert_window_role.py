"""WHICH WINDOW a cert's numbers came from — the select/confirm vocabulary, in one place.

IMPORTERS/CALLERS: `capital_cert_promote` (which re-exports every name here, so no existing
import path changes), `research/cert/certification.py`, and the publish gate.
AFFECTED API: none. The constants keep their exact names and values and stay importable from
`capital_cert_promote`; only the module they are DEFINED in moves.
DATA SCHEMAS: names the `window_role` key inside a `capital_certification.json` artifact, whose
value is one of `select` / `confirm`. No persisted or wire shape changes.

WHY IT IS ITS OWN MODULE. `capital_cert_promote` answers "does this cert PASS the promote gate".
That is a decision. Which window a number came from is a different thing entirely — it is
VOCABULARY that several modules share, and the reason it needs its own home is in the incident
below: the distinction is the whole defence against citing a search as a result.

It also moved for a measured reason. The file-size ratchet caught `capital_cert_promote.py`
growing 710 -> 715 effective lines (CODING_STANDARDS section 7), and `git log` attributes that
growth to the commit which introduced this block. The gate's own remedy is "split the file, or
move the growth elsewhere"; this is the growth, and this is elsewhere.
"""

from __future__ import annotations

from typing import Final

#: WHICH WINDOW a cert's numbers come from -- the question `window_is_in_sample` does not
#: answer. A cert can be perfectly out-of-fit and still be a SELECT window: the grid ranks
#: thousands of lever tuples over one span and publishes the winner from that same span, so
#: the headline is the search, not the result. The CONFIRM window is the separate one the
#: levers were pre-committed to before it was scored.
#:
#: Both artifacts existed for one book, and on 2026-09-03 I read the SELECT one
#: (`capital_certification.json`, liquidation-free perp_3x..perp_8x, best cell $24,579) and
#: used it to accuse the money ledger of falsely excluding the book. The CONFIRM artifact for
#: the same book records $10,000 -> $0.00 at -100% drawdown over 60 trades. Neither file said
#: which question it answered, so the mistake was available to any reader.
#:
#: `.claude/hooks/verdict_window_role_guard.py` already enforces this distinction in PROSE at
#: Stop time. It cannot see an artifact, which is why the same vocabulary lives on the file
#: itself -- an absorbed wrong value has no rhetorical tell for a prose guard to catch.
CERT_WINDOW_ROLE_KEY: Final = "window_role"
CERT_WINDOW_ROLE_SELECT: Final = "select"
CERT_WINDOW_ROLE_CONFIRM: Final = "confirm"

#: The only roles a window may declare. Declared HERE, beside the two members, because a second
#: module rebuilding `frozenset({SELECT, CONFIRM})` is the mirror `a-mirror-needs-a-mechanism`
#: warns about: it stays correct only until a third role exists. `research/cert/certification.py`
#: and the publish gate both read this one.
CERT_WINDOW_ROLES: Final[frozenset[str]] = frozenset({CERT_WINDOW_ROLE_SELECT, CERT_WINDOW_ROLE_CONFIRM})

__all__ = [
    "CERT_WINDOW_ROLES",
    "CERT_WINDOW_ROLE_CONFIRM",
    "CERT_WINDOW_ROLE_KEY",
    "CERT_WINDOW_ROLE_SELECT",
]
