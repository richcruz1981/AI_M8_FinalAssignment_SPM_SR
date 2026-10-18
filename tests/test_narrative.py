from spm_sr.thanatos.narrative import verify_numbers

FACTS = {"number": "PRJ0002", "performance": {"schedule": {"percent_complete": 40.0, "expected_pct": 60.0,
                                                           "gap_pp": -20.0}, "cost": {"cpi": 0.9}}}


def test_traceable_numbers_pass():
    ok, bad = verify_numbers("El avance es 40% contra 60% esperado (-20 pp) y CPI 0.9.", FACTS)
    assert ok, bad


def test_invented_number_rejected():
    ok, bad = verify_numbers("El proyecto tiene un sobrecosto de 37% y 45 días de atraso.", FACTS)
    assert not ok and "37" in bad
