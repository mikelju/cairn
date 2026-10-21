"""Shared fixtures: the app's DuckDB file is built once when it is missing."""

from dataclasses import dataclass

import pytest

from cairn.body_weight import body_weight_change
from cairn.content import ObservationLedger, ValueRef
from cairn.incidence import incidence
from cairn.ingest import DEFAULT_DB, ingest
from cairn.tk_summary import tk_summary
from cairn.tools import study_design


@pytest.fixture(scope="session", autouse=True)
def app_database() -> None:
    if not DEFAULT_DB.exists():
        ingest()


@dataclass
class World:
    """One ledger with a real Observation of each study tool, for building drafts."""

    ledger: ObservationLedger
    design: str
    incidence: str
    weight: str
    tk: str

    def ref(self, obs_id: str, field: str) -> ValueRef:
        return ValueRef(obs_id=obs_id, field=field)


@pytest.fixture
def world() -> World:
    ledger = ObservationLedger()
    return World(
        ledger=ledger,
        design=ledger.add(study_design()),
        incidence=ledger.add(incidence()),
        weight=ledger.add(body_weight_change()),
        tk=ledger.add(tk_summary()),
    )
