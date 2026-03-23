# tests/test_phase44_validation.py
#
# PHASE 44 — Validation & Invariants
#
# Purpose:
# - Prove confidence + Greeks overlays do NOT affect execution
# - Enforce fail-closed behavior
# - Validate determinism invariants
#
# NO production code is modified by this file.
#

import pytest
import datetime as dt

from indicator_authority import create_indicator_assertion
from signal_context import create_signal_context
from confidence_engine import ConfidenceEngine
from greeks_overlay import GreeksSnapshot


# --------------------------------------------------
# Fixtures
# --------------------------------------------------

@pytest.fixture
def dummy_signal_context():
    return create_signal_context(
        symbol="SPY",
        timestamp_utc=dt.datetime(2026, 1, 16, 14, 0, tzinfo=dt.timezone.utc),
        indicators={"RSI(7)": 55},
        rules_passed={"test": True},
        source="TEST",
        engine_version="TEST",
    )


@pytest.fixture
def dummy_indicator_assertion():
    return create_indicator_assertion(
        required={
            "VWAP_Position": "above",
            "EMA9_Slope": "up",
            "RSI(7)": 55,
            "MACD_Histogram": 0.12,
            "ATR_State": "expanding",
        },
        advisory={},
    )


@pytest.fixture
def valid_greeks_snapshot():
    return GreeksSnapshot(
        symbol="SPY",
        expiry="20260116",
        strike=500.0,
        right="C",
        timestamp_utc="2026-01-16T14:00:00Z",
        delta=0.45,
        gamma=0.015,
        theta=-0.08,
        iv=0.32,
        iv_change=0.05,
        volume=1200,
        open_interest=800,
        spread_pct=0.05,
        premium=2.50,
        gamma_efficiency=0.006,
        vol_oi_ratio=1.5,
    )


# --------------------------------------------------
# Tests — Fail Closed
# --------------------------------------------------

def test_confidence_fails_closed_without_greeks(
    dummy_signal_context,
    dummy_indicator_assertion,
):
    report = ConfidenceEngine.evaluate(
        signal_context=dummy_signal_context,
        indicator_assertion=dummy_indicator_assertion,
        greeks_snapshot=None,
    )

    assert report.confidence_score is None
    assert report.confidence_label == "UNSCORED"


# --------------------------------------------------
# Tests — Determinism
# --------------------------------------------------

def test_confidence_deterministic_output(
    dummy_signal_context,
    dummy_indicator_assertion,
    valid_greeks_snapshot,
):
    r1 = ConfidenceEngine.evaluate(
        signal_context=dummy_signal_context,
        indicator_assertion=dummy_indicator_assertion,
        greeks_snapshot=valid_greeks_snapshot,
    )

    r2 = ConfidenceEngine.evaluate(
        signal_context=dummy_signal_context,
        indicator_assertion=dummy_indicator_assertion,
        greeks_snapshot=valid_greeks_snapshot,
    )

    assert r1.confidence_score == r2.confidence_score
    assert r1.confidence_label == r2.confidence_label


# --------------------------------------------------
# Tests — Advisory Only (No Authority)
# --------------------------------------------------

def test_confidence_not_hashed(
    dummy_signal_context,
    dummy_indicator_assertion,
    valid_greeks_snapshot,
):
    report = ConfidenceEngine.evaluate(
        signal_context=dummy_signal_context,
        indicator_assertion=dummy_indicator_assertion,
        greeks_snapshot=valid_greeks_snapshot,
    )

    assert not hasattr(report, "hash")
    assert "confidence" in report.engine_version.lower()


# --------------------------------------------------
# Tests — Range Safety
# --------------------------------------------------

def test_confidence_score_bounds(
    dummy_signal_context,
    dummy_indicator_assertion,
    valid_greeks_snapshot,
):
    report = ConfidenceEngine.evaluate(
        signal_context=dummy_signal_context,
        indicator_assertion=dummy_indicator_assertion,
        greeks_snapshot=valid_greeks_snapshot,
    )

    assert 0.0 <= report.confidence_score <= 1.0
