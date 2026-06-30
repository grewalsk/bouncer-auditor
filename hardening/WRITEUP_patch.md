# Bouncer — Independent WRITEUP Audit (SCRIBE)

**Auditor role:** SCRIBE (did NOT write this paper).
**Files audited:** `paper/bouncer.tex` (full), `paper/related_work.tex`, `paper/references.bib`,
plus the claims ledger in `hardening/state.json` and `hardening/CONVERGENCE_REPORT.md`.
**Date:** 2026-06-30.

## Scope of the honest, surviving claim (from the hardening fixpoint)

The GENERAL mimicry-resistance claim (`C_secure` at defended=2) was **refuted** by node N2:
it derives in closed form a **coverage-hole / slow-bleed** attack (an adversary keeping
per-window harm below `δ_R^min(B)` evades forever; total harm grows unbounded in the horizon).
The honest, surviving claim is **scoped**: Bouncer is mimicry-resistant *only* for a **declared
domain** audited at resolution `δ_R^min(B)` with an **intact secret**. The safety floor (Lemma 1)
holds only over the **union of audited declared domains**, and **only in the controller's own
reward metric `r`** — never end utility (IPC/latency/MLP). Separately, the earlier
"the fix is the controller's own reward" claim was **refuted**: own reward moves the roms tax
only `11.2% → 9.7%`; set-dueling needs a *set-local* reward, which prefetchers lack.

This audit checks whether the PROSE in the manuscript matches that scoped position.

---

## TASK 1 — Hypothesis-Discharge Table

### Lemma 1 (Safety floor), Assumptions A1–A5 (`bouncer.tex:308–318`, lemma `:320–330`)

| Hyp. | Statement | Where established / measured / assumed | Status |
|------|-----------|----------------------------------------|--------|
| **A1** | per-decision reward `r ∈ [0, r_max]` (bounded) | **Assumed** as a modeling premise (`:309`, formal setting `:151–156`); **enforced by construction** in the harness, "bounded rewards drawn so Var ≤ r_max²/4m exactly" (`:486–488`). It is also the load-bearing assumption flagged in the contributions/methodology (`:144–147`, `:470`). | ASSUMED (premise), realized in harness |
| **A2** | a drop episode (`Δ_t < τ`) is gated within `D` windows w.p. `≥ 1−δ`; `D = H/(K−Δ_t)` mean + tail | **Derived** from quickest-detection theory (`:271–280`, `:343–354`) via Siegmund's ARL approx (`eq:siegmund`, `:348–350`); **measured** empirically P1 (`D≈1.8`, one-window best case, `:516–519`), P2 latency chain (`:544–548`), and theory-validation `fig:theory` (`:683–700`, ratio 0.998). | DERIVED + MEASURED |
| **A3** | per-window false-alarm prob `≤ α = 1/ARL_0` | **Derived** from Siegmund corrected-boundary ARL_0 growing exp. in `H/σ_Δ` (`:343–354`); **measured** in `fig:theory(a)` (ARL_0 emp. 927 vs theory 938, `:687`); in the deployed strong-drift regime `α ≈ 0` (`:691–693`). | DERIVED + MEASURED |
| **A4** | a gate switch transient costs `≤ c_sw` | **Assumed** as a bounded per-switch cost (`:316`); enters the floor as `α T c_sw`, reported `≈0` in the deployed regime (`:698`). Not independently measured. | ASSUMED |
| **A5** | there are `N_ep` drop episodes over horizon of `T` windows | **Assumed/parameterized** (`:316–317`); instantiated `N_ep=6` in the theory-validation regret envelope (`:698–700`). | ASSUMED (parameter) |
| **Lemma scope** | floor bounds regret only over the **union of audited declared domains**, in metric `r` | **Stated** in Discussion (`:838–845`) and the coverage-hole paragraph (`:402–421`, esp. "proven only over the *union of audited domains*"). N1 confirms metric is `r`, not end utility. | ASSUMED/SCOPED (correct) |

### Proposition 1 (Mimicry resistance, per-domain) (`bouncer.tex:362–377`, proof `:378–388`)

| Hyp. | Statement | Where established / measured / assumed | Status |
|------|-----------|----------------------------------------|--------|
| **P1: secret uniform partition** | Leader-L & follower sets of `R` drawn uniformly at random each epoch, unobservable to the adversary | **Assumed** as the mechanism (`:365–366`, threat model "The secret" `:188–189`); its load-bearing role is asserted (`:397–400`) and **measured** by the secrecy ablation P4(b) (`:600–608`, TPR `1.0→0` as `f→1`). | ASSUMED + MEASURED (ablation) |
| **P2: within-region exchangeability up to β** | within-`R` set outcomes exchangeable, heterogeneity bias `\|b_R\| ≤ β` | **Assumed** (`:366–367`); **measured** under violation in the misspecification sweep (`σ_het` to 0.30, `fig:robust`, `:639–657`): TPR stays 1.0, latency drifts `1.0→1.7`. Reseeding shrinks β toward i.i.d. (`:395–397`, `:646–649`). | ASSUMED + MEASURED (robustness) |
| **P3: intact secret (β-leak axis `f`)** | adversary blind to within-`R` assignment; leak fraction `f` degrades the bound | **Assumed** (intact case); leak behavior **derived** (`:373–376`) and **measured** P4(b) (`:603–608`). | ASSUMED + MEASURED |
| **P4: bounded reward (A1 reuse)** | reuses `r ∈ [0,r_max]` for the concentration bound `eq:var` (`:260–263`) | Same as A1; **assumed** + harness-enforced (`:486–488`). | ASSUMED (premise) |
| **Prop scope** | holds only for a **declared** domain at resolution `δ_R^min(B)`; global `Δ̂` carries NO guarantee; coverage hole un-closed | **Stated explicitly** (`:356–360`, `:390–400`, and the coverage-hole paragraph `:402–421`: "*We therefore claim mimicry resistance only for declared domains audited at resolution `δ_R^min(B)` with an intact secret—not general, any-region security*"). | SCOPED (correct, matches N2) |

**Discharge table complete: YES.** Every A1–A5 hypothesis and all four Proposition-1
premises (secret uniform partition, within-region exchangeability up to β, intact secret,
bounded reward) plus both theorem scopes have a row.

---

## TASK 2 — Over-Claim Scan (TITLE, ABSTRACT, INTRO, CONCLUSION)

I read the title, abstract (`:36–73`), introduction incl. contributions (`:75–147`),
and conclusion (`:869–878`). I flag only sentences whose prose **exceeds** the scoped
theorems — i.e. they imply (a) general / any-region mimicry resistance without the
declared-domain + intact-secret scope, or (b) a floor over **end utility (IPC)** rather than
the controller's own reward `r`, or (c) that the controller's own reward is "the fix."

Sentences that are already correctly scoped (e.g. the body §IX-G coverage-hole paragraph
`:402–421`, the §IX-A mimicry proposition `:356–400`, the Discussion `:838–867`, and the
abstract's "candidly exposing that its decisions are only as good as the competence reward")
are **not** flagged.

### OVERCLAIM 1 — Abstract (the "exactly from secrecy" mimicry-resistance sentence)

- **Location:** Abstract, `bouncer.tex:53–56`.
- **Verbatim:** "We prove a bounded-regret safety floor (Bouncer is never more than `N_ep·D·r_max + αTc_sw` worse than the fallback) and a mimicry-resistance property that follows *exactly* from the secrecy of the sampler."
- **Why it over-claims:** Reads as an *unconditional* mimicry-resistance property. It omits the declared-domain + finite-resolution scope and the floor's union-of-declared-domains / own-reward scope. Per N2, general mimicry resistance is refuted.
- **Exact rewrite:** "We prove a bounded-regret safety floor (over the union of audited declared domains, in the controller's own reward metric, Bouncer is never more than `N_ep·D·r_max + αTc_sw` worse than the fallback) and a *per-domain* mimicry-resistance property that follows exactly from the secrecy of the sampler—scoped to a declared region audited at finite resolution with the secret intact, and *not* general any-region security."

### OVERCLAIM 2 — Abstract (the "bounds the worst-case cost of any such controller ... under both adversarial steering and benign drift")

- **Location:** Abstract, `bouncer.tex:43–47`.
- **Verbatim:** "We present **Bouncer**, a runtime monitor and trust gate that bounds the worst-case cost of any such controller to that of a known-safe fallback heuristic, under both adversarial steering and benign drift, with no POMDP/belief-state machinery and no added latency on the cache-access critical path."
- **Why it over-claims:** "bounds the worst-case cost ... under ... adversarial steering" with no scope reads as general steering-security. The slow-bleed / coverage-hole adversary (a redistributive steering attack under the resolution floor) is *not* bounded — total harm grows unbounded in `T`. The bound is also in reward `r`, over declared domains only.
- **Exact rewrite:** "We present **Bouncer**, a runtime monitor and trust gate that, for declared domains audited at resolution `δ_R^min(B)` with the secret intact, bounds the worst-case competence cost (in the controller's own reward metric) of any such controller to that of a known-safe fallback heuristic under benign drift and adaptive mimicry, with no POMDP/belief-state machinery and no added latency on the cache-access critical path; a sub-resolution slow-bleed adversary remains an explicitly named open vulnerability."

### OVERCLAIM 3 — Abstract (headline "Bouncer detects *all*")

- **Location:** Abstract, `bouncer.tex:63–67`.
- **Verbatim:** "under an adaptive mimicry adversary, an input-OOD monitor detects *none* of the attacks (`0/50`, Wilson 95% upper bound `0.07`) while Bouncer detects *all* (`50/50`, lower bound `0.93`)—and we show this robustness is purchased entirely by the secrecy of the dueling sets, collapsing as the assignment leaks."
- **Why it over-claims:** "detects *all*" is true only for the *declared-domain, intact-secret* mimicry adversary of P4(a). Stated baldly in the abstract it suggests general mimicry detection; the same P4 axis already shows TPR `→0` for the redistributive / leaking case. The "collapsing as the assignment leaks" clause partially scopes it but is about the `f` axis only, not the `|R|`/resolution axis (the coverage hole).
- **Exact rewrite:** "under an adaptive mimicry adversary *within a declared, secret-intact domain*, an input-OOD monitor detects *none* of the attacks (`0/50`, Wilson 95% upper bound `0.07`) while Bouncer detects *all* (`50/50`, lower bound `0.93`)—a robustness purchased entirely by the secrecy of the dueling sets, which collapses both as the assignment leaks and against a sub-resolution redistributive (slow-bleed) adversary outside the audited domain."

### OVERCLAIM 4 — Introduction (the hedge thesis: "capping the downside at the heuristic's floor")

- **Location:** Introduction, `bouncer.tex:101–106`.
- **Verbatim:** "We would like to keep the upside while capping the downside at the heuristic's floor. That is a hedging problem, and Bouncer is the constructive hedge."
- **Why it over-claims:** As a thesis statement it promises the downside is *capped at the floor*, unconditionally. The coverage hole shows the downside is *not* capped for a sub-resolution region (unbounded cumulative harm), and the cap is in `r`, over declared domains.
- **Exact rewrite:** "We would like to keep the upside while capping the downside, over the audited declared domains and in the controller's own reward metric, at the heuristic's floor. That is a hedging problem, and Bouncer is the constructive hedge—one whose cap, we show, has an explicit sub-resolution coverage hole."

### OVERCLAIM 5 — Introduction, Contributions list (the guarantees bullet)

- **Location:** Contributions, `bouncer.tex:128–131`.
- **Verbatim:** "a bounded-regret safety floor (\Cref{lem:floor}) tied directly to the CUSUM average-run-length theory ... and a mimicry-resistance proposition (\Cref{prop:mimicry}) whose strength is exactly the secrecy of the sampler."
- **Why it over-claims:** Listing it as "a mimicry-resistance proposition" without the per-domain qualifier reads as general. The proposition itself is titled "Mimicry resistance, **per-domain**" (`:362`) and is explicitly *not* general (`:356–360`); the contributions list should carry that scope.
- **Exact rewrite:** "a bounded-regret safety floor (\Cref{lem:floor}, over the union of audited declared domains, in the controller's own reward) tied directly to the CUSUM average-run-length theory ... and a *per-domain* mimicry-resistance proposition (\Cref{prop:mimicry})—scoped to a declared region audited at resolution `δ_R^min(B)` with an intact secret, with the sub-resolution slow-bleed attack named as an open vulnerability—whose strength is exactly the secrecy of the sampler."

### OVERCLAIM 6 — Conclusion (the headline cap sentence)

- **Location:** Conclusion, `bouncer.tex:869–878`.
- **Verbatim:** "it caps the worst-case behavior of any learned microarchitectural controller at its vetted fallback—under benign drift and an adaptive mimicry adversary alike—for `~336` bytes and zero added datapath latency."
- **Why it over-claims:** "caps the worst-case behavior of *any* ... controller at its vetted fallback ... under ... an adaptive mimicry adversary" is the general claim N2 refuted. It omits the declared-domain + intact-secret scope, the reward-metric scope, and the named coverage-hole exception.
- **Exact rewrite:** "for declared domains audited at resolution `δ_R^min(B)` with the secret intact, it caps the worst-case *competence* (in the controller's own reward metric) of a learned microarchitectural controller at its vetted fallback—under benign drift and an adaptive mimicry adversary alike—for `~336` bytes and zero added datapath latency; a sub-resolution slow-bleed adversary outside the audited domain is a named, un-closed vulnerability."

### OVERCLAIM 7 — Introduction "Why not monitor inputs" (utility-vs-reward conflation)

- **Location:** Introduction, `bouncer.tex:108–116`.
- **Verbatim:** "Bouncer instead measures *realized competence*—the reward the controller actually earns relative to the fallback—which is what one ultimately cares about and what an attacker cannot fake without actually making the controller good."
- **Why it over-claims:** "which is what one ultimately cares about" conflates the controller's own reward `r` with end utility. Per N1, the certificate is conditional on the unobserved `r ≈ utility` map; the roms result shows `sign(Δ^reward) ≠ sign(Δ^utility)` is possible, so reward is *not* automatically what one ultimately cares about. (The clause "what an attacker cannot fake without actually making the controller good" is itself only true up to the resolution floor / declared domain.)
- **Exact rewrite:** "Bouncer instead measures *realized competence*—the reward the controller actually earns relative to the fallback—a signal an attacker cannot fake within a declared, secret-intact domain without actually making the controller good (in that reward metric); the certificate is over the controller's own reward, not end utility, which it tracks only insofar as reward proxies utility."

### Borderline cases checked and NOT flagged (already scoped)

- Abstract `:67–72` ("bounding a corrupted prefetcher's damage to the prefetch-off floor—and **candidly exposing that its decisions are only as good as the competence reward it is given**") — correctly scoped; explicitly disclaims utility fidelity. **Not flagged.**
- Abstract `:70–73` ("The mechanism's quantitative guarantees are validated in a fully-released synthetic harness; the ChampSim integration is a real-simulator proof of deployment, not a SPEC sweep.") — correctly scoped. **Not flagged.**
- Contributions `:143–147` ("We are explicit ... that the controlled quantitative claims come from the synthetic harness ...") — correctly scoped. **Not flagged.**
- Conclusion `:876–878` ("The robustness is not free: we show it is purchased exactly by the secrecy of the dueling sets, and we quantify the price of losing it.") — correctly scoped on the `f` axis (does NOT claim generality). **Not flagged** (though it would benefit from naming the coverage hole too; optional).
- Body §IX-A/§IX-G (`:356–421`) and Discussion (`:838–867`) — these are the *correctly scoped* statements; they already say "declared domains audited at that resolution with an intact secret" and "name the sub-resolution coverage hole as an open vulnerability." **Not flagged** (these are the model the front-matter should match).
- Discussion `:855–867` and §VI-J ChampSim (`:760–779`, `:855–867`) — the own-reward-is-NOT-the-fix result is stated **correctly** (`11.2%→9.7%`, set-local tension). **Not flagged.** No surviving sentence still says own reward "is the fix."

**No surviving sentence claims the controller's own reward is "the fix."** That refutation
is already correctly written into the body and Discussion. The over-claims are confined to
the front matter (abstract / intro / conclusion), which still over-promises *general* security
and a *utility* cap relative to the scoped body.

---

## TASK 3 — Symbol / Consistency Spot-Check

| Symbol | First use | Definition | Verdict |
|--------|-----------|------------|---------|
| `τ` | abstract uses "trust threshold τ" (`:53` via contributions `:120`), Def. "Off-policy condition" defines it | Defined `:165–169` (`Δ_W < τ`, `τ ≥ 0`); operating point `τ=0.05` (`:489`), ChampSim `τ=0` (`:724`) | OK — defined at first formal use; the two operating-point values are clearly labeled as harness vs ChampSim, not a redefinition. |
| `K` | `:120` contributions? no — first in CUSUM `:274` | Defined `:274` as `K = τ + γ_detect/2`; restated A2 `:310` as `K = τ + γ/2` | OK (γ vs γ_detect is the same constant, minor notation drift — see note). |
| `σ_Δ` (`\sigd`) | `eq:var` `:260–263` defines `σ_Δ²` | Defined at first use (`:263`); regional variant `σ_{Δ,R}` introduced `:375` and `:407` | OK — both defined where introduced. |
| `Δ̂` (`\dhat`) | abstract narrative + contributions `:124` ("`Δ̂ = r̄_L − r̄_F`") | Formally defined `:250–252` (`Δ̂_W = r̄_L − r̄_F`); per-domain `Δ̂_R` `:369` | OK — contributions give the inline form; §V gives the formal definition. Acceptable forward reference. |
| `δ_R^min` (`δ_R^{\min}`) | First in coverage-hole paragraph `:404–411` | Defined `:409–411` (`δ_R = k σ_{Δ,R} = k r_max/√(2mρ\|R\|)`, budget floor `δ_R^min(B)`) and `fig:hole` caption `:428–430` (`δ_R^min(B)=kσ_R ∝ 1/√B`). | OK — defined at first use. |
| `β` | Prop. 1 `:366` ("heterogeneity bias `\|b_R\| ≤ β`") | Defined at first use `:366`; reused proof `:381–386`, misspecification `:643`. | OK. |
| `B` (budget) | Coverage-hole paragraph `:402–411` | Defined implicitly as "a fixed budget `B`" / "affordable budget" (`:409–411`), `fig:hole` `B=4,8,16,32` (`:430`). Note: `B` (leader budget) is distinct from `b_R` (bias) and `b` (Siegmund boundary `:347`). | OK but see note 3. |

**Notes / minor (non-blocking):**
1. **`K` constant — `γ_detect` vs `γ`.** `:274` writes `K = τ + γ_detect/2`; `:310` (A2) writes `K = τ + γ/2`. Same quantity, two names. Recommend unifying to `γ` (or `γ_detect`) in both places.
2. **`D` overloaded.** `D` is the detection delay throughout (`:316`, `:329`, `:343`), but `:54` and `:324` also has it in the floor `N_ep·D·r_max`; consistent there. Separately `D_{val}` (validation distribution, `:155`, `:288`) is a distinct symbol — no collision because of the subscript, but a reader skim could trip. Acceptable.
3. **`B` (leader budget) vs `b_R` (bias) vs `b` (Siegmund boundary `b=H/σ_Δ+1.166`, `:347`).** Three `b`-family symbols. All distinguishable (capital/subscript), no true clash. No change required.
4. **No symbol is defined twice with conflicting meaning.** No symbol is used before any definition in a way that would block comprehension (the abstract/contributions inline-introduce `τ`, `Δ̂` and then §IV–V formalize them — standard forward referencing).

---

## TASK 4 — Citations + Figure Check

| Item | Result |
|------|--------|
| `\cite{mehmood2022blackbox}` present in `related_work.tex` | **YES** — `related_work.tex:5` ("Black-Box Simplex `\cite{mehmood2022blackbox}`"). |
| `mehmood2022blackbox` resolves in bib | **YES** — `references.bib:481–487` (complete `@inproceedings`, NFM 2022, arXiv:2102.12981). Resolves to `\bibcite{mehmood2022blackbox}{35}` in `bouncer.aux`. |
| `\cite{shojaei2026conformal}` present in `related_work.tex` | **YES** — `related_work.tex:5` ("conformal prediction `\cite{shojaei2026conformal}`"). |
| `shojaei2026conformal` resolves in bib | **YES** — `references.bib:489–494` (complete `@article`, arXiv:2606.25371, 2026). Resolves to `\bibcite{shojaei2026conformal}{36}`. |
| `\Cref{fig:hole}` referenced | **YES** — referenced at `bouncer.tex:418`; figure labeled `\label{fig:hole}` at `:431` (env `:423–432`, image `coverage_hole.pdf`). `bouncer.aux:73–74` confirms `\newlabel{fig:hole}` and `fig:hole@cref` (figure 3). |
| Undefined references/citations in build log | **NONE** — `bouncer.log` shows no "undefined" or citation/reference warnings. |

Both newer related-work cites the hardening report recommended (N6 items 6) are **present and
resolve**. Citations + figure: **OK.**

---

## STRUCTURED SUMMARY

**(a) Does any prose claim exceed the scoped theorems?**
**YES.** The body (§IV–IX) and Discussion are correctly scoped and already name the
coverage-hole as an open vulnerability and the own-reward "fix" as refuted. But the
**front matter — title-adjacent abstract, introduction (incl. contributions), and conclusion —
still over-promises**: it asserts general / any-region mimicry resistance and steering-security
("caps the worst-case behavior of *any* ... controller ... under an adaptive mimicry adversary",
"bounds the worst-case cost of any such controller ... under ... adversarial steering",
"mimicry-resistance property that follows exactly from the secrecy of the sampler"), and in one
place conflates the controller's own reward with end utility ("which is what one ultimately cares
about"). These exceed the scoped Lemma 1 (union of *declared* domains, in reward `r`) and the
*per-domain* Proposition 1. There is a front-matter / body mismatch.

**(b) Overclaim sentences with exact rewrites** — 7 found, all in the abstract / intro /
conclusion (full verbatim + rewrite in Task 2 above):
1. `:53–56` Abstract — "mimicry-resistance property that follows *exactly* from the secrecy of the sampler" → add per-domain + declared-resolution + intact-secret + floor reward/union scope.
2. `:43–47` Abstract — "bounds the worst-case cost of any such controller ... under ... adversarial steering" → scope to declared domains, reward metric; name slow-bleed exception.
3. `:63–67` Abstract — "Bouncer detects *all* (`50/50`...)" → scope detection to declared, secret-intact domain; note collapse vs sub-resolution redistributive adversary.
4. `:101–106` Intro — "capping the downside at the heuristic's floor ... constructive hedge" → cap is over audited declared domains, in reward; note the coverage hole.
5. `:128–131` Contributions — "a mimicry-resistance proposition ... exactly the secrecy of the sampler" → per-domain, declared-resolution, intact-secret; floor over union/reward; name open vuln.
6. `:869–878` Conclusion — "caps the worst-case behavior of any learned microarchitectural controller at its vetted fallback—under ... adaptive mimicry adversary" → declared domain + intact secret + reward-metric scope; name slow-bleed exception.
7. `:108–116` Intro — "realized competence ... which is what one ultimately cares about" → reward, not end utility; certificate conditional on `r ≈ utility`.

**(c) Discharge table complete?** **YES.** All of A1–A5 (Lemma 1) and all four Proposition-1
premises (secret uniform partition, within-region exchangeability up to β, intact secret,
bounded reward) plus both theorem-scope rows are present, each marked
established / measured / assumed with file-line anchors.

**(d) Citations + figure OK?** **YES.** `\cite{mehmood2022blackbox}` and
`\cite{shojaei2026conformal}` are both present in `related_work.tex:5`, both have complete bib
entries (`references.bib:481–487`, `:489–494`), and both resolve in `bouncer.aux`
(refs 35, 36). `\Cref{fig:hole}` is referenced (`:418`) and defined (`:431`), resolving to
figure 3. No undefined-reference warnings in `bouncer.log`.

**Symbol/consistency:** clean. No symbol used-before-definition that blocks comprehension and
no conflicting double-definition. Only cosmetic notation drift: `K = τ + γ_detect/2` (`:274`)
vs `K = τ + γ/2` (`:310`) — unify the subscript.
