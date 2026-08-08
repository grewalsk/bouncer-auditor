"""A minimal trained-controller case study for the MLForSys workshop paper.

The controller is an offline-trained, PC-conditioned cache-insertion policy.  A
logistic model learns whether a newly referenced line will be reused within a
short horizon.  At deployment it inserts predicted-reusable lines and bypasses
predicted-streaming lines; the safe fallback is ordinary LRU, which inserts
every miss.

The experiment deliberately isolates *concept shift*: the marginal distribution
of the four PC classes is unchanged, while their reuse meaning reverses halfway
through the run.  Thus a PC-histogram OOD monitor remains silent even though the
learned controller becomes worse than LRU.  Bouncer uses fixed leader
sets (the stateful-controller-safe configuration) and gates follower sets after
the measured learned-minus-LRU hit-rate advantage turns negative.

This is controlled trace-replay evidence, not a claim about a production cache
controller or end-to-end IPC.  The existing ChampSim experiments remain the
real-simulator boundary study.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Dict, Iterable, List, Tuple

import numpy as np
import matplotlib.pyplot as plt

from bouncer.cusum import LowerCusum
from experiments import workshop_common as C


# Two-sided 95% Student-t critical value for the 12 deployment seeds (11 d.f.).
# The experiment intentionally avoids a SciPy dependency for this single value.
T95_DF11 = 2.200985


@dataclass(frozen=True)
class Config:
    n_sets: int = 64
    ways: int = 8
    accesses_per_set_window: int = 64
    hot_lines: int = 4
    windows: int = 60
    shift_window: int = 30
    n_learned_leaders: int = 8
    n_fallback_leaders: int = 8
    train_examples: int = 20000
    validation_examples: int = 5000
    train_seed: int = 2026
    evaluation_seeds: int = 12
    cusum_K: float = 0.02
    cusum_H: float = 0.12


class LogisticInsertionPolicy:
    """Four-PC logistic reuse classifier trained with full-batch gradient descent."""

    def __init__(self, n_pc: int = 4):
        self.n_pc = n_pc
        self.w = np.zeros(n_pc + 1, dtype=float)  # intercept + one-hot PC

    def features(self, pc: np.ndarray) -> np.ndarray:
        pc = np.asarray(pc, dtype=int)
        X = np.zeros((pc.size, self.n_pc + 1), dtype=float)
        X[:, 0] = 1.0
        X[np.arange(pc.size), pc + 1] = 1.0
        return X

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        z = np.clip(z, -30.0, 30.0)
        return 1.0 / (1.0 + np.exp(-z))

    def fit(self, pc: np.ndarray, reused: np.ndarray, *, steps: int = 800,
            learning_rate: float = 0.4, l2: float = 1e-3) -> None:
        X = self.features(pc)
        y = np.asarray(reused, dtype=float)
        for _ in range(steps):
            p = self._sigmoid(X @ self.w)
            grad = (X.T @ (p - y)) / y.size
            grad[1:] += l2 * self.w[1:]
            self.w -= learning_rate * grad

    def probability(self, pc: np.ndarray | int) -> np.ndarray | float:
        a = np.asarray([pc] if np.isscalar(pc) else pc, dtype=int)
        out = self._sigmoid(self.features(a) @ self.w)
        return float(out[0]) if np.isscalar(pc) else out

    def insert(self, pc: int) -> bool:
        return bool(self.probability(pc) >= 0.5)


class SetCache:
    """Small true-LRU cache; insertion can be bypassed by the learned policy."""

    def __init__(self, ways: int):
        self.ways = ways
        self.lines: List[int] = []  # LRU at index 0, MRU at the end

    def access(self, tag: int, insert: bool) -> int:
        if tag in self.lines:
            self.lines.remove(tag)
            self.lines.append(tag)
            return 1
        if insert:
            if len(self.lines) >= self.ways:
                self.lines.pop(0)
            self.lines.append(tag)
        return 0


def make_training_data(cfg: Config) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Derive future-reuse labels from two seeded training-domain traces.

    Half of the references draw from a small recurring working set and half are
    one-shot stream lines.  PCs 0/1 usually generate recurring lines and PCs 2/3
    usually generate stream lines; three percent cross the association.  A label
    is one exactly when the same tag occurs within the next 64 references.  The
    validation trace is generated independently rather than split by access.
    """
    def labeled_trace(n: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(seed)
        recurrent = np.arange(n) % 2 == 0
        rng.shuffle(recurrent)
        tags = np.empty(n, dtype=np.int64)
        pc = np.empty(n, dtype=int)
        stream_tag = 1_000_000
        for i, hot in enumerate(recurrent):
            crossed = bool(rng.random() < 0.03)
            if hot:
                tags[i] = int(rng.integers(0, 8))
                pc[i] = int(rng.choice((2, 3) if crossed else (0, 1)))
            else:
                tags[i] = stream_tag
                stream_tag += 1
                pc[i] = int(rng.choice((0, 1) if crossed else (2, 3)))

        reused = np.zeros(n, dtype=int)
        next_position: Dict[int, int] = {}
        for i in range(n - 1, -1, -1):
            tag = int(tags[i])
            if tag in next_position and next_position[tag] - i <= 64:
                reused[i] = 1
            next_position[tag] = i
        return pc, reused

    pc_tr, y_tr = labeled_trace(cfg.train_examples, cfg.train_seed)
    pc_va, y_va = labeled_trace(cfg.validation_examples, cfg.train_seed + 1)
    return pc_tr, y_tr, pc_va, y_va


def make_set_window(cfg: Config, window: int, set_id: int,
                    shifted: bool, rng: np.random.Generator) -> List[Tuple[int, int]]:
    """Return ``(tag, pc)`` accesses with an exactly uniform PC histogram.

    Half the accesses revisit four hot lines; half are one-shot stream lines.
    The PC/reuse association reverses after the shift, but every set-window has
    exactly 16 occurrences of each PC at the default 64-access window.  Tags
    rotate each window so a controller
    must make a fresh insertion decision rather than coasting on warm state.
    """
    m = cfg.accesses_per_set_window
    assert m % 8 == 0 and (m // 2) % cfg.hot_lines == 0
    half = m // 2
    per_hot = half // cfg.hot_lines
    assert per_hot % 2 == 0, "each hot line must balance its two PC classes"
    base = (window + 1) * 10_000 + set_id * 100
    hot_pcs = (2, 3) if shifted else (0, 1)
    stream_pcs = (0, 1) if shifted else (2, 3)

    accesses: List[Tuple[int, int]] = []
    for h in range(cfg.hot_lines):
        tag = base + h
        for j in range(per_hot):
            accesses.append((tag, hot_pcs[j % 2]))
    for j in range(half):
        tag = 1_000_000_000 + base * m + j
        accesses.append((tag, stream_pcs[j % 2]))
    rng.shuffle(accesses)
    counts = np.bincount([pc for _, pc in accesses], minlength=4)
    assert np.all(counts == m // 4), counts
    return accesses


def _route(policy: str, model: LogisticInsertionPolicy, pc: int) -> bool:
    if policy == "learned":
        return model.insert(pc)
    if policy == "fallback":
        return True
    raise ValueError(policy)


def simulate(cfg: Config, model: LogisticInsertionPolicy, seed: int,
             mode: str, *, post_shift_severity: float = 1.0,
             ramp_windows: int = 0, psel_bits: int = 10,
             shift_order: np.ndarray | None = None) -> Dict[str, object]:
    """Simulate pure learned, pure LRU, Bouncer, or a PSEL reference.

    ``post_shift_severity`` is the fraction of sets whose PC/reuse meaning is
    reversed.  Every set-window remains exactly PC-marginal invariant.  A fixed
    independently seeded ordering makes severities nested without coupling the
    workload to the leader assignment.  ``ramp_windows`` linearly increases the
    affected fraction after the nominal change point.

    The PSEL mode is an architectural reference, not a safety-calibrated
    competitor: its signed saturating counter accumulates leader hit-count
    differences and followers obey the sign.
    """
    if not 0.0 <= post_shift_severity <= 1.0:
        raise ValueError("post_shift_severity must lie in [0, 1]")
    if mode not in {"learned", "fallback", "bouncer", "psel"}:
        raise ValueError(mode)
    rng = np.random.default_rng(seed)
    caches = [SetCache(cfg.ways) for _ in range(cfg.n_sets)]

    perm = rng.permutation(cfg.n_sets)
    learned_leaders = set(int(x) for x in perm[:cfg.n_learned_leaders])
    fallback_leaders = set(int(x) for x in perm[
        cfg.n_learned_leaders:cfg.n_learned_leaders + cfg.n_fallback_leaders])
    followers = set(range(cfg.n_sets)) - learned_leaders - fallback_leaders

    if shift_order is None:
        shift_order = np.random.default_rng(seed + 1_000_003).permutation(cfg.n_sets)
    else:
        shift_order = np.asarray(shift_order, dtype=int)
        if sorted(shift_order.tolist()) != list(range(cfg.n_sets)):
            raise ValueError("shift_order must be a permutation of set IDs")

    insert_by_pc = tuple(model.insert(pc) for pc in range(model.n_pc))

    detector = LowerCusum(K=cfg.cusum_K, H=cfg.cusum_H, auto_reset=False)
    gate_open = True
    gate_window = None
    psel_limit = (1 << (psel_bits - 1)) - 1
    psel_score = 0
    hit_rate: List[float] = []
    per_set_hit_rate: List[List[float]] = []
    delta_hat: List[float] = []
    gate_trace: List[int] = []
    pc_tv: List[float] = []
    severity_trace: List[float] = []
    psel_trace: List[int] = []

    for w in range(cfg.windows):
        if w < cfg.shift_window:
            severity = 0.0
        elif ramp_windows > 0:
            progress = min(1.0, (w - cfg.shift_window + 1) / ramp_windows)
            severity = post_shift_severity * progress
        else:
            severity = post_shift_severity
        n_shifted = int(round(severity * cfg.n_sets))
        shifted_sets = set(int(x) for x in shift_order[:n_shifted])
        severity_trace.append(n_shifted / cfg.n_sets)

        per_set_hits = np.zeros(cfg.n_sets, dtype=float)
        pc_counts = np.zeros(4, dtype=int)
        for s in range(cfg.n_sets):
            if mode == "learned":
                policy = "learned"
            elif mode == "fallback":
                policy = "fallback"
            elif s in learned_leaders:
                policy = "learned"
            elif s in fallback_leaders:
                policy = "fallback"
            else:
                policy = "learned" if gate_open else "fallback"

            accesses = make_set_window(cfg, w, s, s in shifted_sets, rng)
            for tag, pc in accesses:
                pc_counts[pc] += 1
                insert = insert_by_pc[pc] if policy == "learned" else True
                per_set_hits[s] += caches[s].access(tag, insert)

        rates = per_set_hits / cfg.accesses_per_set_window
        hit_rate.append(float(np.mean(rates)))
        per_set_hit_rate.append(rates.tolist())
        pc_dist = pc_counts / np.sum(pc_counts)
        pc_tv.append(float(0.5 * np.sum(np.abs(pc_dist - 0.25))))

        if mode in {"bouncer", "psel"}:
            d = float(np.mean(rates[list(learned_leaders)]) -
                      np.mean(rates[list(fallback_leaders)]))
            delta_hat.append(d)
            if mode == "bouncer":
                if gate_open and detector.update(d):
                    gate_open = False  # routing changes on the next window
                    gate_window = w + 1
            else:
                # Equal leader-pool sizes and equal decisions/set make this the
                # signed hit-count form of DIP's miss-updated PSEL counter.
                update = int(round(np.sum(per_set_hits[list(learned_leaders)]) -
                                   np.sum(per_set_hits[list(fallback_leaders)])))
                psel_score = int(np.clip(psel_score + update, -psel_limit - 1, psel_limit))
                next_gate_open = psel_score >= 0
                if gate_open and not next_gate_open and gate_window is None:
                    gate_window = w + 1
                gate_open = next_gate_open
            gate_trace.append(int(gate_open))
        else:
            delta_hat.append(float("nan"))
            gate_trace.append(int(mode == "learned"))
        psel_trace.append(psel_score)

    return dict(hit_rate=hit_rate, delta_hat=delta_hat, gate_open=gate_trace,
                pc_tv=pc_tv, gate_window=gate_window,
                per_set_hit_rate=per_set_hit_rate,
                learned_leaders=sorted(learned_leaders),
                fallback_leaders=sorted(fallback_leaders),
                followers=sorted(followers), severity=severity_trace,
                psel_score=psel_trace)


def ci95(values: Iterable[float]) -> Tuple[float, float, float]:
    a = np.asarray(list(values), dtype=float)
    mean = float(np.mean(a))
    if a.size != 12:
        raise ValueError("The released Student-t interval is defined for 12 seeds")
    half = float(T95_DF11 * np.std(a, ddof=1) / np.sqrt(a.size))
    return mean, mean - half, mean + half


def span_mean(a: np.ndarray, start: int, stop: int) -> float:
    return float(np.mean(a[start:stop]))


def main() -> None:
    cfg = Config()
    C.setstyle()

    pc_tr, y_tr, pc_va, y_va = make_training_data(cfg)
    model = LogisticInsertionPolicy()
    model.fit(pc_tr, y_tr)
    p_va = np.asarray(model.probability(pc_va))
    val_accuracy = float(np.mean((p_va >= 0.5) == y_va))
    val_positive_rate = float(np.mean(y_va))
    val_majority_accuracy = max(val_positive_rate, 1.0 - val_positive_rate)
    val_logloss = float(-np.mean(y_va * np.log(p_va + 1e-12) +
                                     (1 - y_va) * np.log(1 - p_va + 1e-12)))

    runs: Dict[str, List[Dict[str, object]]] = {k: [] for k in ("learned", "fallback", "bouncer")}
    for i in range(cfg.evaluation_seeds):
        seed = 10_000 + i
        for mode in runs:
            runs[mode].append(simulate(cfg, model, seed, mode))

    curves = {mode: np.asarray([r["hit_rate"] for r in rs], dtype=float)
              for mode, rs in runs.items()}
    per_set_curves = {
        mode: np.asarray([r["per_set_hit_rate"] for r in rs], dtype=float)
        for mode, rs in runs.items()
    }
    b_dhat = np.asarray([r["delta_hat"] for r in runs["bouncer"]], dtype=float)
    gate_windows = np.asarray([r["gate_window"] for r in runs["bouncer"]], dtype=float)
    delays = gate_windows - cfg.shift_window
    max_pc_tv = max(float(np.max(r["pc_tv"])) for r in runs["bouncer"])

    # Exclude the first five windows of each regime to remove cold-start and
    # gate-transition effects from steady summaries.
    pre = slice(5, cfg.shift_window)
    post = slice(cfg.shift_window + 5, cfg.windows)
    pre_seed = {mode: np.mean(a[:, pre], axis=1) for mode, a in curves.items()}
    post_seed = {mode: np.mean(a[:, post], axis=1) for mode, a in curves.items()}
    clean_retained = ((pre_seed["bouncer"] - pre_seed["fallback"]) /
                      (pre_seed["learned"] - pre_seed["fallback"]))
    loss_recovered = ((post_seed["bouncer"] - post_seed["learned"]) /
                      (post_seed["fallback"] - post_seed["learned"]))

    # Shadow potential outcomes are available only because this is a simulator.
    # They audit the causal estimand without entering the online detector.
    follower_delta = np.zeros_like(b_dhat)
    for i, run in enumerate(runs["bouncer"]):
        followers = np.asarray(run["followers"], dtype=int)
        follower_delta[i] = np.mean(
            per_set_curves["learned"][i, :, followers]
            - per_set_curves["fallback"][i, :, followers], axis=0
        )
    estimator_bias = b_dhat - follower_delta

    confidence_by_pc = np.abs(
        np.asarray([model.probability(i) for i in range(model.n_pc)]) - 0.5
    )
    confidence_mean = float(np.mean(confidence_by_pc))
    designed_clean_retention = 1.0 - cfg.n_fallback_leaders / cfg.n_sets
    designed_shift_recovery = 1.0 - cfg.n_learned_leaders / cfg.n_sets

    summary = dict(
        scope=("Seeded set-associative trace replay with an offline-trained four-PC logistic "
               "insertion controller; controlled concept shift, not ChampSim or end-to-end IPC."),
        config=cfg.__dict__,
        model=dict(weights=model.w.tolist(), reuse_probability_by_pc=[model.probability(i) for i in range(4)],
                   validation_accuracy=val_accuracy,
                   validation_majority_accuracy=val_majority_accuracy,
                   validation_positive_rate=val_positive_rate,
                   validation_logloss=val_logloss),
        uncertainty=dict(method="two-sided 95% Student-t intervals across deployment seeds",
                         deployment_seeds=cfg.evaluation_seeds,
                         degrees_of_freedom=cfg.evaluation_seeds - 1,
                         critical_value=T95_DF11),
        pc_marginal=dict(reference=[0.25] * 4, max_total_variation=max_pc_tv,
                         input_ood_alarms=0,
                         note="Each set-window has exactly 25% of every PC before and after shift."),
        model_confidence_monitor=dict(
            absolute_margin_by_pc=confidence_by_pc.tolist(),
            mean_absolute_margin_pre=confidence_mean,
            mean_absolute_margin_post=confidence_mean,
            distribution_total_variation=0.0,
            alarms=0,
            note=("The PC histogram is unchanged exactly, so every deterministic function "
                  "of PC alone, including the model's confidence distribution, is unchanged.")),
        steady_hit_rate=dict(
            pre_shift={mode: dict(zip(("mean", "ci95_low", "ci95_high"), ci95(v)))
                       for mode, v in pre_seed.items()},
            post_shift={mode: dict(zip(("mean", "ci95_low", "ci95_high"), ci95(v)))
                        for mode, v in post_seed.items()}),
        detection=dict(gate_window_mean=float(np.mean(gate_windows)),
                       delay_windows_mean=float(np.mean(delays)),
                       delay_windows_min=int(np.min(delays)), delay_windows_max=int(np.max(delays)),
                       detected_seeds=int(np.sum(np.isfinite(gate_windows))),
                       total_seeds=cfg.evaluation_seeds,
                       pre_shift_false_alarms=int(np.sum(gate_windows < cfg.shift_window))),
        utility=dict(
            designed_clean_gain_retention=designed_clean_retention,
            designed_shift_loss_recovery=designed_shift_recovery,
            note=("These 7/8 values are allocation ceilings in expectation: one fallback "
                  "leader arm remains exposed before gating and one learned leader arm "
                  "remains exposed after gating. Seed variation comes from which sets are leaders."),
            clean_learned_gain_retained=dict(zip(("mean", "ci95_low", "ci95_high"), ci95(clean_retained))),
            shifted_fallback_loss_recovered=dict(zip(("mean", "ci95_low", "ci95_high"), ci95(loss_recovered)))),
        estimator_audit=dict(
            estimand="shadow learned-minus-fallback advantage on follower sets",
            mean_bias_all=float(np.mean(estimator_bias)),
            rmse_all=float(np.sqrt(np.mean(estimator_bias ** 2))),
            mean_bias_pre=float(np.mean(estimator_bias[:, pre])),
            mean_bias_post=float(np.mean(estimator_bias[:, post])),
            note=("The shadow outcomes are diagnostic only and are never supplied to Bouncer. "
                  "This homogeneous, equal-traffic experiment makes sampling/locality/state "
                  "bias small; the result does not establish the premise for skewed workloads.")),
        curves={mode: dict(mean=np.mean(a, axis=0).tolist(),
                           ci95_half=(T95_DF11 * np.std(a, axis=0, ddof=1) /
                                      np.sqrt(a.shape[0])).tolist())
                for mode, a in curves.items()},
        delta_hat=dict(mean=np.mean(b_dhat, axis=0).tolist(),
                       ci95_half=(T95_DF11 * np.std(b_dhat, axis=0, ddof=1) /
                                  np.sqrt(b_dhat.shape[0])).tolist()))
    C.save_json("trained_controller.json", summary)

    x = np.arange(cfg.windows)
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.65), gridspec_kw={"width_ratios": [1.45, 1.0]})
    ax = axes[0]
    styles = dict(learned=(C.PALETTE["unguarded"], "ungated learned"),
                  fallback=(C.PALETTE["fallback"], "LRU fallback"),
                  bouncer=(C.PALETTE["bouncer"], "Bouncer"))
    for mode in ("learned", "fallback", "bouncer"):
        mean = np.mean(curves[mode], axis=0)
        half = (T95_DF11 * np.std(curves[mode], axis=0, ddof=1) /
                np.sqrt(cfg.evaluation_seeds))
        color, label = styles[mode]
        ax.plot(x, mean, color=color, label=label)
        ax.fill_between(x, mean - half, mean + half, color=color, alpha=0.12, linewidth=0)
    ax.axvline(cfg.shift_window, color="#333333", ls="--", lw=1.0)
    ax.text(cfg.shift_window + 0.7, 0.06, "PC/reuse\nmeaning swaps", fontsize=7, va="bottom")
    ax.set_xlabel("audit window")
    ax.set_ylabel("cache hit rate")
    ax.set_ylim(0, 0.56)
    ax.legend(loc="upper right", ncol=1, fontsize=7)
    ax.set_title("(a) Learned gain reverses under concept shift")

    ax = axes[1]
    dmean = np.mean(b_dhat, axis=0)
    dhalf = (T95_DF11 * np.std(b_dhat, axis=0, ddof=1) /
             np.sqrt(cfg.evaluation_seeds))
    ax.plot(x, dmean, color=C.PALETTE["accent"], label=r"measured $\hat\Delta$")
    ax.fill_between(x, dmean - dhalf, dmean + dhalf,
                    color=C.PALETTE["accent"], alpha=0.14, linewidth=0)
    ax.axhline(0, color="#666666", lw=0.8)
    ax.axvline(cfg.shift_window, color="#333333", ls="--", lw=1.0)
    ax.axvline(float(np.mean(gate_windows)), color=C.PALETTE["bouncer"], ls=":", lw=1.3,
               label=f"mean gate: +{np.mean(delays):.1f} window")
    ax.set_xlabel("audit window")
    ax.set_ylabel(r"leader hit-rate gap $\hat\Delta$")
    ax.set_title("(b) Competence, not inputs, exposes the reversal")
    ax.legend(loc="center right", fontsize=7)
    C.savefig(fig, "trained_controller.pdf")

    print(f"  validation accuracy={val_accuracy:.4f}, majority={val_majority_accuracy:.4f}, "
          f"log loss={val_logloss:.4f}")
    print(f"  pre hit rate learned/fallback/Bouncer: "
          f"{np.mean(pre_seed['learned']):.4f}/{np.mean(pre_seed['fallback']):.4f}/{np.mean(pre_seed['bouncer']):.4f}")
    print(f"  post hit rate learned/fallback/Bouncer: "
          f"{np.mean(post_seed['learned']):.4f}/{np.mean(post_seed['fallback']):.4f}/{np.mean(post_seed['bouncer']):.4f}")
    print(f"  detected {np.sum(np.isfinite(gate_windows))}/{cfg.evaluation_seeds}; "
          f"delay={np.mean(delays):.2f} windows; PC-TV={max_pc_tv:.6f}")
    print(f"  clean learned gain retained={np.mean(clean_retained):.3f}; "
          f"shifted fallback loss recovered={np.mean(loss_recovered):.3f}")
    print(f"  allocation ceilings={designed_clean_retention:.3f}/{designed_shift_recovery:.3f}; "
          f"estimator bias mean={np.mean(estimator_bias):+.5f}, "
          f"RMSE={np.sqrt(np.mean(estimator_bias ** 2)):.5f}")

    assert val_accuracy > 0.94
    assert max_pc_tv == 0.0
    assert np.all(np.isfinite(gate_windows))
    assert np.mean(delays) <= 3.0
    assert np.mean(pre_seed["learned"]) > np.mean(pre_seed["fallback"]) + 0.05
    assert np.mean(post_seed["learned"]) < np.mean(post_seed["fallback"]) - 0.20
    assert np.mean(clean_retained) > 0.70
    assert np.mean(loss_recovered) > 0.80
    assert abs(np.mean(estimator_bias)) < 0.02


if __name__ == "__main__":
    main()
