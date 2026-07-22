"""Add trainee at /trainer-trainees."""

from ct_training_tracker.runtime import require_runtime
from ct_training_tracker.views.trainer import render_trainees


def main() -> None:
    runtime = require_runtime()
    if runtime is None:
        return
    if runtime.profile["role"] != "trainer":
        return
    render_trainees(runtime.repository, runtime.profile["id"])


main()
