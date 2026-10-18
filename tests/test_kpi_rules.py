import datetime as dt

from spm_sr.thanatos import kpi_rules as K

TH_S = {"yellow_gap_pp": -5, "red_gap_pp": -15}
TH_C = {"green_cpi": 0.95, "yellow_cpi": 0.85, "max_consumption": 1.0}
TH_R = {"green_low": 0.9, "green_high": 1.1, "yellow_low": 0.8, "yellow_high": 1.25}
TH_SC = {"yellow_pending": 1, "red_pending": 3}
AS_OF = dt.date(2026, 10, 19)


def proj(**kw):
    base = {"planned_start": AS_OF - dt.timedelta(days=50), "planned_end": AS_OF + dt.timedelta(days=50),
            "percent_complete": 50, "planned_cost": 100000, "actual_cost": 50000,
            "planned_effort": 1000, "actual_effort": 500}
    base.update(kw)
    return base


def test_schedule_green_yellow_red():
    assert K.schedule(proj(), AS_OF, TH_S)["color"] == K.G
    assert K.schedule(proj(percent_complete=40), AS_OF, TH_S)["color"] == K.Y      # -10 pp
    assert K.schedule(proj(percent_complete=30), AS_OF, TH_S)["color"] == K.R      # -20 pp


def test_schedule_overdue_is_red():
    p = proj(planned_end=AS_OF - dt.timedelta(days=1), percent_complete=99)
    r = K.schedule(p, AS_OF, TH_S)
    assert r["color"] == K.R and r["overdue"] and r["end_variance_days"] == 1


def test_schedule_missing_dates():
    assert K.schedule(proj(planned_end=None), AS_OF, TH_S)["color"] == K.DF


def test_cost_cpi_bands():
    assert K.cost(proj(), TH_C)["color"] == K.G
    assert K.cost(proj(actual_cost=55556), TH_C)["color"] == K.Y
    assert K.cost(proj(actual_cost=62000), TH_C)["color"] == K.R
    assert K.cost(proj(percent_complete=100, actual_cost=110000), TH_C)["color"] == K.R  # consumo > 100 %


def test_cost_zero_budget_is_missing_not_green():
    assert K.cost(proj(planned_cost=0), TH_C)["color"] == K.DF


def test_resources_bands_and_zero_progress():
    assert K.resources(proj(), None, TH_R)["color"] == K.G
    assert K.resources(proj(actual_effort=600), None, TH_R)["color"] == K.Y      # 1.2
    assert K.resources(proj(actual_effort=700), None, TH_R)["color"] == K.R      # 1.4
    assert K.resources(proj(percent_complete=0, actual_effort=0), None, TH_R)["color"] == K.G
    assert K.resources(proj(percent_complete=0, actual_effort=10), None, TH_R)["color"] == K.Y


def test_scope():
    pend = {"requested", "pending"}
    assert K.scope([], True, TH_SC, pend)["color"] == K.G
    assert K.scope([{"state": "requested"}], True, TH_SC, pend)["color"] == K.Y
    assert K.scope([{"state": "requested"}] * 3, True, TH_SC, pend)["color"] == K.R
    assert K.scope(None, False, TH_SC, pend)["color"] == K.DF


def test_overall_rules():
    assert K.overall({"schedule": K.G, "cost": K.G, "resources": K.G, "scope": K.G})["color"] == K.G
    assert K.overall({"schedule": K.R, "cost": K.G, "resources": K.G, "scope": K.G})["color"] == K.R
    assert K.overall({"schedule": K.G, "cost": K.G, "resources": K.G, "scope": K.R})["color"] == K.Y
    assert K.overall({"schedule": K.G, "cost": K.G, "resources": K.R, "scope": K.R})["color"] == K.R
    o = K.overall({"schedule": K.G, "cost": K.DF, "resources": K.G, "scope": K.G})
    assert o["color"] == K.G and o["incomplete_evidence"]


def test_compare():
    assert K.compare(K.G, K.R) == "Optimismo"
    assert K.compare(K.R, K.G) == "Conservador"
    assert K.compare(K.Y, K.Y) == "Consistente"
    assert K.compare(None, K.G) == "No comparable"
