# Bounded-resume delta report (N4 + WRITEUP)

Two units executed; no proof reopened; no N4 back-edge fired; preconditions honored
(claims-invariant guarded against missing `text`; N4 capped — the demonstration is a
single bounded experiment, not the unbounded optimizer that stalled the prior run).

## What N4 showed (coverage-hole / slow-bleed demonstration)
FALLBACK branch (controlled harness, **real** Bouncer region dueling + CUSUM + gate FSM;
only the environment is the Python competence harness, labelled synthetic). Independent
Skeptic gate: **GREEN** on all four checks (reproduced the numbers).
- A constant per-window harm `h=0.06` on a 256-set victim region, kept below
  `δ_R^min`, **never trips the gate over a 360-window horizon**: `Δ̂_R` mean `0.205 ≥ τ`,
  CUSUM never alarms, yet **cumulative victim harm grows monotonically to 19.2**.
- **Evade-forever:** across horizons `T∈{120…600}` the attack evades at every length and
  total harm scales linearly (`harm ∝ T`).
- Closed-form floor `δ_R^min(B)=kσ_R ∝ 1/√B` (`0.19,0.13,0.094,0.066` for `n_{L,R}=2,4,8,16`):
  more budget shrinks the hole but never closes it.
- Figure `figures/coverage_hole.pdf` added to the manuscript (`\Cref{fig:hole}`), beside the
  closed-form coverage-hole paragraph in Proposition 1.

## What the discharge map caught and fixed (WRITEUP)
Independent Scribe audit (`hardening/WRITEUP_patch.md`). The **body §IV–IX and Discussion were
already correctly scoped**; the **front matter was not** — a body/front-matter mismatch. Fixed
all **7** over-claims:
1–3. **Abstract** — "bounds the worst-case cost of any controller under adversarial steering",
   "mimicry-resistance that follows exactly from secrecy", "Bouncer detects all (50/50)" →
   all scoped to *declared domain, finite resolution, intact secret, own-reward metric*, with
   the slow-bleed exception named.
4,7. **Introduction** — the hedge thesis ("capping the downside at the floor") and the
   reward-vs-utility conflation ("which is what one ultimately cares about") → scoped to the
   audited domains / own reward; certificate explicitly not over end utility.
5. **Contributions** — the guarantees bullet → "*per-domain* mimicry-resistance proposition …
   slow-bleed named as open vulnerability".
6. **Conclusion** — "caps the worst-case behavior of *any* controller … under adaptive mimicry"
   → declared-domain + intact-secret + own-reward scope + named coverage hole.

Hypothesis-discharge table: **complete** (A1–A5 of Lemma 1; the four Prop-1 premises; both
theorem-scope rows), each anchored to where it is established/measured/assumed. Symbol check:
unified `K=τ+γ/2` notation; figure budget convention aligned to `n_{L,R}` (the N2/Prop-1
convention). Citations: `mehmood2022blackbox` + `shojaei2026conformal` integrated and resolve;
off-topic arXiv:2511.02620 removed from the candidate list.

## Final state of C_secure
**C_secure (general mimicry resistance vs steering): defended ≈ 0 — refuted.** The surviving,
now-front-matter-consistent claim: mimicry resistance holds **only for a declared domain audited
at resolution `δ_R^min(B)` with an intact secret**; the safety floor holds over the **union of
audited declared domains, in the controller's own reward metric**; the sub-resolution slow-bleed
adversary is a **named, un-closed vulnerability**, now demonstrated (`fig:hole`). No prose claim
in the manuscript exceeds the scoped theorems. Manuscript: 12 pp, compiles clean, 0 undefined.
