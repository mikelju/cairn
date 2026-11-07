"""Deploy to Lightsail keeping the active deployment's environment (keys set by hand survive)."""

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

# Local values for these names override the active deployment; unset ones never delete anything.
DEPLOY_VARS = ("CAIRN_ACCESS_CODE", "CAIRN_LIVE_CAP_USD")
Runner = Callable[[list[str]], str]


def run_aws(command: list[str]) -> str:
    """Run an AWS CLI command and return stdout (profile from the environment)."""
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def current_environment(service: str, region: str, run: Runner = run_aws) -> dict[str, str]:
    """Environment of the active app container; empty if there is no deployment yet."""
    query = "containerServices[0].currentDeployment.containers.app.environment"
    command = ["aws", "lightsail", "get-container-services", "--service-name", service]
    command += ["--region", region, "--query", query, "--output", "json"]
    found = json.loads(run(command) or "null")
    return {str(k): str(v) for k, v in found.items()} if isinstance(found, dict) else {}


def merge_environment(
    current: Mapping[str, str], local: Mapping[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Return the merged map and a status per name: kept, overridden or added."""
    merged = dict(current)
    status = {name: "kept" for name in current}
    for name in DEPLOY_VARS:
        value = local.get(name, "")
        if value:
            status[name] = "overridden" if name in current else "added"
            merged[name] = value
    return merged, status


def containers_json(image: str, environment: Mapping[str, str]) -> str:
    app: dict[str, object] = {"image": image, "ports": {"8000": "HTTP"}}
    if environment:
        app["environment"] = dict(environment)
    return json.dumps({"app": app})


def deploy(
    service: str,
    region: str,
    dry_run: bool = False,
    run: Runner = run_aws,
    local: Mapping[str, str] | None = None,
    log: Callable[[str], None] = print,
) -> None:
    """Merge environments and create the deployment; only names are ever logged."""
    local_env = os.environ if local is None else local
    merged, status = merge_environment(current_environment(service, region, run), local_env)
    names = ", ".join(f"{name} ({state})" for name, state in sorted(status.items()))
    log(f"environment variables: {names or 'none'}")
    if dry_run:
        log("dry run: no deployment created")
        return
    images = ["aws", "lightsail", "get-container-images", "--service-name", service]
    images += ["--region", region, "--query", "containerImages[0].image", "--output", "text"]
    image = run(images).strip()
    handle, name = tempfile.mkstemp(prefix="cairn-containers-", suffix=".json")
    path = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(containers_json(image, merged))
        command = ["aws", "lightsail", "create-container-service-deployment"]
        command += ["--service-name", service, "--region", region]
        command += ["--containers", f"file://{path}"]
        command += [
            "--public-endpoint",
            "containerName=app,containerPort=8000,healthCheck={path=/healthz}",
        ]
        run(command)
    finally:
        path.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    service, region = [a for a in argv if a != "--dry-run"]
    deploy(service, region, dry_run=dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
