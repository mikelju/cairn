import json
from pathlib import Path

import pytest

from cairn import deploy_env

CURRENT = {"AWS_ACCESS_KEY_ID": "AKIA-secret", "CAIRN_ACCESS_CODE": "old-code"}


class FakeAws:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.file: Path | None = None
        self.contents = ""
        self.fail = fail

    def __call__(self, command: list[str]) -> str:
        self.calls.append(command)
        verb = command[2]
        if verb == "get-container-services":
            return json.dumps(CURRENT)
        if verb == "get-container-images":
            return "svc:app.1\n"
        arg = command[command.index("--containers") + 1]
        assert arg.startswith("file://")
        self.file = Path(arg.removeprefix("file://"))
        self.contents = self.file.read_text(encoding="utf-8")
        if self.fail:
            raise RuntimeError("aws failed")
        return ""


def test_merge_overrides_and_keeps() -> None:
    merged, status = deploy_env.merge_environment(CURRENT, {"CAIRN_LIVE_CAP_USD": "5"})
    assert merged == {**CURRENT, "CAIRN_LIVE_CAP_USD": "5"}
    assert status == {
        "AWS_ACCESS_KEY_ID": "kept",
        "CAIRN_ACCESS_CODE": "kept",
        "CAIRN_LIVE_CAP_USD": "added",
    }
    merged, status = deploy_env.merge_environment(CURRENT, {"CAIRN_ACCESS_CODE": "new"})
    assert merged["CAIRN_ACCESS_CODE"] == "new"
    assert status["CAIRN_ACCESS_CODE"] == "overridden"


def test_unset_local_vars_keep_existing() -> None:
    merged, _ = deploy_env.merge_environment(CURRENT, {"CAIRN_ACCESS_CODE": ""})
    assert merged == CURRENT


def test_current_environment_empty_without_deployment() -> None:
    assert deploy_env.current_environment("s", "r", lambda _c: "null\n") == {}


def test_deploy_writes_temp_file_and_removes_it(capsys: pytest.CaptureFixture[str]) -> None:
    aws = FakeAws()
    logged: list[str] = []
    deploy_env.deploy("s", "r", run=aws, local={"CAIRN_LIVE_CAP_USD": "5"}, log=logged.append)
    body = json.loads(aws.contents)
    assert body["app"]["image"] == "svc:app.1"
    assert body["app"]["ports"] == {"8000": "HTTP"}
    assert body["app"]["environment"] == {**CURRENT, "CAIRN_LIVE_CAP_USD": "5"}
    assert aws.file is not None and not aws.file.exists()
    command = " ".join(aws.calls[-1])
    assert "AKIA-secret" not in command and "old-code" not in command
    assert "AKIA-secret" not in "".join(logged) and "old-code" not in "".join(logged)
    assert "AWS_ACCESS_KEY_ID (kept)" in logged[0]


def test_temp_file_removed_on_failure() -> None:
    aws = FakeAws(fail=True)
    with pytest.raises(RuntimeError):
        deploy_env.deploy("s", "r", run=aws, local={}, log=lambda _m: None)
    assert aws.file is not None and not aws.file.exists()


def test_dry_run_prints_names_only_and_creates_nothing() -> None:
    aws = FakeAws()
    logged: list[str] = []
    deploy_env.deploy("s", "r", dry_run=True, run=aws, local={}, log=logged.append)
    assert all(c[2] == "get-container-services" for c in aws.calls)
    assert aws.file is None
    assert "old-code" not in "".join(logged)
    assert "CAIRN_ACCESS_CODE (kept)" in logged[0]


MAKEFILE = Path(__file__).resolve().parent.parent / "Makefile"


def test_makefile_has_no_literal_backslash_n_and_continuations_are_clean() -> None:
    lines = MAKEFILE.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if line.startswith("\t") and "\\n" in line:
            outside = line.replace('"', "'")
            quoted = any(part for part in outside.split("'")[1::2] if "\\n" in part)
            assert quoted or "$$" in line, f"Makefile:{number} has a literal backslash-n"
        if line.endswith("\\"):
            assert lines[number].startswith("\t"), (
                f"Makefile:{number} continuation is not followed by a tab line"
            )


def test_deploy_recipe_joins_get_and_create_with_or() -> None:
    lines = MAKEFILE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("deploy: $("))
    first = [lines[start + 1].lstrip("\t")]
    while first[-1].endswith("\\"):
        first.append(lines[start + len(first) + 1].lstrip("\t"))
    command = " ".join(part.removesuffix("\\").strip() for part in first)
    check, _, create = command.partition("||")
    assert "get-container-services" in check and "create-container-service" not in check
    assert "create-container-service" in create and "get-container-services" not in create
    assert " n " not in check
