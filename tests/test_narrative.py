from spm_sr.thanatos.narrative import verify_numbers

FACTS = {"number": "PRJ0002", "performance": {"schedule": {"percent_complete": 40.0, "expected_pct": 60.0,
                                                           "gap_pp": -20.0}, "cost": {"cpi": 0.9}}}


def test_traceable_numbers_pass():
    ok, bad = verify_numbers("El avance es 40% contra 60% esperado (-20 pp) y CPI 0.9.", FACTS)
    assert ok, bad


def test_invented_number_rejected():
    ok, bad = verify_numbers("El proyecto tiene un sobrecosto de 37% y 45 días de atraso.", FACTS)
    assert not ok and "37" in bad


class _Block:
    def __init__(self, type_, text=""):
        self.type, self.text = type_, text


class _Msg:
    def __init__(self, blocks, stop="end_turn"):
        self.content, self.stop_reason = blocks, stop


class _Client:
    def __init__(self, msg):
        self.messages = self
        self._msg = msg

    def create(self, **kw):
        return self._msg


def _narrator(msg):
    from spm_sr.thanatos.narrative import Narrator

    n = Narrator({"llm": {"enabled": False}})
    n.enabled, n._client, n.model = True, _Client(msg), "x"
    return n


def test_empty_llm_text_falls_back_to_template():
    n = _narrator(_Msg([_Block("thinking")], stop="max_tokens"))
    out = n.narrate(FACTS, "PLANTILLA")
    assert out["source"] == "plantilla" and out["text"] == "PLANTILLA" and out["llm_error"] == "E-LLM-03"


def test_valid_llm_text_is_used():
    n = _narrator(_Msg([_Block("text", "Avance 40% vs 60% esperado.")]))
    assert n.narrate(FACTS, "PLANTILLA")["source"] == "llm"


def test_dates_in_facts_are_traceable():
    import datetime as dt

    ok, bad = verify_numbers("Fin planeado 2026-10-09.", {"planned_end": dt.date(2026, 10, 9)})
    assert ok, bad
