"""
Newsletter / waitlist constants.

Single source of truth for lead cap and allowed attribution sources.
@see .cursor/plans/landing_full_page_merged.plan.md (Newsletter & VIP launch)
"""

# First N subscribers get is_lead=True (VIP launch seat); after that is_lead=False.
LEAD_CAP = 1000

# Allowed values for newsletter_subscribers.source (attribution).
# Validate in repository/endpoint; extend when new campaigns are added.
ALLOWED_SOURCES = frozenset({"landing", "google", "x", "direct", "blog"})
