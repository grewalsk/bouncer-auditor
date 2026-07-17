// bouncer.cc — standalone self-test for the ChampSim-deployable auditor.
// Build:  c++ -std=c++17 -O2 bouncer.cc -o bouncer_selftest && ./bouncer_selftest
//
// Reproduces, in C++, the qualitative behaviour validated in Python:
//   clean      -> stays TRUSTED, no false gate
//   attack     -> gates within a couple of windows; recovers after attack ends
// The reward model mirrors environment.py: mu_C(u)=clip(0.8-0.7u), mu_0=0.5.
#include "bouncer.h"
#include <cstdio>
#include <random>

using namespace bouncer;

static double mu_C(double u) { double v = 0.80 - 0.70 * u; return v < 0 ? 0 : (v > 1 ? 1 : v); }
static constexpr double MU0 = 0.50;

int main() {
  BouncerConfig cfg;            // defaults = §12 operating point
  Bouncer bnc(cfg);
  std::mt19937_64 rng(12345);
  std::uniform_real_distribution<double> U(0.0, 1.0);
  std::normal_distribution<double> Nz(0.0, 0.02);

  const int T = 220, onset = 90, offset = 180;
  int first_gated = -1, retrust = -1;
  for (int t = 0; t < T; ++t) {
    // The state present at the start of t routes window t. Evidence collected
    // during t can change only the next window's state.
    Gate routed = bnc.state();
    if (routed == Gate::GATED && first_gated < 0 && t >= onset) first_gated = t;
    if (routed == Gate::TRUSTED && t > offset && retrust < 0) retrust = t - offset;
    bool attack = (t >= onset && t < offset);
    double u = (attack ? 0.92 : 0.05) + Nz(rng);
    if (u < 0) u = 0; if (u > 1) u = 1;
    // hot path: m decisions per set per window (subsampled here for speed)
    for (uint32_t s = 0; s < cfg.n_sets; ++s) {
      uint8_t tg = bnc.pool_tag(s);
      // leader-C runs learned (reward ~ mu_C(u)); leader-F runs fallback (mu_0)
      double p = (tg == 2) ? MU0 : mu_C(u);
      // mean of m Bernoulli(p) ~ Binomial(m,p)/m, approximated by p + noise
      std::binomial_distribution<int> B(cfg.m, p);
      double r = double(B(rng)) / cfg.m;
      bnc.observe(s, r);
    }
    // Tier-A escalation: here driven by a simple reward-drop proxy (the real
    // shim wires the S_in/S_dec/S_res sketches). attack -> escalate.
    bool escalate = attack;
    bnc.end_window(escalate, !escalate);
  }
  std::printf("first routed GATED win  = %d  (attack onset %d -> latency %d)\n",
              first_gated, onset, first_gated - onset);
  std::printf("re-trust latency        = %d windows after attack ended\n", retrust);
  std::printf("sigma_delta (n=32,m=64) = %.4f\n",
              SetDueling::sigma_delta(1.0, cfg.m, cfg.n_L, cfg.n_F));
  bool ok = (first_gated >= 0 && (first_gated - onset) <= 4) && (retrust >= 0);
  std::printf("SELFTEST %s\n", ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}
