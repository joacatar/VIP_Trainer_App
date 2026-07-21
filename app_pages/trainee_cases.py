"""Trainee cases at /trainee."""

from ct_training_tracker.runtime import require_runtime
from ct_training_tracker.views.trainee import render_trainee_portal


def main() -> None:
    runtime = require_runtime()
    if runtime is None:
        return
    if runtime.profile["role"] != "trainee":
        return
    render_trainee_portal(runtime.repository, runtime.profile)


main()
