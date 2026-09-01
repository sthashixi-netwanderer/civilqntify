"""Shared outcome types for the per-standard compliance evaluators.

Both :mod:`concrete_mix.validation.astm_c33` and
:mod:`concrete_mix.validation.is383` report each requirement of their
standard as a :class:`ClauseCheck` so the UI can render one table and one
clause-cited dialog regardless of the selected standard.
"""

from __future__ import annotations

from dataclasses import dataclass

PASS = "pass"
FAIL = "fail"
NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class ClauseCheck:
    """Outcome of one standard requirement.

    status is one of ``pass`` / ``fail`` / ``not_evaluated``. Requirements
    the user has no test result for are reported as ``not_evaluated`` —
    they never trigger the non-conformance dialog. A dash/blank cell of the
    standard's tables ("no requirement") is reported the same way.
    """

    clause: str
    title: str
    status: str
    requirement: str
    measured: str
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.status == FAIL
