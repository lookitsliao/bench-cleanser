"""Provenance regressions for the standalone audit workflow."""

from __future__ import annotations

from tools.audit import ContaminationAuditor, DataManager


def test_tracker_records_the_actual_auditor_identity(monkeypatch) -> None:
    result = {
        "verdict": "CLEAN",
        "evidence_strength": "strong",
        "failure_reason": "genuine_difficulty",
        "reasoning": "The agent did not implement the requested behavior.",
        "auditor_identity": "openai-compatible:fixture-model",
        "timestamp": "2026-07-12 00:00:00",
    }
    monkeypatch.setattr(
        DataManager,
        "load_analysis",
        staticmethod(lambda case_num: result if case_num == 1 else None),
    )
    rows = [{"case_num": "1", "human_verdict": ""}]

    updated = ContaminationAuditor.update_tracker(rows)

    assert updated == 1
    assert rows[0]["audited_by"] == "openai-compatible:fixture-model"


def test_legacy_analysis_without_identity_is_marked_unknown(monkeypatch) -> None:
    monkeypatch.setattr(
        DataManager,
        "load_analysis",
        staticmethod(lambda case_num: {"verdict": "CLEAN"}),
    )
    rows = [{"case_num": "1", "human_verdict": ""}]

    ContaminationAuditor.update_tracker(rows)

    assert rows[0]["audited_by"] == "llm:unknown"
