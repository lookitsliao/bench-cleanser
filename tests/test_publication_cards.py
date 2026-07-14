"""Fail-closed claims for the pre-release data and router cards."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_card_cannot_imply_a_released_or_populated_corpus() -> None:
    text = (ROOT / "docs" / "DATA_CARD.md").read_text(encoding="utf-8")

    assert "There is no released\nor populated verification-gap dataset" in text
    assert "No populated paired corpus exists" in text
    assert "Public availability is not redistribution\npermission" in text
    assert "signed release dossier" in text


def test_router_card_names_baseline_identity_and_negative_results() -> None:
    text = (ROOT / "docs" / "ROUTER_CARD.md").read_text(encoding="utf-8")

    assert '`RoutingPolicy(version="conservative-v1")`' in text
    assert "deterministic engineering baseline" in text
    assert "uncalibrated" in text.casefold()
    assert "0.53249" in text
    assert "patch size beats\n  router risk" in text
    assert "no task-validity prediction" in text
    assert "not cryptographic producer identity" in text


def test_cards_point_to_the_same_prospective_protocol() -> None:
    relative = "experiments/prospective_pilot/PREREGISTRATION.md"
    data = (ROOT / "docs" / "DATA_CARD.md").read_text(encoding="utf-8")
    router = (ROOT / "docs" / "ROUTER_CARD.md").read_text(encoding="utf-8")

    assert relative in data
    assert relative in router
