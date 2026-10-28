from model.capacity import Surge, Users, required_capacity, simulate

SURGE = Surge(peak=200, pre_release_s=30, rise_s=5, decay_tau_s=30, post_release_s=120)
CALM = Users(retry_prob=0, impatient_retry_prob=0)


def test_ample_capacity_serves_everyone():
    r = simulate(SURGE, CALM, mu=5000)
    assert r.served_ok > 0.999
    assert r.success_within["2s"] > 0.99
    assert abs(r.amplification - 1) < 0.01


def test_overload_hurts_and_retries_amplify():
    calm = simulate(SURGE, CALM, mu=100)
    assert calm.success_within["5s"] < 0.9
    angry = simulate(SURGE, Users(retry_prob=0.9, impatient_retry_prob=0.9, patience=(3, 6)), mu=100)
    assert angry.amplification > calm.amplification


def test_monotone_in_capacity():
    vals = [simulate(SURGE, Users(), mu=m).success_within["5s"] for m in (80, 160, 320, 640)]
    assert all(b >= a - 1e-9 for a, b in zip(vals, vals[1:]))


def test_required_capacity_meets_target():
    mu = required_capacity(SURGE, Users(), target=0.95, deadline="5s", eta=1.0, dt=1.0)
    assert simulate(SURGE, Users(), mu, dt=1.0, drain_s=600).success_within["5s"] >= 0.95
    assert simulate(SURGE, Users(), mu * 0.7, dt=1.0, drain_s=600).success_within["5s"] < 0.95
