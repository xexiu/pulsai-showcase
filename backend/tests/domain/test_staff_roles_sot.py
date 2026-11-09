"""THIS FILE IS THE PARITY TEST for ``STAFF_ROLES`` — it is the mechanism, not a promise.

The domain layer may not import ``infrastructure.persistence.user_model``, so the role values
are necessarily spelled in two places. Rather than a comment asking future editors to reconcile
them, this reads BOTH definitions and fails when they disagree.

It exists because the concept had already split three ways in the backend before anyone noticed:
``UserRole.is_admin()``, a private ``_STAFF_ROLES`` in the email policy, and a bare
``("admin", "super_admin")`` tuple inside the live-trading gate. Adding a fourth role would have
reached some of them and silently missed the others — including the one that decides whether a
Celery tick places real orders on mainnet.

Guarding the guard: every assertion below would pass trivially against an empty set, so the
non-emptiness of both sides is asserted first. A parity test that compares nothing to nothing is
a test that does not exist.
"""

from __future__ import annotations

from src.domain.enums import STAFF_ROLES
from src.infrastructure.persistence.user_model import UserRole


def _admin_role_values() -> set[str]:
    return {role.value for role in UserRole if role.is_admin()}


def test_both_definitions_are_non_empty_before_anything_is_compared() -> None:
    """Without this, an emptied enum or constant would make every check below vacuous."""
    assert STAFF_ROLES, "the domain constant is empty — every staff policy now denies everyone"
    assert _admin_role_values(), "UserRole.is_admin() matches nothing — the enum lost its admins"


def test_staff_roles_matches_the_role_enums_own_admin_predicate() -> None:
    """The domain set must be exactly the roles the infrastructure enum calls admin."""
    assert _admin_role_values() == STAFF_ROLES


def test_every_staff_role_is_a_real_role_value() -> None:
    """Guards the direction the equality cannot state on its own: a string matching no role.

    If ``STAFF_ROLES`` gained "super-admin" (hyphen), the equality above fails only because the
    sets differ. This names the actual consequence: no user can ever hold that role, so the
    policy silently denies everyone it was written to allow.
    """
    known = {role.value for role in UserRole}

    assert STAFF_ROLES.issubset(known), f"not real roles: {STAFF_ROLES - known}"


def test_the_ordinary_user_role_is_not_staff() -> None:
    """Pins the negative case, so a set that accidentally widened to every role fails here."""
    assert UserRole.USER.value not in STAFF_ROLES
