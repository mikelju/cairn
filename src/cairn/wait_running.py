"""Bounded wait until a Lightsail container service is RUNNING after a deployment."""

import json
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

TRIES = 30
INTERVAL_SECONDS = 10
FAILED_STATES = {"DISABLED", "DELETING"}


def aws_service(service: str, region: str) -> dict[str, Any]:
    """Return the container service description from the AWS CLI (profile from the environment)."""
    command = ["aws", "lightsail", "get-container-services", "--service-name", service]
    command += ["--region", region, "--output", "json"]
    out = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    return json.loads(out)["containerServices"][0]


def wait_running(
    fetch: Callable[[], dict[str, Any]],
    tries: int = TRIES,
    interval: float = INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> bool:
    """Poll until RUNNING with no pending deployment; False if it fails or tries run out."""
    for attempt in range(1, tries + 1):
        service = fetch()
        state = service.get("state", "UNKNOWN")
        pending = (service.get("nextDeployment") or {}).get("state")
        log(f"try {attempt}/{tries}: state {state}, pending deployment {pending or 'none'}")
        if state in FAILED_STATES or pending == "FAILED":
            log("deployment failed: check the Lightsail console for the container logs")
            return False
        if state == "RUNNING" and pending is None:
            return True
        if attempt < tries:
            sleep(interval)
    log(f"gave up after {tries} tries ({tries * interval:.0f} s) without RUNNING")
    return False


def main(argv: list[str]) -> int:
    service, region = argv
    return 0 if wait_running(lambda: aws_service(service, region)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
