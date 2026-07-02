# Bouncer Hardening — Convergence Report

**Project:** `$HOME/projects/bouncer-hpca`
**Role:** SCRIBE (final blackboard emission)
**Date:** 2026-06-29

---

## 1. Fixpoint status and Gap trajectory

**Fixpoint reached: NO.**

The hardening loop did not converge. Three settled nodes (N6, N1, N2) were
processed across four sweeps, but five nodes remain `UNSETTLED / PENDING`
(N3, N4, N5, LEMMA1, PROP1, CONC, WRITEUP) and were never reached before the run
ended. N2 exited via the **escape valve** after 2 failed gate attempts rather
than a clean settle, which is itself a signal that the loop terminated mid-frontier
rather than at a stable point.

**Gap trajectory:** `[3, 3, 3, 3, 2]`

```
Gap
 3  ●────●────●────●
                    \
 2                   ●
    s1   s2   s3   s4   (final)
```

- The Gap held flat at **3** through sweeps 1–4 (N6 GREEN, N1 GREEN, N2 fail, N2 fail).
  Settling N6 and N1 did not move the Gap because the binding constraint was always
  `C_general` (defended=1) and neither node raised it.
- The Gap dropped to **2** only when N2 hit the escape valve and `C_secure` was
  force-settled at defended=2 — i.e. the drop is an *administrative* relaxation of
  the frontier, **not** a genuine reduction in the asserted-vs-defended deficit.
  The honest residual deficit for `C_secure` is still 2 (asserted) vs 0 (truly
  defended for the general claim); see §3 and §4.

A real fixpoint would require the remaining PENDING nodes (especially N4 and the
proof nodes LEMMA1/PROP1) to be visited and the WRITEUP node to absorb the implied
edits. None of that happened.

---

## 2. Per-node verdict

| Node | Status | Strength | One-line reason |
|------|--------|----------|-----------------|
| **N6** | SETTLED | **strong** | Prior-art conjunction is clean: no neighbor unifies all three pillars (secret set-dueling + realized-competence audit + bounded-regret floor on a learned microarch controller). No rewrite forced; only two one-line cites to add. |
| **N1** | SETTLED | **strong** | What the audit certifies is stated correctly and at the right scope: Δ̂ bounds realized advantage **in the controller's own reward metric**, never end utility; over-gating confirmed on `roms` as a falsifiable prediction, not a hidden bug. |
| **N2** | SETTLED | **WEAKENED** | Violation node. The math is correct but its content is a closed-form derivation of the coverage-hole / slow-bleed attack that *breaks* general mimicry resistance. Settled at defended=2 only by **escape valve**; the honest defended level for the general claim is **0**. |
| N3 | UNSETTLED | — | Never reached (PENDING). |
| N4 | UNSETTLED | — | Never reached (PENDING). **See §4 — this is the most consequential gap.** |
| N5 | UNSETTLED | — | Never reached (PENDING). |
| LEMMA1 | UNSETTLED | — | Never reached (PENDING); the safety-floor lemma is unverified by this loop. |
| PROP1 | UNSETTLED | — | Never reached (PENDING); the mimicry proposition is unverified by this loop. |
| CONC | UNSETTLED | — | Never reached (PENDING). |
| WRITEUP | UNSETTLED | — | Never reached (PENDING); implied manuscript edits are **not yet applied**. |

**Summary:** 2 SETTLED-strong (N6, N1), 1 SETTLED-weakened (N2), 7 untouched.

---

## 3. Claims ledger — final asserted / defended

| Claim | Text | Asserted | Defended | What it now honestly says |
|-------|------|:--------:|:--------:|---------------------------|
| **C_floor** | bounded-regret safety floor vs fallback | 3 | **2** | Holds **in the controller's own reward metric `r`**, over the **union of audited declared domains** only. Not yet independently verified (LEMMA1 untouched). Deficit of 1 remains. Crucially, the floor does **not** cover sub-resolution or undeclared regions (the N2 hole). |
| **C_secure** | mimicry resistance vs adversarial steering | 2 | **2 (administrative); 0 (honest)** | Supported **only** for the narrow declared-region-with-intact-secret case. **General (any-region) mimicry resistance is refuted** by N2's coverage-hole / slow-bleed derivation, corroborated by P4 (TPR 1.0 → 0 as f→1). The ledger's defended=2 is the escape-valve value, **not** an earned defense. |
| **C_general** | generality across learned controller classes | 2 | **1** | The binding constraint of the whole run. Held flat at 1 through every sweep; no settled node raised it. Currently demonstrated on one controller family (the ChampSim prefetcher/cache setting), not across controller classes. Deficit of 1. |
| **C_deploy** | real-systems deployability (ChampSim) | 2 | **2** | Fully defended. ChampSim integration is real and produces the `results/champsim.json` and `results/p4.json` evidence used throughout. |

The two live deficits are **C_general (1 short)** and **C_secure (honestly 2 short
for the general claim, papered over to 0 by the escape valve)**.

---

## 4. The single most important thing that changed

**N2 converted a claimed strength into a proven weakness, and the loop absorbed it
by *relaxing the claim* rather than *fixing the system*.**

N2 is a **violation node**. It does not defend `C_secure`; it derives, in closed
form from the single set-dueling variance identity, a **coverage hole** that an
adversary can drive through indefinitely:

- Within-region resolvable gap `δ_R = k·r_max / √(2m·ρ·|R|)` scales as `|R|^(−1/2)`.
- The feasible leader count `n_{L,R} ≥ k²r_max²/(2m·δ_R²)` is **independent of `|R|`** —
  resolution fixes an absolute leader budget; region size only decides whether those
  leaders physically fit.
- **Adversary best response:** with affordable budget `B`, pick the smallest region
  (or trickle the harm) so that `(1−f)·g < δ_R^min(B) = k·r_max/√(2mB)` and sit
  permanently under the resolution floor.
- The safety-floor Lemma (`bouncer.tex:320-339`) does **not** plug this: it bounds
  regret only over the **union of audited declared domains**. A sub-resolution or
  undeclared region lives outside that union.

This is empirically corroborated, not hypothetical: **P4 (`results/p4.json`)** is
exactly the `n_{L,R}=4`, `|R|=32` victim region being eaten as the secret leaks —
TPR `1.0` (f≤0.4) → `0.075` (f=0.8) → `0` (f=1.0). Region size `|R|` and secret-leak
fraction `f` are interchangeable axes of the same hole; the paper currently exposes
only the `f` axis and omits the `|R|` axis.

The gate **correctly rejected** the prior defended=2 for the general claim. The
escape valve then re-settled `C_secure` at defended=2 administratively. **This is a
known overclaim that the ledger now masks.** The honest reading: general mimicry
resistance is *not* established; only the declared-region-with-intact-secret case is.

> **Note on N4:** the brief flagged a possible N4 violation as a candidate "most
> important change." **There is none — N4 was never reached** (it is still
> `UNSETTLED / PENDING`). The dominant event is the N2 weakening above. N4 remains an
> open, unaudited risk: it could surface a *second* violation, and given that it sits
> downstream of the same set-dueling substrate, it should be the **next frontier**
> on any resumed run.

---

## 5. Implied manuscript edits

There is **no `hardening/WRITEUP_patch.md`** — the WRITEUP node was never reached, so
the edits below are **not yet applied**. They are the concrete changes the settled
nodes imply and should be written into `paper/bouncer.tex` (and `related_work.tex`)
on the next pass:

**From N2 (mandatory — fixes an active overclaim):**
1. State the **coverage-hole / slow-bleed attack explicitly** in the security section,
   alongside the existing `f→1` secrecy-leak axis. Add the `|R|`-axis: `δ_R ∝ |R|^(−1/2)`,
   `n_{L,R}` independent of `|R|`, and the adversary best response
   `(1−f)·g < δ_R^min(B)`.
2. **Scope `C_secure` down** wherever stated: mimicry resistance holds for a
   **declared region audited at resolution, with the secret intact** — not for any
   region. Remove or qualify any unconditional "mimicry-resistant" phrasing.
3. **Scope the safety-floor Lemma** (`bouncer.tex:320-339`): make explicit that the
   regret bound covers the **union of audited declared domains only**, and that
   sub-resolution / undeclared regions are out of scope.
4. Apply the **numeric-drift fix** to the budget table: the `|R|=64` row should use
   exact `σ_R = 1/√(2·64·8) = 0.03125`, giving ARL0 `1.069e12` and `α_R = 9.35e-13`
   (replacing the 4-dp-rounded `1.16e12 / 8.6e-13`). All other rows already reproduce.

**From N1 (keep / reinforce — already mostly correct):**
5. Keep `bouncer.tex:140-141` as written. Ensure no sentence claims a bound on **end
   utility (IPC/latency/MLP)**; the certificate is explicitly conditional on the
   unobserved `r ≈ utility` map. Present the `roms` over-gating result as a
   **falsifiable prediction confirmed** (conservative failure: costs utility, preserves
   the floor), and flag the dangerous **over-crediting** case as the open hole the §8
   own-reward design must close.

**From N6 (additive — hardening, not rewrite):**
6. Add two one-line related-work cites in `related_work.tex`:
   - *Conformal Recovery-Deadline Certificates for Runtime Assurance of Adapting
     Controllers* (arXiv 2606.25371, 2026) — differentiate: CPS recovery-time
     conformal cert; no dueling, no secrecy, no reward channel.
   - The **Black-Box Simplex** line — differentiate: relaxes Simplex's model
     requirement via a recovery region, not a relative regret floor.
7. Optionally cite LLM-inference secret-sampling verification (arXiv 2511.02620) as
   **independent corroboration** of the secret-sampling principle in a different
   domain (supports, does not scoop).
8. Keep the "repurposes / borrows the substrate" framing already in the tex. Any
   "first to" claim must be scoped to the **full three-pillar conjunction**, never to
   any single ingredient.

---

## 6. Honest bottom line

The loop verified two claims cleanly (what the audit certifies, and the prior-art
position) and **uncovered that the headline security property is narrower than
advertised**. It did **not** reach a fixpoint: the proof nodes (LEMMA1, PROP1), the
downstream substrate nodes (N3, N4, N5), the conclusion (CONC), and the write-up
(WRITEUP) are all untouched. The most urgent follow-ups are (a) actually applying the
N2 scoping edits to the manuscript, and (b) auditing **N4 next**, since it sits on the
same set-dueling substrate that just produced one violation and is the natural place a
second one would appear.
