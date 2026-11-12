"""Discrete-event simulator of the same server and students as model/capacity.py,
request by request: a second check on the fluid model.

Students arrive as a Poisson process following the surge curve. Each student
has one patience, drawn once, and every request times out after it:
- a request still waiting for a worker is dropped;
- one that a worker already took is finished anyway, unless
  cancel_on_disconnect is set.

After a 503 or a time-out, a student refreshes with some probability after a
random pause, and gives up after max_attempts failures. Students who arrive
before release poll until release, and some look again after their result.

The server has `workers` slots and a queue of `queue_cap` (fifo or lifo).
How the CPU serves the requests that hold a worker is set by `service`:
- "fifo": one after another in the order they started, 1/mu each. This is
  close to Go's run queue, where a 5 ms page rarely gets preempted.
- "ps": processor sharing, every started request progressing at mu/n.
- "random": one after another like "fifo", but the next one is picked at
  random among the started requests, as when the database pool and the Go
  scheduler do not keep start order.

    python -m model.des --scenario bench/scenarios/paper.yaml --capacity 200 --peak 447 --seed 1
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import random
from collections import defaultdict, deque
from pathlib import Path

import yaml

from model.capacity import Result, Surge, Users, from_scenario


class _Student:
    __slots__ = ("patience", "failures", "first", "done")

    def __init__(self, patience: float):
        self.patience = patience
        self.failures = 0
        self.first = None   # time of the first request after release
        self.done = False


class _Req:
    __slots__ = ("st", "sent", "repeat", "state", "live", "finish_v")

    def __init__(self, st: _Student, sent: float, repeat: bool):
        self.st = st
        self.sent = sent
        self.repeat = repeat
        self.state = 0      # 0 waiting, 1 in service, 2 finished or dropped
        self.live = True    # the student is still waiting for this answer
        self.finish_v = 0.0


def simulate_des(surge: Surge, users: Users, mu: float, deadlines=(2, 5, 10), drain_s: float = 45,
                 queue_cap: int = 4096, workers: int = 256, order: str = "fifo", service: str = "fifo",
                 cancel_on_disconnect: bool = False, other_cost: float = 0.0, seed: int = 1,
                 keep_timeline: bool = False) -> Result:
    if order not in ("fifo", "lifo") or service not in ("fifo", "ps", "random"):
        raise ValueError("order must be fifo|lifo and service fifo|ps|random")
    shuffle = service == "random"
    if shuffle:
        service = "fifo"  # same machinery; the next request on the CPU is picked at random
    rng = random.Random(seed)
    t_end = surge.post_release_s + drain_s
    ev: list = []
    seq = 0

    def push(t: float, kind: str, obj=None, extra=None) -> None:
        nonlocal seq
        if t <= t_end:
            seq += 1
            heapq.heappush(ev, (t, seq, kind, obj, extra))

    # Arrivals: Poisson process with rate surge.rate(t), by thinning.
    peak = max(surge.peak, 1e-9)
    t = -surge.pre_release_s if surge.shape != "constant" else 0.0
    n_users = 0
    while True:
        t += rng.expovariate(peak)
        if t > surge.post_release_s:
            break
        if rng.random() * peak <= surge.rate(t):
            n_users += 1
            push(t, "arrive")

    c = dict(served=0.0, requests=0.0, polls=0.0, completed=0.0, delivered=0.0, wasted=0.0, dropped=0.0,
             rejected=0.0, cancelled=0.0, late=0.0, gave_up=0.0)
    within = {d: 0 for d in deadlines}
    by_send: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    waiting: deque[_Req] = deque()
    n_wait = 0
    in_service: deque[_Req] = deque()  # "fifo" service: start order; the head is on the CPU
    head_done = None                   # "fifo": time the head finishes
    tax = 0.0                          # CPU owed for rejected and dropped requests, in answers
    # "ps": virtual time, heap of finishing virtual times, version of the next completion event
    v_now, v_last, ps_heap, ps_n, ps_version = 0.0, 0.0, [], 0, 0

    def note(sent: float, outcome: str) -> None:
        if keep_timeline:
            by_send[math.floor(sent)][outcome] += 1

    def uniform(rg) -> float:
        return rng.uniform(rg[0], rg[1]) if rg[1] > rg[0] else rg[0]

    def fail(now: float, r: _Req, timeout: bool) -> None:
        st = r.st
        if r.repeat or st.done:
            return
        st.failures += 1
        if st.failures >= users.max_attempts:
            c["gave_up"] += 1
            st.done = True
            return
        p = users.impatient_retry_prob if timeout else users.retry_prob
        if rng.random() < p:
            push(now + uniform(users.retry_delay), "send", st, False)
        else:
            c["gave_up"] += 1
            st.done = True

    def ps_advance(now: float) -> None:
        nonlocal v_now, v_last
        if ps_n > 0:
            v_now += (now - v_last) * mu / ps_n
        v_last = now

    def ps_schedule(now: float) -> None:
        nonlocal ps_version
        ps_version += 1
        while ps_heap and ps_heap[0][2].state != 1:
            heapq.heappop(ps_heap)
        if ps_heap:
            fv = ps_heap[0][0]
            push(now + max(0.0, fv - v_now) * ps_n / mu, "ps_done", None, ps_version)

    def start(now: float, r: _Req) -> None:
        nonlocal head_done, ps_n
        r.state = 1
        if service == "fifo":
            in_service.append(r)
            if len(in_service) == 1:
                head_done = now + 1.0 / mu
                push(head_done, "fifo_done", r)
        else:
            ps_advance(now)
            ps_n += 1
            r.finish_v = v_now + 1.0
            heapq.heappush(ps_heap, (r.finish_v, id(r), r))
            ps_schedule(now)

    def busy() -> int:
        return len(in_service) if service == "fifo" else ps_n

    def next_head(now: float) -> None:
        """Put the next started request on the CPU ("random": any of them)."""
        nonlocal head_done, tax
        if not in_service:
            return
        if shuffle and len(in_service) > 1:
            i = rng.randrange(len(in_service))
            in_service[0], in_service[i] = in_service[i], in_service[0]
        head_done = now + (1.0 + tax) / mu
        tax = 0.0
        push(head_done, "fifo_done", in_service[0])

    def finish(now: float, r: _Req) -> None:
        """r's answer is ready."""
        r.state = 2
        c["completed"] += 1
        if not r.live:
            c["wasted"] += 1
            return
        c["delivered"] += 1
        note(r.sent, "correct")
        st = r.st
        if r.repeat or st.done:
            return
        st.done = True
        c["served"] += 1
        if st.first is not None:
            for d in deadlines:
                if now - st.first <= d + 1e-9:
                    within[d] += 1
        if users.repeat_view_prob > 0 and rng.random() < users.repeat_view_prob:
            push(now + uniform(users.repeat_after), "send", st, True)

    def take_next(now: float) -> None:
        """A worker is free: give it the oldest (fifo) or newest (lifo) live waiting request."""
        nonlocal n_wait
        while busy() < workers and n_wait > 0:
            r = waiting.popleft() if order == "fifo" else waiting.pop()
            if r.state != 0:
                continue
            n_wait -= 1
            start(now, r)

    while ev:
        now, _, kind, obj, extra = heapq.heappop(ev)
        if kind == "arrive":
            st = _Student(uniform(users.patience))
            if now < 0:
                # Before release: "not released" answers until the first poll after release.
                t_poll = now
                while t_poll < 0:
                    c["polls"] += 1
                    c["requests"] += 1
                    t_poll += max(uniform(users.prerelease_poll), 0.01)
                push(t_poll, "send", st, False)
            else:
                push(now, "send", st, False)
        elif kind == "send":
            st, repeat = obj, extra
            if st.done and not repeat:
                continue
            if st.first is None and not repeat:
                st.first = now
            r = _Req(st, now, repeat)
            c["requests"] += 1
            note(now, "sent")
            if busy() < workers and n_wait == 0:
                start(now, r)
            elif queue_cap <= 0 or n_wait < queue_cap:
                waiting.append(r)
                n_wait += 1
            else:
                r.state = 2
                c["rejected"] += 1
                tax += other_cost
                note(now, "rejected")
                fail(now, r, timeout=False)
                continue
            push(now + st.patience, "timeout", r)
        elif kind == "timeout":
            r = obj
            if r.state == 2:
                continue
            r.live = False
            note(r.sent, "timeout")
            if r.state == 0:
                r.state = 2
                n_wait -= 1
                c["dropped"] += 1
                tax += other_cost
            else:
                c["late"] += 1
                if cancel_on_disconnect:
                    c["cancelled"] += 1
                    if service == "fifo":
                        if in_service and in_service[0] is r:
                            # the head is on the CPU: stop it and start the next one
                            in_service.popleft()
                            r.state = 2
                            next_head(now)
                        else:
                            in_service.remove(r)
                            r.state = 2
                    else:
                        ps_advance(now)
                        r.state = 2
                        ps_n -= 1
                        ps_schedule(now)
                    take_next(now)
            fail(now, r, timeout=True)
        elif kind == "fifo_done":
            r = obj
            if not in_service or in_service[0] is not r or r.state != 1:
                continue  # stale: the head was cancelled
            in_service.popleft()
            finish(now, r)
            take_next(now)
            if in_service and in_service[0].state == 1 and (head_done is None or head_done <= now):
                next_head(now)
        elif kind == "ps_done":
            if extra != ps_version:
                continue
            ps_advance(now)
            while ps_heap and ps_heap[0][2].state != 1:
                heapq.heappop(ps_heap)
            if ps_heap:
                _, _, r = heapq.heappop(ps_heap)
                ps_n -= 1
                finish(now, r)
            take_next(now)
            ps_schedule(now)

    return Result(users=n_users, served=c["served"], requests=c["requests"],
                  success_within={f"{d:g}s": within[d] / n_users if n_users else 0 for d in deadlines},
                  polls=c["polls"], completed=c["completed"], delivered=c["delivered"], wasted=c["wasted"],
                  dropped=c["dropped"], rejected=c["rejected"], cancelled=c["cancelled"], late=c["late"],
                  gave_up=c["gave_up"], by_send={s: dict(v) for s, v in sorted(by_send.items())},
                  backend_requests=c["requests"] - c["polls"])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenario", required=True)
    p.add_argument("--capacity", type=float, required=True, help="answers/s the server finishes while busy")
    p.add_argument("--peak", type=float)
    p.add_argument("--workers", type=int, default=256)
    p.add_argument("--queue", type=int, default=4096)
    p.add_argument("--order", choices=["fifo", "lifo"], default="fifo")
    p.add_argument("--service", choices=["fifo", "ps"], default="fifo")
    p.add_argument("--cancel-on-disconnect", action="store_true")
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args()
    sc = yaml.safe_load(Path(a.scenario).read_text())
    surge, users = from_scenario(sc, a.peak)
    r = simulate_des(surge, users, a.capacity, drain_s=sc.get("generator", {}).get("drain_s", 45), workers=a.workers,
                     queue_cap=a.queue, order=a.order, service=a.service, cancel_on_disconnect=a.cancel_on_disconnect,
                     seed=a.seed)
    print(json.dumps({"users": r.users, "served_ok": round(r.served_ok, 4), "amplification": round(r.amplification, 2),
                      "useful_share": round(r.useful_share, 4),
                      "success_within": {k: round(v, 4) for k, v in r.success_within.items()}}, indent=2))


if __name__ == "__main__":
    main()
