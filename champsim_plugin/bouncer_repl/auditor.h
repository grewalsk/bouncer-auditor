// bouncer.h — Off-Policy Competence Auditor (ChampSim-deployable skeleton).
//
// Semantics are identical to the simulation-validated Python harness in
// ../bouncer/. This header is self-contained C++17 (no ChampSim headers) so it
// can be unit-tested standalone (see bouncer.cc selftest) and then dropped into
// a ChampSim prefetcher/replacement module (see pythia_bouncer_shim.cc).
#ifndef BOUNCER_AUDITOR_H
#define BOUNCER_AUDITOR_H

#include <cstdint>
#include <vector>
#include <random>
#include <algorithm>
#include <cmath>

namespace bouncer {

// ---- one-sided lower CUSUM (repeated-CUSUM: resets on alarm) ---------------
struct LowerCusum {
  double K, H, C = 0.0;
  bool auto_reset = true;
  LowerCusum(double k, double h) : K(k), H(h) {}
  bool update(double x) {
    C = std::max(0.0, C + (K - x));
    if (C > H) { if (auto_reset) C = 0.0; return true; }
    return false;
  }
  void reset() { C = 0.0; }
};

// ---- two-sided CUSUM (Tier-A residual/score monitors) ---------------------
struct TwoSidedCusum {
  double ref, k, H, Cp = 0.0, Cn = 0.0;
  bool auto_reset = true;
  TwoSidedCusum(double r, double kk, double h) : ref(r), k(kk), H(h) {}
  bool update(double x) {
    double d = x - ref;
    Cp = std::max(0.0, Cp + d - k);
    Cn = std::max(0.0, Cn - d - k);
    if (Cp > H || Cn > H) { if (auto_reset) { Cp = Cn = 0.0; } return true; }
    return false;
  }
};

// ---- randomized-secret set-dueling ----------------------------------------
// Secret per-set/per-bucket pool tag, reseeded each epoch from an on-die RNG.
// 0 = follower, 1 = leader-C (run learned), 2 = leader-F (run fallback).
class SetDueling {
 public:
  SetDueling(uint32_t n_sets, uint32_t n_L, uint32_t n_F, uint64_t hw_seed)
      : n_sets_(n_sets), n_L_(n_L), n_F_(n_F), rng_(hw_seed), tag_(n_sets, 0) {
    reseed();
  }
  void reseed() {
    std::vector<uint32_t> perm(n_sets_);
    for (uint32_t i = 0; i < n_sets_; ++i) perm[i] = i;
    std::shuffle(perm.begin(), perm.end(), rng_);
    std::fill(tag_.begin(), tag_.end(), 0);
    for (uint32_t i = 0; i < n_L_; ++i) tag_[perm[i]] = 1;
    for (uint32_t i = n_L_; i < n_L_ + n_F_; ++i) tag_[perm[i]] = 2;
    sumL_ = sumF_ = 0.0; cntL_ = cntF_ = 0;
  }
  inline uint8_t tag(uint32_t set) const { return tag_[set]; }
  // accumulate a bounded reward observed on `set` for the policy that actually
  // ran there (leader-C contributes to L, leader-F to F).
  inline void observe(uint32_t set, double reward) {
    uint8_t tg = tag_[set];
    if (tg == 1) { sumL_ += reward; ++cntL_; }
    else if (tg == 2) { sumF_ += reward; ++cntF_; }
  }
  // Δ̂ = r̄_L - r̄_F over the window; resets accumulators. model_based replaces
  // r̄_F by a model estimate (no leader-F) -> weakens Prop 6.2.
  double delta_hat(bool model_based, double model_q0) {
    double rL = cntL_ ? sumL_ / cntL_ : 0.0;
    double rF = model_based ? model_q0 : (cntF_ ? sumF_ / cntF_ : 0.0);
    last_rL_ = rL; last_rF_ = rF; last_cntL_ = cntL_; last_cntF_ = cntF_;
    sumL_ = sumF_ = 0.0; cntL_ = cntF_ = 0;
    return rL - rF;
  }
  // realized per-arm sample counts/means of the window just closed (for the
  // empirical resolution sigma_dhat = sqrt(rL(1-rL)/cntL + rF(1-rF)/cntF)).
  double last_rL() const { return last_rL_; }
  double last_rF() const { return last_rF_; }
  uint64_t last_cntL() const { return last_cntL_; }
  uint64_t last_cntF() const { return last_cntF_; }
  static double sigma_delta(double r_max, uint32_t m, uint32_t n_L, uint32_t n_F) {
    return std::sqrt((r_max * r_max / (4.0 * m)) * (1.0 / n_L + 1.0 / n_F));
  }
 private:
  uint32_t n_sets_, n_L_, n_F_;
  std::mt19937_64 rng_;
  std::vector<uint8_t> tag_;
  double sumL_ = 0, sumF_ = 0; uint64_t cntL_ = 0, cntF_ = 0;
  double last_rL_ = 0, last_rF_ = 0; uint64_t last_cntL_ = 0, last_cntF_ = 0;
};

// ---- gate FSM -------------------------------------------------------------
enum class Gate : uint8_t { TRUSTED = 0, SUSPECT = 1, GATED = 2, PROBING = 3 };

struct GateConfig {
  double tau = 0.05, delta_hys = 0.05;
  uint32_t T_clear = 5, T_dwell = 6, T_dwell_max = 24, T_reprobe = 4;
  double backoff_mult = 2.0;
};

class GateFSM {
 public:
  explicit GateFSM(GateConfig c) : c_(c), dwell_target_(c.T_dwell) {}
  Gate state() const { return s_; }
  bool C_active_everywhere() const { return s_ == Gate::TRUSTED || s_ == Gate::SUSPECT; }
  bool probing() const { return s_ == Gate::PROBING; }

  Gate step(bool tierA_escalate, bool tierA_clear, bool tierB_fired, double delta_hat) {
    switch (s_) {
      case Gate::TRUSTED:
        if (tierB_fired) { s_ = Gate::GATED; dwell_ = 0; }     // mimicry path
        else if (tierA_escalate) { s_ = Gate::SUSPECT; clear_ = 0; }
        break;
      case Gate::SUSPECT:
        if (tierB_fired) { s_ = Gate::GATED; dwell_ = 0; }
        else if (tierA_clear) { if (++clear_ >= c_.T_clear) s_ = Gate::TRUSTED; }
        else clear_ = 0;
        break;
      case Gate::GATED:
        if (++dwell_ >= dwell_target_) { s_ = Gate::PROBING; reprobe_ = 0; }
        break;
      case Gate::PROBING:
        if (delta_hat >= c_.tau + c_.delta_hys) {
          if (++reprobe_ >= c_.T_reprobe) { s_ = Gate::TRUSTED; dwell_target_ = c_.T_dwell; }
        } else if (delta_hat < c_.tau) {
          s_ = Gate::GATED; dwell_ = 0;
          dwell_target_ = std::min<uint32_t>(uint32_t(dwell_target_ * c_.backoff_mult), c_.T_dwell_max);
        } else reprobe_ = 0;
        break;
    }
    return s_;
  }
 private:
  GateConfig c_; Gate s_ = Gate::TRUSTED;
  uint32_t dwell_target_, clear_ = 0, dwell_ = 0, reprobe_ = 0;
};

// ---- top-level auditor ----------------------------------------------------
struct BouncerConfig {
  uint32_t n_sets = 2048, n_L = 32, n_F = 32, m = 64;
  double tau = 0.05, gamma_detect = 0.10, tierb_H = 0.8, r_max = 1.0;
  bool model_based = false; double model_q0 = 0.5;
  uint64_t hw_seed = 0xB0FFEEULL;
  double delta_hys = 0.05;   // PROBING re-trust band: re-trust when dhat >= tau+delta_hys
  bool reseed_enabled = true; // secret reseed each epoch; OFF == fixed leaders (DRRIP-style)
};

class Bouncer {
 public:
  explicit Bouncer(BouncerConfig c)
      : c_(c),
        dueling_(c.n_sets, c.n_L, c.n_F, c.hw_seed),
        tierb_(c.tau + c.gamma_detect / 2.0, c.tierb_H),
        gate_(GateConfig{c.tau, c.delta_hys}) {}

  // per-access hot path (off the datapath): O(1), a couple of adds.
  inline uint8_t pool_tag(uint32_t set) const { return dueling_.tag(set); }
  inline void observe(uint32_t set, double reward) { dueling_.observe(set, reward); }

  // per-window (epoch) confirmer, fired every ~10^5-10^6 cycles on the mgmt core.
  Gate end_window(bool tierA_escalate, bool tierA_clear) {
    double dh = dueling_.delta_hat(c_.model_based, c_.model_q0);
    bool fired = tierb_.update(dh);
    last_delta_hat_ = dh;
    Gate g = gate_.step(tierA_escalate, tierA_clear, fired, dh);
    if (c_.reseed_enabled) dueling_.reseed();   // secret reseed each epoch (OFF -> fixed leaders)
    return g;
  }
  bool use_learned(uint32_t set) const {
    // leaders are fixed; followers follow the gate
    uint8_t tg = dueling_.tag(set);
    if (tg == 1) return true;          // leader-C always learned
    if (tg == 2) return false;         // leader-F always fallback
    return gate_.C_active_everywhere();
  }
  double last_delta_hat() const { return last_delta_hat_; }
  double last_rL() const { return dueling_.last_rL(); }
  double last_rF() const { return dueling_.last_rF(); }
  uint64_t last_cntL() const { return dueling_.last_cntL(); }
  uint64_t last_cntF() const { return dueling_.last_cntF(); }
  // empirical per-window resolution of the dueling estimate (binomial s.e.).
  double sigma_dhat() const {
    double vL = dueling_.last_cntL() ? dueling_.last_rL() * (1.0 - dueling_.last_rL()) / dueling_.last_cntL() : 0.0;
    double vF = dueling_.last_cntF() ? dueling_.last_rF() * (1.0 - dueling_.last_rF()) / dueling_.last_cntF() : 0.0;
    return std::sqrt(vL + vF);
  }
  Gate state() const { return gate_.state(); }

 private:
  BouncerConfig c_;
  SetDueling dueling_;
  LowerCusum tierb_;
  GateFSM gate_;
  double last_delta_hat_ = 0.0;
};

}  // namespace bouncer
#endif
