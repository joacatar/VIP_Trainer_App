"""Trainer dashboard at /trainer."""

from ct_training_tracker.runtime import require_runtime
from ct_training_tracker.views.trainer import render_dashboard


def main() -> None:
    runtime = require_runtime()
    if runtime is None:
        return
    if runtime.profile["role"] != "trainer":
        return
    render_dashboard(runtime.repository)


main()
