"""Trainee full-width case workspace at /trainee-case."""

from ct_training_tracker.runtime import require_runtime
from ct_training_tracker.views.trainee import render_trainee_case_workspace


def main() -> None:
    runtime = require_runtime()
    if runtime is None or runtime.profile["role"] != "trainee":
        return
    render_trainee_case_workspace(runtime.repository, runtime.profile)


main()

