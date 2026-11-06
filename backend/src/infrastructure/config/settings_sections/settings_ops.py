"""Settings mixin — composite ops sections (15-26)."""

from .settings_ops_features import SettingsOpsFeaturesMixin
from .settings_ops_platform import SettingsOpsPlatformMixin
from .settings_ops_rate_limits import SettingsOpsRateLimitsMixin
from .settings_ops_vendors import SettingsOpsVendorsMixin
from .settings_ops_workers import SettingsOpsWorkersMixin


class SettingsOpsMixin(
    SettingsOpsFeaturesMixin,
    SettingsOpsRateLimitsMixin,
    SettingsOpsPlatformMixin,
    SettingsOpsWorkersMixin,
    SettingsOpsVendorsMixin,
):
    """Feature flags, limits, workers, vendors."""
