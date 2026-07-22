"""Trainer full-width case workspace at /trainer-case."""

from ct_training_tracker.runtime import require_runtime
from ct_training_tracker.views.trainer import render_trainer_case_workspace


def main() -> None:
    runtime = require_runtime()
    if runtime is None or runtime.profile["role"] != "trainer":
        return
    render_trainer_case_workspace(runtime.repository, runtime.profile["id"])


main()

