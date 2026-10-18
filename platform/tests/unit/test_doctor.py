from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from shipharness.config import Settings
from shipharness.doctor import DoctorReport, run_doctor

from .fakes import fake_langsmith_key, fake_openai_key


class FakeAuthError(Exception):
    status_code = 401


class APIConnectionError(Exception):
    pass


class NotFoundError(Exception):
    """Same class name and status as openai.NotFoundError: the key cannot use this model."""

    status_code = 404


class Probes:
    def __init__(
        self,
        openai_exc: Exception | None = None,
        langsmith_exc: Exception | None = None,
        model_excs: dict[str, Exception] | None = None,
    ):
        self.openai_exc, self.langsmith_exc = openai_exc, langsmith_exc
        self.model_excs = model_excs or {}
        self.calls: list[str] = []
        self.models: list[str] = []

    def openai(self, settings: Settings) -> None:
        self.calls.append("openai")
        if self.openai_exc:
            raise self.openai_exc

    def openai_model(self, settings: Settings, model: str) -> None:
        self.models.append(model)
        if model in self.model_excs:
            raise self.model_excs[model]

    def langsmith(self, settings: Settings) -> None:
        self.calls.append("langsmith")
        if self.langsmith_exc:
            raise self.langsmith_exc


def which_all(name: str) -> str | None:
    return f"/usr/bin/{name}"


def settings_with_keys(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENAI_API_KEY", fake_openai_key())
    monkeypatch.setenv("LANGSMITH_API_KEY", fake_langsmith_key())
    return Settings(_env_file=None)


def settings_without_keys(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    return Settings(_env_file=None)


def status(report: DoctorReport, name: str) -> str:
    return next(c.status for c in report.checks if c.name == name)


def test_missing_keys_are_reported_with_next_step(monkeypatch: pytest.MonkeyPatch) -> None:
    report = run_doctor(
        settings_without_keys(monkeypatch), offline=False, probes=Probes(), which=which_all
    )
    for name in ("OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        check = next(c for c in report.checks if c.name == name)
        assert check.status == "missing"
        assert "add it to .env at the repo root" in check.next_step
    assert report.ok is False


def test_valid_keys_are_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    probes = Probes()
    report = run_doctor(
        settings_with_keys(monkeypatch), offline=False, probes=probes, which=which_all
    )
    assert status(report, "OPENAI_API_KEY") == "ok"
    assert status(report, "LANGSMITH_API_KEY") == "ok"
    assert probes.calls == ["openai", "langsmith"]


def test_auth_error_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    report = run_doctor(
        settings_with_keys(monkeypatch),
        offline=False,
        probes=Probes(openai_exc=FakeAuthError("bad key")),
        which=which_all,
    )
    assert status(report, "OPENAI_API_KEY") == "invalid"
    assert report.ok is False


def test_connection_error_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    report = run_doctor(
        settings_with_keys(monkeypatch),
        offline=False,
        probes=Probes(langsmith_exc=APIConnectionError("down")),
        which=which_all,
    )
    assert status(report, "LANGSMITH_API_KEY") == "unreachable"


def test_offline_skips_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    probes = Probes()
    report = run_doctor(
        settings_with_keys(monkeypatch), offline=True, probes=probes, which=which_all
    )
    assert probes.calls == []
    check = next(c for c in report.checks if c.name == "OPENAI_API_KEY")
    assert check.status == "ok" and "not verified" in check.detail


def test_missing_docker_is_a_warning_not_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def which(name: str) -> str | None:
        return None if name in ("docker", "podman") else f"/usr/bin/{name}"

    report = run_doctor(
        settings_with_keys(monkeypatch), offline=False, probes=Probes(), which=which
    )
    check = next(c for c in report.checks if c.name == "container runtime")
    assert check.status == "warn"
    assert "UNSANDBOXED" in check.detail
    assert report.ok is True


def test_report_never_echoes_any_part_of_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = fake_openai_key()
    leaky = FakeAuthError(f"Incorrect API key provided: {key[:8]}****{key[-6:]}")
    report = run_doctor(
        settings_with_keys(monkeypatch),
        offline=False,
        probes=Probes(openai_exc=leaky),
        which=which_all,
    )
    text = report.render()
    for start in range(len(key) - 5):
        assert key[start : start + 6] not in text


def test_cli_exit_code_and_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from shipharness import cli

    settings_without_keys(monkeypatch)
    monkeypatch.setattr(cli, "load_settings", lambda: Settings(_env_file=None))
    result = CliRunner().invoke(cli.app, ["doctor", "--offline"])
    assert result.exit_code == 1
    assert "x missing" in result.output
    assert "OPENAI_API_KEY" in result.output


class LangSmithError(Exception):
    """Same class name as langsmith.utils.LangSmithError, raised for an invalid key (HTTP 403)."""


def test_langsmith_error_is_reported_as_invalid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    report = run_doctor(
        settings_with_keys(monkeypatch),
        offline=False,
        probes=Probes(langsmith_exc=LangSmithError("403 Forbidden")),
        which=which_all,
    )
    check = next(c for c in report.checks if c.name == "LANGSMITH_API_KEY")
    assert check.status == "invalid"
    assert "LangSmith key invalid" in check.detail
    assert report.ok is False


def test_real_langsmith_probe_maps_http_403_to_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from shipharness.doctor import RealProbes

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"]  # sent, never printed
        return httpx.Response(403, json={"detail": "Forbidden"})

    probes = RealProbes(http=httpx.Client(transport=httpx.MockTransport(handler)))
    report = run_doctor(
        settings_with_keys(monkeypatch), offline=False, probes=probes, which=which_all
    )
    check = next(c for c in report.checks if c.name == "LANGSMITH_API_KEY")
    assert check.status == "invalid"
    assert "LangSmith key invalid" in check.detail


def test_real_langsmith_probe_maps_connection_failure_to_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from shipharness.doctor import RealProbes

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    probes = RealProbes(http=httpx.Client(transport=httpx.MockTransport(handler)))
    report = run_doctor(
        settings_with_keys(monkeypatch), offline=False, probes=probes, which=which_all
    )
    assert next(c for c in report.checks if c.name == "LANGSMITH_API_KEY").status == "unreachable"


# -- course models -------------------------------------------------------------


def _check(report: DoctorReport, name: str):  # type: ignore[no-untyped-def]
    return next(c for c in report.checks if c.name == name)


def test_both_course_models_are_checked_and_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = settings_with_keys(monkeypatch)
    probes = Probes()
    report = run_doctor(settings, offline=False, probes=probes, which=which_all)
    assert probes.models == [settings.openai_model, settings.openai_eval_model]
    agent, reviewer = _check(report, "agent model"), _check(report, "reviewer model")
    assert agent.status == "ok" and agent.detail == f"{settings.openai_model} accepted"
    assert reviewer.status == "ok" and reviewer.detail == f"{settings.openai_eval_model} accepted"
    assert report.ok is True


def test_a_model_the_key_cannot_use_names_the_model_and_the_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_with_keys(monkeypatch)
    probes = Probes(model_excs={settings.openai_model: NotFoundError("no access")})
    report = run_doctor(settings, offline=False, probes=probes, which=which_all)
    agent = _check(report, "agent model")
    assert agent.status == "missing"
    assert settings.openai_model in agent.detail
    assert "program's email" in agent.next_step and "Build tier" in agent.next_step
    assert _check(report, "reviewer model").status == "ok"
    assert report.ok is False
    assert "no access" not in report.render()  # provider messages are never echoed


def test_a_permission_error_on_the_reviewer_model_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_with_keys(monkeypatch)
    probes = Probes(model_excs={settings.openai_eval_model: FakeAuthError("tier")})
    report = run_doctor(settings, offline=False, probes=probes, which=which_all)
    reviewer = _check(report, "reviewer model")
    assert reviewer.status == "missing" and settings.openai_eval_model in reviewer.detail


def test_models_are_not_checked_without_an_accepted_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for settings, probes, offline in (
        (settings_without_keys(monkeypatch), Probes(), False),
        (settings_with_keys(monkeypatch), Probes(openai_exc=FakeAuthError("bad")), False),
        (settings_with_keys(monkeypatch), Probes(), True),
    ):
        report = run_doctor(settings, offline=offline, probes=probes, which=which_all)
        assert probes.models == []
        assert not [c for c in report.checks if c.name in ("agent model", "reviewer model")]


def _model_json(model: str) -> dict[str, object]:
    return {"id": model, "object": "model", "created": 0, "owned_by": "openai"}


def test_real_model_probe_asks_for_each_model_by_id_and_uses_no_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from shipharness.doctor import RealProbes

    settings = settings_with_keys(monkeypatch)
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"object": "list", "data": []})
        model = request.url.path.rsplit("/", 1)[-1]
        if model == settings.openai_model:
            return httpx.Response(
                404,
                json={"error": {"message": "does not exist", "type": "invalid_request_error"}},
            )
        return httpx.Response(200, json=_model_json(model))

    probes = RealProbes(openai_http=httpx.Client(transport=httpx.MockTransport(handler)))
    report = run_doctor(settings, offline=False, probes=probes, which=which_all)
    assert f"/v1/models/{settings.openai_model}" in paths
    assert f"/v1/models/{settings.openai_eval_model}" in paths
    assert all(p.startswith("/v1/models") for p in paths)  # no completion call, no tokens
    assert _check(report, "OPENAI_API_KEY").status == "ok"
    assert _check(report, "agent model").status == "missing"
    assert _check(report, "reviewer model").status == "ok"


# -- class date --------------------------------------------------------------


def _date_check(report: DoctorReport):  # type: ignore[no-untyped-def]
    return next(c for c in report.checks if c.name == "SHIPHARNESS_CLASS_DATE")


def _with_date(monkeypatch: pytest.MonkeyPatch, day: str | None) -> Settings:
    settings_with_keys(monkeypatch)
    if day is None:
        monkeypatch.delenv("SHIPHARNESS_CLASS_DATE", raising=False)
    else:
        monkeypatch.setenv("SHIPHARNESS_CLASS_DATE", day)
    return Settings(_env_file=None)


def test_class_purpose_without_a_class_date_is_a_failed_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = run_doctor(
        _with_date(monkeypatch, None), offline=True, purpose="class", probes=Probes(),
        which=which_all,
    )  # fmt: skip
    check = _date_check(report)
    assert check.status == "missing"
    assert report.ok is False
    text = report.render()
    assert "SHIPHARNESS_CLASS_DATE=YYYY-MM-DD" in text  # the line to add to .env
    assert ".env" in text
    assert "export SHIPHARNESS_CLASS_DATE=YYYY-MM-DD" in text
    assert "shipharness-class-<date>" in text


@pytest.mark.parametrize("day", ["20-10-2026", "2026-13-40", "2026/10/20", "tomorrow"])
def test_a_malformed_class_date_is_a_failed_item(monkeypatch: pytest.MonkeyPatch, day: str) -> None:
    report = run_doctor(
        _with_date(monkeypatch, day), offline=True, purpose="class", probes=Probes(),
        which=which_all,
    )  # fmt: skip
    check = _date_check(report)
    assert check.status == "invalid"
    assert "YYYY-MM-DD" in check.detail and day in check.detail
    assert report.ok is False


def test_a_valid_class_date_names_the_class_project(monkeypatch: pytest.MonkeyPatch) -> None:
    report = run_doctor(
        _with_date(monkeypatch, "2026-10-20"), offline=True, purpose="class", probes=Probes(),
        which=which_all,
    )  # fmt: skip
    check = _date_check(report)
    assert check.status == "ok"
    assert "shipharness-class-2026-10-20" in check.detail


@pytest.mark.parametrize("purpose", ["pilot", "assignment"])
def test_pilot_and_assignment_need_no_class_date(
    monkeypatch: pytest.MonkeyPatch, purpose: str
) -> None:
    report = run_doctor(
        _with_date(monkeypatch, None), offline=True, purpose=purpose, probes=Probes(),
        which=which_all,
    )  # fmt: skip
    assert _date_check(report).status == "ok"
    assert all(c.status == "ok" or c.name != "SHIPHARNESS_CLASS_DATE" for c in report.checks)


def test_cli_doctor_purpose_class_fails_without_a_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from shipharness import cli

    _with_date(monkeypatch, None)
    monkeypatch.setattr(cli, "load_settings", lambda: Settings(_env_file=None))
    result = CliRunner().invoke(cli.app, ["doctor", "--offline", "--purpose", "class"])
    assert result.exit_code == 1
    assert "SHIPHARNESS_CLASS_DATE" in result.output
    assert "export SHIPHARNESS_CLASS_DATE=YYYY-MM-DD" in result.output
    default = CliRunner().invoke(cli.app, ["doctor", "--offline"])
    assert "SHIPHARNESS_CLASS_DATE" in default.output  # make doctor's default purpose is class


def test_cli_doctor_purpose_pilot_reports_no_date_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from shipharness import cli

    _with_date(monkeypatch, None)
    monkeypatch.setattr(cli, "load_settings", lambda: Settings(_env_file=None))
    result = CliRunner().invoke(cli.app, ["doctor", "--offline", "--purpose", "pilot"])
    failing = [line for line in result.output.splitlines() if line.lstrip().startswith("x ")]
    assert not [line for line in failing if "SHIPHARNESS_CLASS_DATE" in line]


def test_cli_doctor_refuses_an_unknown_purpose(monkeypatch: pytest.MonkeyPatch) -> None:
    from shipharness import cli

    monkeypatch.setattr(cli, "load_settings", lambda: Settings(_env_file=None))
    result = CliRunner().invoke(cli.app, ["doctor", "--offline", "--purpose", "demo"])
    assert result.exit_code == 2
    assert "class, pilot, or assignment" in result.output
