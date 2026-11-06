"""Training-job lifecycle signals (re-exported by ``src.shared.exceptions``)."""


# ---------------------------------------------------------------------------
# Training-job lifecycle signals (control flow, not domain errors)
# ---------------------------------------------------------------------------
class TrainingPausedError(Exception):
    """Raised when a training job is paused by admin.

    Progress is preserved — the job can be resumed later (Optuna study state is
    saved to disk). Plain ``Exception`` (not ``PulsAIException``): a control-flow
    signal a progress callback raises to stop a long-running study, not an API error.
    """


class TrainingCancelledError(Exception):
    """Raised when a training job is cancelled by admin.

    Training is permanently stopped; partial results may be discarded. Plain
    ``Exception`` for the same reason as :class:`TrainingPausedError`.
    """
