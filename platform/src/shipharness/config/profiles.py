"""Run profiles: named sets of setting overrides, applied identically to both arms.

`standard` keeps the settings as loaded (the default for every command). `class` is for live class
runs only (`make demo-N`, `make final`, `make show-N`): reasoning effort low for the agent arms,
2 CPUs for every arm, referee, and preview container, the OpenAI Fast tier for the agent arms'
model calls, a 420 s agent time limit (RUN_TIMEOUT_S) for both arms, so a run fits the class
window (`standard` keeps 300 s), and 900 s of harness work (HARNESS_TIMEOUT_S) for both arms
(`standard` keeps 120 s): at 120 s the harness's own work (handoff test runs, gates, test filters)
ended harness arms during session-end work (show-2 and demo-3, 2026-10-18; the final,
2026-10-17), and show-4's test filters took 572 s of harness work (2026-10-18). The reviewer
keeps OPENAI_EVAL_REASONING_EFFORT and never requests a tier. Each arm's spec records the values
it ran with (ab.json, arms.<arm>.spec).
"""

from __future__ import annotations

from typing import Any

from shipharness.config.settings import Settings

PROFILES: dict[str, dict[str, Any]] = {
    "standard": {},
    "class": {
        "openai_reasoning_effort": "low",
        "openai_service_tier": "fast",
        "sandbox_cpus": 2.0,
        "run_timeout_s": 420,
        "harness_timeout_s": 900,
    },
}
PROFILE_HELP = (
    "standard (settings as loaded) or class (live class runs: low effort, Fast, 2 CPUs, 420 s agent"
    " time, 900 s harness time)."
)


def apply_profile(settings: Settings, profile: str) -> Settings:
    """Settings with the profile's overrides; both arms read the same values."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}: {', '.join(PROFILES)}")
    overrides = PROFILES[profile]
    return settings.model_copy(update=overrides) if overrides else settings
