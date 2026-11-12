"""Capacity-planning model (plan section 8.1).

A fluid model of result day. Students arrive following the surge curve and ask
a bounded server for their result. The server works like `rb portal`
(internal/portal/portal.go):

- at most `workers` requests are in service at once, and together they are
  finished at `mu` answers per second (the CPU limit divided by the CPU one
  answer costs);
- at most `queue_cap` more wait for a worker; a request beyond that gets a 503
  at once;
- a request that times out while it is still waiting is dropped at no cost,
  but one that times out after a worker took it is finished anyway, because
  CANCEL_ON_DISCONNECT is off, as in most stacks. Nobody receives that answer,
  so the work is wasted.

Students behave like the load generator's students (internal/surge/run.go).
Each student has one patience, and every request times out after it. After a
failure (a 503 or a time-out) a student refreshes with some probability after
a short pause, and gives up after `max_attempts` failures. Students who arrive
before release poll every few seconds; some look again after seeing their
result.

Nothing is fitted to the outcomes. mu comes from the CPU limit and the CPU
measured per answer; the server limits and the student behaviour come from
the run's configuration. `validate` compares the predictions with lab runs.

    # predict one configuration (mu in answers per second)
    python -m model.capacity simulate --scenario bench/scenarios/paper.yaml --capacity 187 --peak 447

    # predict every run of a design from its configuration and report the error
    python -m model.capacity validate runs/paper-core runs/paper-refresh --design a --out runs/model-a.csv

    # planning table for real board sizes
    python -m model.capacity plan --cpu-costs runs/paper-core/report/summary.csv --out planning.md
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import random
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Surge:
    peak: float
    pre_release_s: float = 60
    start_frac: float = 0.02
    end_frac: float = 0.2
    rise_s: float = 5
    decay_tau_s: float = 90
    floor_frac: float = 0.02
    post_release_s: float = 300
    shape: str = "surge"

    def rate(self, t: float) -> float:
        """Same curve as surge.SurgeSpec.Rate in the Go generator."""
        p = self.peak
        if t > self.post_release_s:
            return 0.0
        if self.shape == "constant":
            return p if t >= 0 else 0.0
        if t < -self.pre_release_s:
            return 0.0
        if t < 0:
            f = (t + self.pre_release_s) / self.pre_release_s
            return p * (self.start_frac + (self.end_frac - self.start_frac) * f)
        if t < self.rise_s:
            return p * (self.end_frac + (1 - self.end_frac) * t / self.rise_s)
        floor = self.floor_frac * p
        return floor + (p - floor) * math.exp(-(t - self.rise_s) / max(self.decay_tau_s, 1e-9))


@dataclass
class Users:
    patience: tuple[float, float] = (5, 20)
    retry_prob: float = 0.8
    impatient_retry_prob: float = 0.9
    retry_delay: tuple[float, float] = (1, 5)
    max_attempts: int = 20
    prerelease_poll: tuple[float, float] = (10, 30)
    repeat_view_prob: float = 0.0
    repeat_after: tuple[float, float] = (5, 20)
    queue_manual_refresh_per_min: float = 1.0  # manual refreshes while held in a waiting room


@dataclass
class Room:
    """A virtual waiting room in front of the server, like `rb waitingroom`
    (internal/wroom). It admits students at `admit_rate` per second in arrival
    order. A queued student learns of the admission at the next poll, and
    from then on reaches the server directly for `session_s` seconds,
    retries included.

    With naive tickets, a manual refresh loses the ticket. The student joins
    again at the back, and the old ticket stays in the queue: the room still
    admits it, which wastes the admission, unless it has gone unseen for
    `abandon_s`. With token tickets, a refresh keeps the place. `request_cap`
    (not in rb waitingroom yet) would end the session after that many server
    requests, sending the student back to the queue.

    The room has its own CPU (`cpus`; 0 means unlimited). Answering a queued
    student costs `cost_queued` CPU-seconds, and passing a request through to
    the server costs `cost_proxied`. When polls and passed-through requests
    need more CPU than the room has, every request waits in the room. That
    wait eats the student's patience: a poll that waits longer than the
    patience is a time-out, and a request bound for the server reaches it
    late or not at all."""
    admit_rate: float
    mode: str = "token"
    session_s: float = 60.0
    abandon_s: float = 30.0
    poll_s: float = 5.0
    request_cap: int = 0
    cpus: float = 0.0
    cost_queued: float = 45e-6
    cost_proxied: float = 350e-6
    max_delay_s: float = 60.0


@dataclass
class Result:
    users: float
    served: float
    requests: float
    success_within: dict = field(default_factory=dict)
    timeline: list = field(default_factory=list)
    polls: float = 0.0       # requests sent before release (answered "not released")
    completed: float = 0.0   # answers the server finished after release
    delivered: float = 0.0   # ... while the student was still waiting
    wasted: float = 0.0      # ... after the student had already given up on that request
    dropped: float = 0.0     # requests that timed out before a worker took them
    rejected: float = 0.0    # 503 because the queue was full
    cancelled: float = 0.0   # started requests stopped when the student left (cancel_on_disconnect)
    late: float = 0.0        # requests that timed out after a worker took them
    # Outcomes per second of the request's send time, like the generator's
    # timeseries.csv (only with keep_timeline): second -> outcome -> requests.
    by_send: dict = field(default_factory=dict)
    gave_up: float = 0.0     # students who stopped trying (no refresh, or max_attempts)
    backend_requests: float = 0.0   # requests that reached the server (not answered by a waiting room)
    admitted: float = 0.0           # waiting-room admissions, including lost (naive) tickets
    wasted_admissions: float = 0.0  # admissions of tickets whose student had lost them
    wait_p50_s: float = math.nan    # median wait from first request to first admission
    still_queued: float = 0.0       # students still in the waiting room at the end
    room_timeouts: float = 0.0      # requests bound for the server that timed out inside a saturated room

    @property
    def served_ok(self) -> float:
        return self.served / self.users if self.users else 0.0

    @property
    def amplification(self) -> float:
        return self.requests / self.users if self.users else 0.0

    @property
    def backend_amplification(self) -> float:
        return self.backend_requests / self.users if self.users else 0.0

    @property
    def useful_share(self) -> float:
        """Share of the answers the server finished that reached a waiting student."""
        return self.delivered / self.completed if self.completed else math.nan


class _Cohort:
    """Requests sent in the same step by students in the same state."""
    __slots__ = ("amount", "k", "first", "failures", "repeat", "expires", "started", "live", "session", "cap",
                 "entered")

    def __init__(self, amount: float, k: int, first, failures: int, repeat: bool, expires: int, started: bool,
                 session=None, cap=None, entered: int = 0):
        self.amount = amount
        self.k = k                # patience class
        self.first = first        # step of the student's first request after release; None once past every deadline
        self.failures = failures
        self.repeat = repeat      # a look-again request after the result was seen
        self.expires = expires    # step at which the request times out
        self.started = started    # a worker has taken it
        self.live = True          # the student is still waiting for this answer
        self.session = session    # waiting room: step at which the admission ends (None: no room)
        self.cap = cap            # waiting room: failures at which the admission ends (None: no cap)
        self.entered = entered    # step it reached the server (requests of one step count as simultaneous)


class _Ticket:
    """Waiting-room tickets of students in the same state who joined the queue together."""
    __slots__ = ("live", "k", "first", "failures", "t0", "created", "ghosts")

    def __init__(self, live: float, k: int, first, failures: int, t0, created: int):
        self.live = live          # students who still hold these tickets
        self.k = k
        self.first = first
        self.failures = failures
        self.t0 = t0              # first request after release (step, for the wait); None if not a first admission
        self.created = created
        self.ghosts: dict[int, float] = {}  # step a ticket was lost (naive refresh) -> tickets


def _prerelease(surge: Surge, poll: tuple[float, float], dt: float, samples: int, seed: int = 1):
    """Students who arrive before release: how many there are, how many requests
    each sends before release, and when their first request after release falls
    (fractions per step). They poll every `poll` seconds, as in the generator."""
    h = 0.01
    edges, cum, total = [], [], 0.0
    t = -surge.pre_release_s
    while t < 0:
        total += surge.rate(t + h / 2) * h
        edges.append(t)
        cum.append(total)
        t += h
    if total <= 1e-12:
        return 0.0, 0.0, {}
    rng = random.Random(seed)
    lo, hi = poll
    hist: dict[int, float] = defaultdict(float)
    sent = 0
    for i in range(samples):
        j = min(bisect.bisect_left(cum, (i + 0.5) / samples * total), len(edges) - 1)
        t = edges[j]
        while t < 0:
            sent += 1
            t += max(rng.uniform(lo, hi) if hi > lo else lo, dt)
        hist[int(t / dt)] += 1.0 / samples
    return total, sent / samples, dict(hist)


def simulate(surge: Surge, users: Users, mu: float, eta: float = 1.0, dt: float = 0.25,
             deadlines=(2, 5, 10), drain_s: float = 90, queue_cap: float = 4096,
             keep_timeline: bool = False, workers: float = 256, order: str = "fifo",
             cancel_on_disconnect: bool = False, patience_classes: int = 10,
             prerelease_samples: int = 4000, other_cost: float = 0.0, room: Room | None = None) -> Result:
    """Run the fluid model from the first arrival until drain_s after arrivals stop.

    mu: answers per second the server finishes while it is busy.
    eta: extra share of mu lost under overload that the model does not explain
         (1.0, the default, means none). Kept to compare with earlier fits.
    workers, queue_cap: requests in service at once, and requests waiting for a worker.
    order: which waiting request a free worker takes: "fifo" (the oldest, as in
           rb portal) or "lifo" (the newest).
    cancel_on_disconnect: stop a started request when its student leaves instead
           of finishing it.
    other_cost: CPU of one rejected or dropped request, as a fraction of one
           answer's CPU; it is taken from the capacity in the step it happens.
    room: a waiting room in front of the server (None: students reach it directly).
    """
    if order not in ("fifo", "lifo"):
        raise ValueError(f"order must be fifo or lifo, not {order!r}")
    fifo = order == "fifo"
    lo, hi = users.patience
    nk = max(1, patience_classes) if hi > lo else 1
    patience = [lo + (k + 0.5) * (hi - lo) / nk for k in range(nk)] if nk > 1 else [lo]
    life = [max(1, round(p / dt)) for p in patience]

    def spread(rg) -> list[int]:
        a, b = rg
        n = max(1, min(8, int((b - a) / dt)))
        return [max(1, round((a + (j + 0.5) * (b - a) / n) / dt)) for j in range(n)]

    retry_steps = spread(users.retry_delay)
    repeat_steps = spread(users.repeat_after)
    # First-try times are kept to `bucket` steps so that retries of students
    # who started close together share one cohort.
    bucket = max(1, round(0.5 / dt))
    half = (bucket - 1) * dt / 2
    max_deadline = max(deadlines) if deadlines else 0.0

    per_s = max(1, round(1 / dt))
    # Pending requests per step, keyed by (patience class, first-try step, failures,
    # look-again, end of waiting-room admission, failures at which it ends).
    pending: dict[int, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
    room_q: deque[_Ticket] = deque()
    room_live = tokens = backend_requests = admitted = wasted_admissions = 0.0
    wait_hist: dict[int, float] = defaultdict(float)
    naive = room is not None and room.mode == "naive"
    if room is None:
        pre_users, pre_sent, first_hist = _prerelease(surge, users.prerelease_poll, dt, prerelease_samples)
        for st, frac in first_hist.items():
            for k in range(nk):
                pending[st][(k, st - st % bucket, 0, False, None, None)] += pre_users * frac / nk
        polls = pre_users * pre_sent
    else:
        # Students who arrive before release get a ticket and poll the room until
        # release; at release their tickets are at the head of the queue. With naive
        # tickets, some were lost by a manual refresh while waiting.
        pre_users = mean_wait = 0.0
        t, h = -surge.pre_release_s, 0.01
        while t < 0:
            x = surge.rate(t + h / 2) * h
            pre_users += x
            mean_wait += x * -(t + h / 2)
            t += h
        mean_wait = mean_wait / pre_users if pre_users else 0.0
        polls = pre_users * (1 + mean_wait / room.poll_s)
        lost = 1 - math.exp(-users.queue_manual_refresh_per_min / 60 * mean_wait) if naive else 0.0
        t0 = round(room.poll_s / 2 / dt)  # first poll after release
        if pre_users > 0:
            for k in range(nk):
                tk = _Ticket(pre_users / nk, k, t0 - t0 % bucket, 0, t0, 0)
                if lost:
                    tk.ghosts[-round(mean_wait / 2 / dt)] = pre_users / nk * lost
                room_q.append(tk)
            room_live = pre_users
    total_users = pre_users
    requests = polls
    served = completed = delivered = wasted = dropped = rejected = cancelled = late = gave_up = 0.0
    within = {d: 0.0 for d in deadlines}
    waiting: deque[_Cohort] = deque()
    service: deque[_Cohort] = deque()
    w_total = s_total = 0.0
    expiry: dict[int, list[_Cohort]] = defaultdict(list)
    timeline = []
    by_send: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    admit_steps = spread((0.0, room.poll_s)) if room is not None else []
    session_steps = round(room.session_s / dt) if room is not None else 0
    abandon_steps = round(room.abandon_s / dt) if room is not None else 0
    # Requests bound for the server that are still waiting in a saturated room:
    # step at which they reach the server -> (key..., amount, step they time out).
    delayed: dict[int, list] = defaultdict(list)
    room_delay = proxied_last = room_timeouts = 0.0
    retry_mean = sum(users.retry_delay) / 2

    def still_counts(first, s: int):
        return first if first is not None and (s - first) * dt - half <= max_deadline else None

    def join_room(s: int, k: int, first, failures: int, t0, amount: float) -> None:
        nonlocal room_live
        last = room_q[-1] if room_q else None
        if last is not None and last.created == s and (last.k, last.first, last.failures) == (k, first, failures):
            if t0 is not None and last.t0 is not None:
                last.t0 = (last.t0 * last.live + t0 * amount) / (last.live + amount)
            last.live += amount
        else:
            room_q.append(_Ticket(amount, k, first, failures, t0, s))
        room_live += amount

    def note(sent_step: int, outcome: str, amount: float) -> None:
        if keep_timeline:
            by_send[int(sent_step * dt)][outcome] += amount

    def fail(s: int, c: _Cohort, amount: float, timeout: bool) -> None:
        nonlocal gave_up
        if c.repeat or amount <= 1e-12:
            return  # a look-again request: nothing follows it
        failures = c.failures + 1
        if failures >= users.max_attempts:
            gave_up += amount
            return
        p = users.impatient_retry_prob if timeout else users.retry_prob
        gave_up += amount * (1 - p)
        if p <= 0:
            return
        share = amount * p / len(retry_steps)
        key = (c.k, still_counts(c.first, s), failures, False, c.session, c.cap)
        for j in retry_steps:
            pending[s + j][key] += share

    steps_end = int(round((surge.post_release_s + drain_s) / dt))
    overhead = 0.0  # rejected and dropped requests not yet paid for, in answers of CPU
    for s in range(steps_end):
        t = s * dt
        # 1. Requests sent in this step get a free worker, a place in the queue, or a 503.
        if room is not None and room.cpus > 0:
            # How long a request waits in the room in this step (see Room): queued
            # students poll less often while it is saturated, so the wait settles
            # where their polls and the passed-through requests use all its CPU.
            avail = room.cpus - room.cost_proxied * proxied_last / dt
            need = room.cost_queued * room_live / room.poll_s
            if avail <= 0:
                room_delay = room.max_delay_s
            elif need <= avail:
                room_delay = 0.0
            else:
                room_delay = min(room.max_delay_s, room.cost_queued * room_live / avail - room.poll_s)
        d_steps = round(room_delay / dt)
        proxied_now = 0.0
        arriving = []
        new = surge.rate(t) * dt
        if new > 0:
            total_users += new
            arriving += [(k, s - s % bucket, 0, False, None, None, new / nk) for k in range(nk)]
        arriving += [(*key, a) for key, a in pending.pop(s, {}).items()]
        to_server = list(delayed.pop(s, ()))  # requests that waited in the room until now
        for k, first, f, rep, sess, cap, a in arriving:
            requests += a
            if room is not None and not (sess is not None and s < sess and (cap is None or f < cap)):
                # Not admitted, or the admission has ended: the waiting room answers.
                if not rep:  # a look-again after the admission ended is not followed
                    join_room(s, k, first, f, s if (f == 0 and sess is None) else None, a)
                continue
            backend_requests += a
            note(s, "sent", a)
            expires = s + life[k]
            if room is not None:
                proxied_now += a
                if d_steps > 0:
                    if d_steps >= life[k]:
                        # The student's patience runs out while the request is still in the room.
                        room_timeouts += a
                        note(s, "timeout", a)
                        fail(expires, _Cohort(a, k, first, f, rep, expires, False, sess, cap), a, timeout=True)
                    else:
                        delayed[s + d_steps].append((k, first, f, rep, sess, cap, a, expires))
                    continue
            to_server.append((k, first, f, rep, sess, cap, a, expires))
        proxied_last = proxied_now
        fresh: list[_Cohort] = []  # this step's waiting requests; the queue limit is applied after step 2
        # Requests that arrive in the same step count as simultaneous: free workers
        # (and later queue places) are shared among them in proportion.
        arriving_total = sum(item[6] for item in to_server)
        start_share = min(1.0, max(0.0, workers - s_total) / arriving_total) if arriving_total > 1e-12 else 0.0
        for k, first, f, rep, sess, cap, a, expires in to_server:
            to_service = a * start_share
            to_wait = a - to_service
            if to_service > 1e-12:
                c = _Cohort(to_service, k, first, f, rep, expires, True, sess, cap, s)
                service.append(c)
                expiry[c.expires].append(c)
                s_total += to_service
            if to_wait > 1e-12:
                c = _Cohort(to_wait, k, first, f, rep, expires, False, sess, cap, s)
                waiting.append(c)
                expiry[c.expires].append(c)
                w_total += to_wait
                fresh.append(c)

        if room is not None and t >= 0:
            # Queued students poll the room, less often while it is saturated.
            requests += room_live * dt / (room.poll_s + room_delay)
            stuck = {k: min(1.0, (1 - users.impatient_retry_prob) / (patience[k] + retry_mean))
                     for k in range(nk) if patience[k] < room_delay}
            if s % per_s == 0 and room_live > 1e-9 and (naive or stuck):
                # With naive tickets, a manual refresh loses the ticket and the student
                # joins again at the back. In a saturated room, students whose patience
                # is shorter than the room's wait see their polls time out, and some give
                # up; their tickets stay behind until they are skipped.
                p = 1 - math.exp(-users.queue_manual_refresh_per_min / 60) if naive else 0.0
                moved: dict[tuple, list] = {}
                for tk in room_q:
                    if tk.live <= 1e-12:
                        continue
                    q = tk.live * stuck.get(tk.k, 0.0)
                    if q > 1e-12:
                        tk.live -= q
                        tk.ghosts[s] = tk.ghosts.get(s, 0.0) + q
                        gave_up += q
                        room_live -= q
                    x = tk.live * p
                    if x <= 1e-12:
                        continue
                    tk.live -= x
                    tk.ghosts[s] = tk.ghosts.get(s, 0.0) + x
                    key = (tk.k, still_counts(tk.first, s), tk.failures)
                    m = moved.setdefault(key, [0.0, 0.0, 0.0])
                    m[0] += x
                    if tk.t0 is not None:
                        m[1] += x * tk.t0
                        m[2] += x
                for (k, first, f), (x, t0w, wt) in moved.items():
                    room_q.append(_Ticket(x, k, first, f, t0w / wt if wt else None, s))
                    requests += x
            # Admissions at admit_rate, oldest ticket first. Lost tickets unseen for
            # abandon_s are skipped; younger ones use up an admission.
            tokens = min(room.admit_rate, tokens + room.admit_rate * dt)
            while tokens > 1e-12 and room_q:
                tk = room_q[0]
                young = 0.0
                for g in list(tk.ghosts):
                    if s - g > abandon_steps:
                        del tk.ghosts[g]
                    else:
                        young += tk.ghosts[g]
                total = tk.live + young
                if total <= 1e-12:
                    room_q.popleft()
                    continue
                x = min(tokens, total)
                frac = x / total
                adm = tk.live * frac
                tk.live -= adm
                for g in tk.ghosts:
                    tk.ghosts[g] *= 1 - frac
                tokens -= x
                admitted += x
                wasted_admissions += x - adm
                room_live -= adm
                if adm > 1e-12:
                    if tk.t0 is not None:
                        wait_hist[int(round((s - tk.t0) * dt))] += adm
                    sess = s + session_steps
                    sess -= sess % per_s
                    cap = tk.failures + room.request_cap if room.request_cap > 0 else None
                    key = (tk.k, still_counts(tk.first, s), tk.failures, False, sess, cap)
                    if tk.created == s:  # fast path: this very request goes through
                        pending[s + 1][key] += adm
                    else:  # the student learns of it at the next poll
                        for j in admit_steps:
                            pending[s + j][key] += adm / len(admit_steps)
                if frac >= 1 - 1e-12:
                    room_q.popleft()
            room_live = max(room_live, 0.0)

        # 2. The workers finish mu*dt answers, the earliest started first, less the
        #    CPU spent on rejected and dropped requests. Free workers then take
        #    waiting requests: the oldest (fifo) or the newest (lifo). Both repeat
        #    until this step's capacity is used, so that throughput is not capped
        #    at `workers` per step when dt is long.
        budget = mu * dt * (eta if w_total > 1e-9 else 1.0)
        paid = min(budget, overhead)
        budget -= paid
        overhead -= paid
        while True:
            while budget > 1e-12 and service:
                c = service[0]
                x = min(budget, c.amount)
                if x > 0:
                    c.amount -= x
                    s_total -= x
                    budget -= x
                    completed += x
                    if not c.live:
                        wasted += x
                    else:
                        delivered += x
                        note(c.expires - life[c.k], "correct", x)
                        if not c.repeat:
                            served += x
                            if c.first is not None:
                                age = (s - c.first) * dt - half
                                for d in deadlines:
                                    if age <= d + 1e-9:
                                        within[d] += x
                            if users.repeat_view_prob > 0:
                                share = x * users.repeat_view_prob / len(repeat_steps)
                                for j in repeat_steps:
                                    pending[s + j][(c.k, None, 0, True, c.session, c.cap)] += share
                if c.amount <= 1e-12:
                    service.popleft()

            free = workers - s_total
            moved = 0.0
            while free > 1e-12 and waiting:
                # The oldest (fifo) or newest (lifo) step's waiting requests, shared in proportion.
                while waiting and (waiting[0] if fifo else waiting[-1]).amount <= 1e-12:
                    waiting.popleft() if fifo else waiting.pop()
                if not waiting:
                    break
                step_of = (waiting[0] if fifo else waiting[-1]).entered
                group = []
                for c in (waiting if fifo else reversed(waiting)):
                    if c.entered != step_of:
                        break
                    if c.amount > 1e-12:
                        group.append(c)
                total = sum(c.amount for c in group)
                share = min(1.0, free / total)
                x_all = 0.0
                for c in group:
                    if share >= 1 - 1e-12:
                        x = c.amount
                        c.started = True
                        service.append(c)
                    else:
                        x = c.amount * share
                        c.amount -= x
                        part = _Cohort(x, c.k, c.first, c.failures, c.repeat, c.expires, True, c.session, c.cap,
                                       c.entered)
                        service.append(part)
                        expiry[part.expires].append(part)
                    x_all += x
                if share >= 1 - 1e-12:
                    # drop the started cohorts from the end they were taken from
                    while waiting and (waiting[0] if fifo else waiting[-1]).entered == step_of:
                        waiting.popleft() if fifo else waiting.pop()
                w_total -= x_all
                s_total += x_all
                free -= x_all
                moved += x_all
                if share < 1 - 1e-12:
                    break
            if budget <= 1e-12 or moved <= 1e-12:
                break

        # 3. Queue limit: what this step's arrivals left beyond queue_cap got a 503,
        #    shared in proportion among them (they arrived at the same time).
        excess = w_total - queue_cap
        if excess > 1e-12:
            left = [c for c in fresh if not c.started and c.amount > 1e-12]
            total = sum(c.amount for c in left)
            share = min(1.0, excess / total) if total > 1e-12 else 0.0
            for c in left:
                x = c.amount * share
                c.amount -= x
                w_total -= x
                rejected += x
                overhead += x * other_cost
                note(s, "rejected", x)
                fail(s, c, x, timeout=False)

        # 4. Time-outs: dropped if still waiting; finished for nobody if already started.
        for c in expiry.pop(s, ()):
            if c.amount <= 1e-12 or not c.live:
                continue
            a = c.amount
            note(s - life[c.k], "timeout", a)
            if not c.started:
                c.amount = 0.0
                w_total -= a
                dropped += a
                overhead += a * other_cost
            else:
                c.live = False
                late += a
                if cancel_on_disconnect:
                    c.amount = 0.0
                    s_total -= a
                    cancelled += a
            fail(s, c, a, timeout=True)
        w_total, s_total = max(w_total, 0.0), max(s_total, 0.0)

        if keep_timeline and s % per_s == 0:
            timeline.append({"t_s": t, "queue": w_total + s_total, "waiting": w_total, "in_service": s_total,
                             "arrivals_per_s": new / dt, "requests": requests, "completed": completed,
                             "delivered": delivered, "wasted": wasted, "dropped": dropped, "rejected": rejected,
                             "late": late, "served": served, "room_queued": room_live, "room_delay_s": room_delay,
                             "backend_requests": backend_requests})

    wait_p50 = math.nan
    total_wait = sum(wait_hist.values())
    if total_wait > 0:
        acc = 0.0
        for sec in sorted(wait_hist):
            acc += wait_hist[sec]
            if acc >= total_wait / 2:
                wait_p50 = float(sec)
                break
    if room is None:
        backend_requests = requests
    return Result(users=total_users, served=served, requests=requests,
                  success_within={f"{d:g}s": within[d] / total_users if total_users else 0 for d in deadlines},
                  timeline=timeline, polls=polls, completed=completed, delivered=delivered, wasted=wasted,
                  dropped=dropped, rejected=rejected, cancelled=cancelled, late=late, gave_up=gave_up,
                  by_send={s: dict(v) for s, v in sorted(by_send.items())}, backend_requests=backend_requests,
                  admitted=admitted, wasted_admissions=wasted_admissions, wait_p50_s=wait_p50,
                  still_queued=room_live, room_timeouts=room_timeouts)


def recovery_s(by_send: dict, rise_s: float, window: int = 10, threshold: float = 0.01) -> float:
    """Recovery time as analysis.stats.recovery measures it in the lab: the first
    second after the rise from which, for `window` seconds in a row, under
    `threshold` of the requests sent in each second fail. NaN if never."""
    secs = sorted(t for t in by_send if t >= rise_s)
    if not secs:
        return math.nan
    share = []
    for t in range(int(secs[0]), int(secs[-1]) + 1):
        b = by_send.get(t, {})
        sent = b.get("sent", 0.0)
        share.append((t, (b.get("timeout", 0.0) + b.get("rejected", 0.0)) / sent if sent > 1e-9 else 0.0))
    for i in range(len(share) - window + 1):
        if all(x < threshold for _, x in share[i:i + window]):
            return float(share[i][0])
    return math.nan


def from_scenario(path_or_dict, peak: float | None = None) -> tuple[Surge, Users]:
    sc = path_or_dict if isinstance(path_or_dict, dict) else yaml.safe_load(Path(path_or_dict).read_text())
    s = sc.get("surge", {})
    u = sc.get("users", {})
    surge = Surge(peak=float(peak or s.get("peak_users_per_s", 100)), pre_release_s=s.get("pre_release_s", 60),
                  start_frac=s.get("pre_release_start_frac", 0.02), end_frac=s.get("pre_release_end_frac", 0.2),
                  rise_s=s.get("rise_s", 5), decay_tau_s=s.get("decay_tau_s", 90), floor_frac=s.get("floor_frac", 0.02),
                  post_release_s=s.get("post_release_s", 300), shape=s.get("shape", "surge"))
    users = Users(patience=tuple(u.get("patience_s", (5, 20))), retry_prob=u.get("retry_prob", 0.8),
                  impatient_retry_prob=u.get("impatient_retry_prob", 0.9),
                  retry_delay=tuple(u.get("retry_delay_s", (1, 5))), max_attempts=u.get("max_attempts", 20),
                  prerelease_poll=tuple(u.get("prerelease_poll_s", (10, 30))),
                  repeat_view_prob=u.get("repeat_view_prob", 0.0),
                  repeat_after=tuple(u.get("repeat_after_s", (5, 20))),
                  queue_manual_refresh_per_min=u.get("queue_manual_refresh_per_min", 1.0))
    return surge, users


def _seconds(v, default: float) -> float:
    """'60s', '500ms' or a number of seconds."""
    if v is None or v == "":
        return default
    v = str(v)
    if v.endswith("ms"):
        return float(v[:-2]) / 1000
    if v.endswith("s"):
        return float(v[:-1])
    return float(v)


# -------------------------------------------------------------- validate ---

METRICS = ["served_ok", "success_2s", "success_5s", "success_10s", "amplification", "backend_amplification",
           "useful_share", "dropped_per_user", "rejected_per_user", "recovery_s", "wait_p50_s"]


def lab_runs(exp_dirs: list[Path], design: str) -> list[dict]:
    """Configuration and observed outcomes of every valid run of one design.

    "Answers built" are the 200 and 404 responses the portals finished (stats/portal*.json);
    "answers received" are the correct answers the generator recorded. Mirrors (design M)
    are summed; the model then simulates one mirror with its share of the load."""
    import pandas as pd

    from analysis import stats as lab_stats
    runs = []
    for exp in exp_dirs:
        for run in sorted(p for p in exp.iterdir() if p.is_dir()):
            sum_f, meta_f = run / "load" / "summary.json", run / "meta.json"
            portal_files = sorted((run / "stats").glob("portal*.json"))
            if not (sum_f.exists() and meta_f.exists() and portal_files):
                continue
            meta = json.loads(meta_f.read_text())
            if meta.get("design") != design:
                continue
            s = json.loads(sum_f.read_text())
            if s["generator"]["saturated"] or not s["users"]:
                continue
            portal: dict[str, float] = defaultdict(float)
            for f in portal_files:
                for k, v in json.loads(f.read_text()).items():
                    if isinstance(v, (int, float)):
                        portal[k] += v
            opts = meta.get("options", {})
            env = {**meta.get("env", {}), **(opts.get("env") or {})}
            cpu_s = sum(r.get("cpu_seconds", 0) for name, r in meta.get("resources", {}).items()
                        if name.startswith("portal"))
            built = portal["responses_200"] + portal["responses_404"]
            o = s["requests_by_outcome"]
            received = sum(o.get(k, 0) for k in ("correct", "correct_notfound", "stale", "ahead", "wrong", "missing"))
            n = s["users"]
            observed = {"served_ok": s["user_served_ok"], "amplification": s["amplification"],
                        "backend_amplification": s["backend_amplification"],
                        "useful_share": received / built if built else math.nan,
                        "dropped_per_user": portal["dropped_before_start"] / n,
                        "rejected_per_user": o.get("rejected", 0) / n}
            observed.update({f"success_{k}": v for k, v in s["user_success_within"].items()})
            ts_file = run / "load" / "timeseries.csv"
            observed["recovery_s"] = (lab_stats.recovery(pd.read_csv(ts_file), s["scenario"]["surge"].get("rise_s", 5))
                                      ["recovery_s"] if ts_file.exists() else math.nan)
            room = room_busy = None
            if "WR_ADMIT_RATE" in env:
                room = {"admit_rate": float(env["WR_ADMIT_RATE"]), "mode": env.get("WR_MODE", "token"),
                        "session_s": _seconds(env.get("WR_SESSION_TTL"), 60.0),
                        "abandon_s": _seconds(env.get("WR_ABANDON_AFTER"), 30.0),
                        "poll_s": _seconds(env.get("WR_POLL"), 5.0), "cpus": float(env.get("WR_CPUS", 0.25))}
                users_file = run / "load" / "users.csv.gz"
                if users_file.exists():
                    u = pd.read_csv(users_file, usecols=["arrival_ms", "admitted_ms", "first_try_ms"])
                    u = u[u.admitted_ms >= 0]
                    start = u.first_try_ms.where(u.first_try_ms >= 0, u.arrival_ms.clip(lower=0))
                    observed["wait_p50_s"] = float((u.admitted_ms - start).median() / 1000) if len(u) else math.nan
                room_busy = _room_busy(run, room["cpus"])
            runs.append({"experiment": exp.name, "run": run.name, "label": opts.get("label") or "",
                         "multiple": opts.get("multiple"), "page_cost": str(env.get("PAGE_COST", "5ms")),
                         "mirrors": len(portal_files), "cpus_per_portal": float(env.get("PORTAL_CPUS", 1.0)),
                         "workers": float(env.get("MAX_WORKERS", 256)), "queue_cap": float(env.get("MAX_QUEUE", 4096)),
                         "cpu_s": cpu_s, "answers": built, "other_requests": portal["requests"] - built,
                         "duration_s": (s["ended_unix_ms"] - s["started_unix_ms"]) / 1000,
                         "room": room, "room_busy": room_busy, "scenario": s["scenario"], "observed": observed})
    return runs


def _room_busy(run: Path, limit: float):
    """Mean requests per second that the waiting room answered itself (queued) and
    passed to the server, over the seconds its CPU was at the limit; None if never."""
    import pandas as pd
    res_f, req_f = run / "resources.csv", run / "load" / "requests.csv.gz"
    if not (res_f.exists() and req_f.exists()):
        return None
    res = pd.read_csv(res_f)
    r = res[res.service == "wr"].sort_values("t_ms")
    rate = r.cpu_seconds_total.diff() / (r.t_ms.diff() / 1000)
    busy = set((r.t_ms[rate >= 0.97 * limit] // 1000).astype(int))
    busy = {b for b in busy if b >= 0}
    if len(busy) < 10:
        return None
    q = pd.read_csv(req_f, usecols=["t_ms", "latency_ms", "outcome"])
    q = q.assign(sec=((q.t_ms + q.latency_ms) // 1000).astype(int))
    q = q[q.sec.isin(busy) & (q.outcome != "not_released")]
    queued = (q.outcome == "queued").sum() / len(busy)
    return {"queued_per_s": float(queued), "proxied_per_s": float(len(q) / len(busy) - queued), "cpus": limit}


def room_cpu_costs(runs: list[dict]) -> tuple[float, float] | None:
    """CPU-seconds per queued answer and per passed-through request of the waiting
    room, from runs in which it was saturated: limit = cost_q * queued/s + cost_p * proxied/s.
    None if fewer than two such runs."""
    import numpy as np
    pts = [r["room_busy"] for r in runs if r.get("room_busy")]
    if len(pts) < 2:
        return None
    X = np.array([[p["queued_per_s"], p["proxied_per_s"]] for p in pts], float)
    y = np.array([p["cpus"] for p in pts], float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return max(float(coef[0]), 1e-7), max(float(coef[1]), 1e-7)


def cpu_costs(runs: list[dict]) -> dict:
    """Least-squares split of the portals' CPU-seconds into a cost per answer
    (one per PAGE_COST), a cost per other request (rejected, dropped, not yet
    released) and a constant use per portal while the run lasts (runtime,
    metrics). Fitted to CPU accounting only, never to student outcomes."""
    import numpy as np
    costs = sorted({r["page_cost"] for r in runs})
    X = [[r["answers"] if r["page_cost"] == pc else 0.0 for pc in costs]
         + [r["other_requests"], r["duration_s"] * r["mirrors"]] for r in runs]
    coef, *_ = np.linalg.lstsq(np.array(X, float), np.array([r["cpu_s"] for r in runs], float), rcond=None)
    return {"answer": {pc: max(float(c), 1e-6) for pc, c in zip(costs, coef)},
            "other": max(float(coef[-2]), 0.0), "idle_cpus": max(float(coef[-1]), 0.0)}


def predict(run: dict, costs: dict, dt: float = 0.1, room_costs: tuple[float, float] | None = None) -> Result:
    """Predict one lab run from its configuration and the CPU costs."""
    sc = run["scenario"]
    surge, users = from_scenario(sc)
    surge.peak /= run["mirrors"]  # students pick a mirror at random and switch symmetrically
    answer = costs["answer"][run["page_cost"]]
    mu = max(run["cpus_per_portal"] - costs["idle_cpus"], 0.0) / answer
    room = None
    if run.get("room"):
        room = Room(**run["room"])
        if room_costs:
            room.cost_queued, room.cost_proxied = room_costs
    return simulate(surge, users, mu, dt=dt, drain_s=sc.get("generator", {}).get("drain_s", 45),
                    deadlines=tuple(sc.get("deadlines_s", (2, 5, 10))), workers=run["workers"],
                    queue_cap=run["queue_cap"], other_cost=costs["other"] / answer, keep_timeline=True, room=room)


def validate(runs: list[dict], dt: float = 0.1) -> list[dict]:
    """Predict every run. The CPU costs are fitted to the other runs, so no
    run's own measurement enters its prediction."""
    rows = []
    for i, r in enumerate(runs):
        others = [q for j, q in enumerate(runs) if j != i]
        if not any(q["page_cost"] == r["page_cost"] for q in others):
            continue
        costs = cpu_costs(others)
        room_costs = room_cpu_costs(others) if r.get("room") else None
        res = predict(r, costs, dt, room_costs)
        pred = {"served_ok": res.served_ok, "amplification": res.amplification,
                "backend_amplification": res.backend_amplification, "useful_share": res.useful_share,
                "dropped_per_user": res.dropped / res.users, "rejected_per_user": res.rejected / res.users,
                "wait_p50_s": res.wait_p50_s}
        pred.update({f"success_{k}": v for k, v in res.success_within.items()})
        pred["recovery_s"] = recovery_s(res.by_send, r["scenario"]["surge"].get("rise_s", 5))
        row = {k: r[k] for k in ("experiment", "run", "label", "multiple", "page_cost", "mirrors")}
        row["mu"] = max(r["cpus_per_portal"] - costs["idle_cpus"], 0.0) / costs["answer"][r["page_cost"]]
        row["cpu_ms_answer"] = costs["answer"][r["page_cost"]] * 1000
        row["cpu_ms_other"] = costs["other"] * 1000
        row["idle_cpus"] = costs["idle_cpus"]
        if room_costs:
            row["room_us_queued"], row["room_us_proxied"] = room_costs[0] * 1e6, room_costs[1] * 1e6
        for m in METRICS:
            row[f"obs_{m}"] = r["observed"].get(m, math.nan)
            row[f"pred_{m}"] = pred.get(m, math.nan)
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> str:
    """Mean of the repetitions per configuration, and the mean absolute error."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["experiment"], r["label"], r["multiple"], r["page_cost"], r["mirrors"])].append(r)
    shown = ["served_ok", "success_5s", "amplification", "useful_share", "recovery_s"]
    if any(not math.isnan(r["obs_wait_p50_s"]) for r in rows):  # waiting-room runs
        shown = ["served_ok", "success_10s", "backend_amplification", "useful_share", "wait_p50_s", "recovery_s"]
    head = "| experiment | label | x | page | mirrors | n | " + " | ".join(f"{m} obs / pred" for m in shown) + " |"
    lines = [head, "|" + "---|" * (6 + len(shown))]
    for key, rs in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        cells = []
        for m in shown:
            o = statistics.mean(r[f"obs_{m}"] for r in rs)
            p = statistics.mean(r[f"pred_{m}"] for r in rs)
            cells.append(f"{o:.3f} / {p:.3f}")
        lines.append("| " + " | ".join(str(x) for x in key) + f" | {len(rs)} | " + " | ".join(cells) + " |")
    lines.append("")
    for m in METRICS:
        errs = [abs(r[f"obs_{m}"] - r[f"pred_{m}"]) for r in rows
                if not (math.isnan(r[f"obs_{m}"]) or math.isnan(r[f"pred_{m}"]))]
        if errs:
            lines.append(f"{m}: mean absolute error {statistics.mean(errs):.3f}, largest {max(errs):.3f} ({len(errs)} runs)")
    agree = sum(math.isnan(r["obs_recovery_s"]) == math.isnan(r["pred_recovery_s"]) for r in rows)
    lines.append(f"recovered within the run or not: model agrees in {agree} of {len(rows)} runs")
    return "\n".join(lines)


# ------------------------------------------------------------------ plan ---

def required_capacity(surge: Surge, users: Users, target: float = 0.99, deadline: str = "5s", eta: float = 1.0,
                      dt: float = 1.0) -> float:
    """Smallest capacity (answers/s) for which `target` of students get a
    correct result within `deadline`."""
    lo, hi = 1.0, max(10.0, surge.peak * 4)
    while simulate(surge, users, hi, eta, dt=dt, drain_s=600).success_within[deadline] < target:
        hi *= 2
        if hi > 1e8:
            return math.inf
    for _ in range(30):
        mid = (lo + hi) / 2
        if simulate(surge, users, mid, eta, dt=dt, drain_s=600).success_within[deadline] >= target:
            hi = mid
        else:
            lo = mid
        if hi - lo < 0.01 * hi:
            break
    return hi


def plan(sizes, share_first_hour: float, tau_min: float, users: Users, cpu_costs: dict, eta: float,
         target: float, deadline: str) -> list[dict]:
    """Planning rows for real board sizes.

    The real-time surge: a share of all students checks within the first hour,
    arriving at release with an exponential decay of time constant tau_min.
    """
    rows = []
    tau = tau_min * 60
    for n in sizes:
        # Integral over the first hour of peak*exp(-t/tau) = peak*tau*(1-exp(-3600/tau)).
        peak = share_first_hour * n / (tau * (1 - math.exp(-3600 / tau)))
        surge = Surge(peak=peak, pre_release_s=600, start_frac=0.02, end_frac=0.2, rise_s=30,
                      decay_tau_s=tau, floor_frac=0.0, post_release_s=3600)
        mu = required_capacity(surge, users, target, deadline, eta)
        row = {"students": n, "peak_arrivals_per_s": round(peak, 1), "required_requests_per_s": round(mu, 1)}
        for design, cost in cpu_costs.items():
            row[f"cores_{design}"] = round(mu * cost, 2)
        rows.append(row)
    return rows


def cpu_costs_from_summary(path: Path, multiple: float = 1.0) -> dict:
    """CPU-seconds per served student for each design at a given load multiple,
    from analysis/report.py output (runs/core/report/summary.csv)."""
    import pandas as pd
    df = pd.read_csv(path)
    df = df[(df["multiple"] == multiple) & (df["label"].fillna("") == "")]
    return {r["design"]: r["cpu_s_per_1k_served"] / 1000 for _, r in df.iterrows()
            if not math.isnan(r.get("cpu_s_per_1k_served", math.nan))}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("simulate")
    s.add_argument("--scenario", required=True)
    s.add_argument("--capacity", type=float, required=True, help="answers/s the server finishes while busy")
    s.add_argument("--peak", type=float)
    s.add_argument("--eta", type=float, default=1.0)
    s.add_argument("--workers", type=float, default=256)
    s.add_argument("--queue", type=float, default=4096)
    s.add_argument("--order", choices=["fifo", "lifo"], default="fifo")
    s.add_argument("--cancel-on-disconnect", action="store_true")
    s.add_argument("--drain", type=float, help="seconds after arrivals stop (default: the scenario's drain_s)")
    v = sub.add_parser("validate")
    v.add_argument("experiments", nargs="+", type=Path)
    v.add_argument("--design", required=True)
    v.add_argument("--dt", type=float, default=0.1)
    v.add_argument("--out", type=Path, help="CSV with one row per run")
    pl = sub.add_parser("plan")
    pl.add_argument("--sizes", default="100000,500000,1000000,1500000,2500000")
    pl.add_argument("--share-first-hour", type=float, default=0.6)
    pl.add_argument("--tau-min", type=float, default=15)
    pl.add_argument("--eta", type=float, default=1.0)
    pl.add_argument("--target", type=float, default=0.99)
    pl.add_argument("--deadline", default="5s")
    pl.add_argument("--scenario", default=None, help="take the user-behaviour assumptions from this scenario")
    pl.add_argument("--cpu-costs", type=Path, help="runs/core/report/summary.csv")
    pl.add_argument("--out", type=Path)
    a = p.parse_args()

    if a.cmd == "simulate":
        sc = yaml.safe_load(Path(a.scenario).read_text())
        surge, users = from_scenario(sc, a.peak)
        drain = a.drain if a.drain is not None else sc.get("generator", {}).get("drain_s", 45)
        r = simulate(surge, users, a.capacity, a.eta, drain_s=drain, workers=a.workers, queue_cap=a.queue,
                     order=a.order, cancel_on_disconnect=a.cancel_on_disconnect)
        print(json.dumps({"users": round(r.users), "served_ok": round(r.served_ok, 4),
                          "amplification": round(r.amplification, 2), "useful_share": round(r.useful_share, 4),
                          "success_within": {k: round(v, 4) for k, v in r.success_within.items()},
                          "completed": round(r.completed), "wasted": round(r.wasted), "dropped": round(r.dropped),
                          "rejected": round(r.rejected)}, indent=2))
    elif a.cmd == "validate":
        rows = validate(lab_runs(a.experiments, a.design), a.dt)
        if not rows:
            raise SystemExit("no runs with portal statistics found")
        print(summarize(rows))
        if a.out:
            with a.out.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
                w.writeheader()
                w.writerows(rows)
    elif a.cmd == "plan":
        users = from_scenario(a.scenario)[1] if a.scenario else Users()
        costs = cpu_costs_from_summary(a.cpu_costs) if a.cpu_costs else {}
        rows = plan([int(x) for x in a.sizes.split(",")], a.share_first_hour, a.tau_min, users, costs, a.eta,
                    a.target, a.deadline)
        cols = list(rows[0].keys())
        md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        md += ["| " + " | ".join(f"{r[c]:,}" if isinstance(r[c], (int, float)) else str(r[c]) for c in cols) + " |"
               for r in rows]
        note = (f"\nAssumptions: {a.share_first_hour:.0%} of students check within the first hour, arrivals decay with "
                f"a {a.tau_min:g}-minute time constant, target {a.target:.0%} served correctly within {a.deadline}, "
                f"overload efficiency {a.eta}. Cores = required requests/s x measured CPU-seconds per served student.\n")
        text = "\n".join(md) + "\n" + note
        print(text)
        if a.out:
            a.out.write_text(text)


if __name__ == "__main__":
    main()
