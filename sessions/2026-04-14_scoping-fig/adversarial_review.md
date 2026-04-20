# Adversarial Review: Credit Cycle Position Monitor
# Date: 2026-04-14
# Status: CONDITIONAL VETO — two critical failures must be resolved before architecture begins

## Critical Failures (veto-level)

### 1. Latent variable model is unidentifiable from available data
The Kalman/particle filter approach requires fitting transition dynamics and observation model parameters. Available training data: ~4 complete credit cycles since 1990. A model with any non-trivial parameterization will be severely overfit. Out-of-sample performance is statistically unreliable.

This is not an engineering problem — it is a statistical identification problem.

**Minimum bar to lift:** Either (a) abandon latent variable framing entirely in favor of an ensemble of directly observable sub-indicators, or (b) use a heavily constrained model with theory-grounded priors and document exactly what assumptions are baked in.

### 2. "Credit cycle" is not a single scalar
Consumer credit, leveraged loans, CRE, and IG corporates cycle independently on different timescales. A single scalar cycle score is actively misleading during periods when sub-markets diverge.

**Minimum bar to lift:** Output must be multi-dimensional — sector-specific sub-indicators — not a single score.

---

## Significant Risks (non-blocking)

### 3. Data vintage problem invalidates backtest
Slow signals (FDIC delinquency, loan growth) have revision histories. Current-vintage data differs from what was available in real-time. Backtesting with revised data = look-ahead bias.
**Mitigation:** Use FRED vintage-specific data releases. Point-in-time data must be a first-class design constraint from day one.

### 4. Real-time requirement may be unjustified
PE exit decisions happen over weeks to months. Sub-second vs. daily credit spread updates has zero marginal value for this use case. If real-time is unjustified, the systems complexity loses its motivation and becomes complexity theater.
**Mitigation:** Define actual required latency from use case. Hypothesis: daily updates are sufficient.

### 5. Policy intervention regimes break historical signal relationships
Post-2008 Fed intervention (QE, emergency facilities) suspended historical spread-cycle relationships repeatedly. A model trained on pre-QE history produces wrong outputs when policy acts. This happens precisely when correct outputs matter most.

---

## Hidden Assumptions
1. Credit cycle dynamics are stationary across pre- and post-QE regimes (false)
2. Signal lead/lag relationships are fixed (false — regime-conditional)
3. Stone Point would use this tool for exit decisions (organizational assumption, unverified)
4. "Real-time" adds value over daily (unexamined, likely false for this use case)

## Competitive Reality Check
- Bridgewater's economic machine framework covers this space (40 years of development)
- AQR published business cycle timing research extensively
- Chicago Fed NFCI, Kansas City FSCI, Bloomberg ECON function exist publicly
- Key question: why hasn't Stone Point built this already? Must have a clear answer.

## Honest Hiring Committee Critique
"You fit a latent variable model on 4 credit cycles. What does this tell you that the Chicago Fed NFCI doesn't, and how do you know it works when the next cycle doesn't look like the last four?"

---

## Resolution: What Lifts the Veto

1. **Replace latent variable with observable sub-indicator dashboard:**
   - Bank funding stress: bank CDS, Libor-OIS equivalent
   - Consumer credit stress: credit card + auto delinquency rates
   - CRE stress: CMBS spreads, office vacancy rates
   - Corporate credit: IG/HY spread differential, leveraged loan prices
   - Output = interpretable vector, not black-box scalar

2. **Redefine "real-time" honestly:**
   - Credit spreads: daily (not milliseconds)
   - Delinquency data: monthly, ingested as filed
   - Architecture handles heterogeneous update cadence correctly
   - No pretending anything needs to be faster than the use case requires

3. **Backtest with point-in-time data only:**
   - Use FRED vintage releases
   - Mark which signals were available in real-time vs. required revised data
   - Show outputs at Q3 2007, Q1 2020, Q4 2022 using only contemporaneously available data

4. **Scope the claim correctly:**
   - Not: "exit timing tool"
   - Yes: "early warning system for credit stress conditions affecting FIG portfolio companies"
