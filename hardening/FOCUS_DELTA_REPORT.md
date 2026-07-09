# FOCUS-loop delta report — Bouncer

*Methods-and-paper convergence, run **on top of** the E-loop layer (committed at
`aba145d`, whose own report is `DELTA_REPORT.md`). This loop did **not** rewrite the
paper's structure; it converged onto one committed thesis at exactly the strength the
reproduced evidence supports, killed the residual overclaims the E-loop left, positioned
against a reference class whose bar the evidence clears, and emitted `FOCUS_SHEET.md`.
"Structure after." Every judgment gate was adjudicated by an independent hostile-critic
subagent that was **not** the producer.*

> **Provenance note.** This FOCUS run (session `fa208fab`) executed concurrently with a
> second session (`3dbe50db`) that ran the E-loop and produced `aba145d` + `DELTA_REPORT.md`
> in the **same working tree**. The FOCUS edits below are layered (uncommitted) on top of
> `aba145d`. Nothing was committed/pushed by this loop — see "Handoff."

---

## 0. Starting state (the E-loop layer, verified — not this loop's to redo)

The E-loop had already run the keystone and it **fell back**: `results/e1_keystone.json`
records `KEYSTONE_REAL=false`. The real ChampSim replacement is a **boundary/limitation**
result: a `cache_fill` fix makes `dhat` nonzero; the whole-cache gap is real (LIP 0.336 vs
SRRIP-HP 0.048); but the secret per-epoch reseed **confounds** the **stateful** replacement
reward (reseeded clean `dhat`=0.005≈noise vs fixed-leader 0.233). Finding: **set-locality is
necessary but not sufficient — a secret reseeded audit also needs a (near-)stateless reward**
(`Remark 1`). Phase M treated this as solid and *verified* it (below), did not rebuild it.

## 1. Keystone: still fallen back — nothing re-attempted, nothing faked

`KEYSTONE_REAL=false`, unchanged. All upside/dynamics claims stay scoped to the **stateless
synthetic harness**; the two real ChampSim results are a **downside cap** (prefetcher floor)
and a **boundary finding** (replacement reseed-confound). The committed thesis (T-char)
requires the keystone at strength ≤ 2-synthetic, so this is a valid terminal.

## 2. Phases (each gate adjudicated by an independent hostile critic)

**Phase M (verify-dominant) — PASS.** INV-2 reproduced: `run_all.sh` regenerated every
`results/*.json` + `champsim_e1/*` **bit-identically** (sha256 before==after); C++ self-test
passes. Theory–code coherence PASS: σ_Δ bound, Siegmund ARL (critic regenerated
`ARL(0,5,0.5,1)=938.2`=paper's "938"), Lemma-1 constants (loose 15.1/tight 7.8/measured 5.9),
A1–A5 → discharge table with honest E/M/A tags (A1-stateless = "fails, measured, on a real
cache"). One **DEFECT** (E3 detectability caption vs flat data) → fixed in Phase C. Adversarial
probe: mimicry headline **survives** (0/50 input-OOD is definitional; full-Bouncer TPR=1 earned
on the non-spoofable reward; earned measurement = secrecy ablation).

**Phase R — PASS, bar clearable=TRUE.** Reference class committed:
**runtime assurance + label-free deterioration monitoring**. Both families' norm is
sim+guarantees, not real-silicon wins. Gap fixed: family B (Suitability Filter / Sequential
Harmful Shift Detection / D3M) was **entirely uncited**; the paper foiled only against input-OOD
monitors (a strawman). Added 3 bib entries + a positioning passage in `related_work.tex` naming
the neighbors, the three surviving deltas (secret reseed→mimicry resistance; ~336 B hardware +
bounded-regret floor; set-locality attributability), demoting input monitors to "weakest
alternative."

**Phase T — T-char committed** (`exceeds=false, underclaims=false`; fingerprint
`8c36d05576833603`; sentence in `FOCUS_SHEET.md`/`state.json`). T-monitor rejected (implies a
real guarantee `KEYSTONE_REAL=false` denies); T-hybrid subsumed. Thesis already matched the
paper's abstract/intro/conclusion → stable across the sweep.

**Phase C — 20 candidates → 17 CONFIRMED overclaims REDUCED + 3 producer-missed fixed; 3
ALREADY_SCOPED.** All reductions verified to match evidence **without over-retreating** (the real
downside cap, real whole-cache gap 0.336 vs 0.048, synthetic mimicry TPR 1.0, and R²=0.997
controlled-harness fit all survive). Clusters: E3 detection-power roll-off (flat TPR ⇒ "predicted,
not exercised"); "no added latency" (bald ⇒ *by construction / analytical, RTL future work*, 5
sites); "replacement is **the clean case** / confirms the clean side" (⇒ set-local-but-**stateful**
boundary, 7 sites); CUSUM "delay-optimal" ⇒ "near-optimal/well-motivated"; mimicry f-boundary ⇒
empirical cliff at 0.6–0.8; "proof-of-deployment" ⇒ "boundary study"; "validating **every** claim"
⇒ "the mechanism's quantitative claims."

**Phase E (REDUCE-biased) — no RUN forced.** `defended ≥ thesis_required` for every claim
(INV-5). The E3 gap was resolved by REDUCE, not RUN. **R-latency** queued **OPTIONAL** (T-char
does not need a roll-off claim). R-reseed / R-multitrace not queued (they serve T-mech escalation,
out of scope with `KEYSTONE_REAL=false`).

## 3. Result — FOCUSED

- **Gap = Σ(asserted − defended) = 0.** Every `overclaim=false`.
- **INV-1..INV-5 all green** (two independent final critics: overclaim-residual critic found 1
  missed bald "0 ns added" @ line 711 → fixed → `FOCUSED_INV1_GREEN`; thesis-coherence critic →
  `THESIS_COHERENT_GREEN`).
- Paper recompiles clean: **15 pp, 0 undefined citations/refs**; 3 new family-B citations resolve.
- `focused=true` in `state.json`; `FOCUS_SHEET.md` on disk. **FIXPOINT reached → HALT.**

Deliverables on disk (uncommitted, layered on `aba145d`):
`paper/bouncer.tex`, `paper/related_work.tex`, `paper/references.bib` (edited);
`hardening/state.json` (FOCUS schema, `focused=true`); `hardening/FOCUS_SHEET.md`; this file.

## 4. UNRESOLVED / flagged for human

- **Family-B bib metadata** — `pouget2024suitability`, `amoukou2024sequential`, `d3m2024` carry
  best-effort author/title/year + `note="bibliographic details to verify before submission"`.
  Verify exact venue/year/arXiv-id before submission (a "structure after" step).
- **Stale artifact** — `results/adversarial_review.json` reviews a **superseded** draft (objects to
  an "un-run ChampSim skeleton" / "0 ns" framing already discharged). Recommend delete/date it.
- **E3 JSON internal `scope` string** — `results/e3_sensitivity.json`'s `scope` field still says
  detection power "degrades near the crossing," self-contradicting its own flat `[1.0]×7` data. The
  **paper does not inherit this** (Phase C fixed the paper). Optional cleanup: correct the string in
  `exp_e3_sensitivity.py` and regenerate (changes only that JSON's scope text).
- **R-latency (optional)** — run the latency-vs-Δ sweep to state the E3 detection-power story
  *positively* rather than retreated (cheap, synthetic).
- **Concurrency** — a second session (`3dbe50db`) shares this working tree; coordinate before any
  commit/push (see Handoff).

## 5. Revised odds — a guess, not a guarantee (disaggregated by venue *type*)

The FOCUS pass fixes overclaims; it does **not** fix the missing-real-win objection (no RUN
forced, `KEYSTONE_REAL` still false, no positive real result). Those two facts move different
venues by different amounts, so the odds must **not** be lumped:

- **TMLR ≈ 55–65%.** A claim/evidence-graded journal with **no significance / no "is the win
  big enough" bar** — exactly the bar the FOCUS fixes clear. A genuine strength-3 set-locality
  *characterization* (real ChampSim both sides), an honest stateless-reward refinement, a
  reproduced synthetic mechanism with proofs + CIs, and now **zero** claim/evidence gaps. This
  is where removing the overclaims is load-bearing.
- **MLSys ≈ 30%.** A **systems** venue — it keeps the **same missing-real-win bar as HPCA/ISCA**.
  The FOCUS fixes help the claim/evidence story but do almost nothing for the systems-venue
  objection, which the loop explicitly did not address. **MLSys groups down with the systems
  venues, not up with TMLR** — the earlier report's "MLSys/TMLR ≈ 55–65%" lumping was wrong.
- **HPCA/ISCA ≈ 20–25%, unchanged.** Needs a real-silicon upside win that `KEYSTONE_REAL=false`
  denies.

Net: the FOCUS pass raises **TMLR** (removes the significance bar) and leaves the **systems**
venues (MLSys, HPCA, ISCA) where they were. *Explicitly a subjective estimate.*

## Handoff

The FOCUS loop halts to the human (its terminal is FOCUSED + `FOCUS_SHEET.md`, not a commit).
**Nothing was committed or pushed by this loop**, because a concurrent session (`3dbe50db`) shares
this working tree and the branch `hardening/e-loop-keystone` (already pushed to origin at `aba145d`).
To make the FOCUS work durable: confirm the other session is idle, then
`git add -A && git commit` the FOCUS edits as a new commit on top of `aba145d` (do **not** force-push
`main`). The E-loop's `DELTA_REPORT.md` and its committed `state.json@aba145d` were left intact.
