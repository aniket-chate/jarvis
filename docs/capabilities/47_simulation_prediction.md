# Capability 47: Simulation & Prediction

## 1. Overview & Purpose
Capability 47 empowers JARVIS to formulate mathematical simulations, execute Monte Carlo risk analyses, evaluate multi-scenario "what-if" models, and generate statistical forecasts with rigorous uncertainty bounds.

### Core Architectural Invariants:
- **Strict Epistemic Classification**: The capability enforces hard categorical distinction between:
  - `OBSERVED_FACT`: An empirically measured observation from perception or database.
  - `MODEL_OUTPUT`: The mathematical evaluation of a fitted model.
  - `SIMULATION_RESULT`: The outcome of forward computational dynamics under specified assumptions.
  - `PREDICTION`: An extrapolated probabilistic estimate across future time horizons.
  - `ASSUMPTION`: An unverified antecedent condition or hypothesis.
- **Rule: Never Present a Prediction as a Fact**: Every forecast explicitly embeds uncertainty intervals and epistemic warning disclaimers.
- **Zero Domain Hardcoding**: Operates on arbitrary targets, arbitrary variable names, arbitrary scenario structures, and dynamic step horizons.
- **Model Validation**: Computes standard performance metrics (MAE, RMSE, MAPE, $R^2$) prior to operational deployment.

---

## 2. Architecture & Analytical Pipeline
```
Input Historical Data / Scenario Hypotheses
                   ↓
Scenario Formulation & Variable Discovery
                   ↓
Model Selection & Baseline Calibration
                   ↓
Validation Metrics Assessment (MAE, RMSE, R²)
                   ↓
Deterministic / Stochastic Monte Carlo Execution
                   ↓
Confidence Interval & Uncertainty Propagation
                   ↓
Sensitivity Analysis & Parameter Elasticity
                   ↓
Epistemic Tagging & Natural Explanation
                   ↓
Persistent Provenance Trail
```

---

## 3. Supported Operations & Capability Contracts

| Capability Operation | Description | Epistemic Output |
| :--- | :--- | :--- |
| `simulation.define_scenario` | Declares variables, parameters, and assumptions | `ASSUMPTION` |
| `simulation.run_simulation` | Runs deterministic difference or Monte Carlo simulation | `SIMULATION_RESULT` |
| `simulation.forecast` | Trend projection with expanding confidence intervals | `PREDICTION` |
| `simulation.predict` | Target variable prediction with uncertainty bounds | `PREDICTION` |
| `simulation.validate_model` | Evaluates regression accuracy (MAE, RMSE, $R^2$) | `MODEL_OUTPUT` |
| `simulation.sensitivity_analysis` | Sweeps parameter across perturbations; computes elasticity | `MODEL_OUTPUT` |
| `simulation.compare_scenarios` | Quantifies variable deltas against baseline scenario | `ASSUMPTION` |
| `simulation.get_provenance` | Retrieves audit record and execution metadata | Audit Record |

---

## 4. Epistemic Tagging & Uncertainty Representation

### 4.1 Epistemic Warning Invariant
Any operation producing forward projections returns explicit epistemic warnings:
```json
{
  "target": "pressure_psi",
  "epistemic_tag": "PREDICTION",
  "epistemic_warning": "Predictions are probabilistic estimates based on historical trajectory; never present as guaranteed fact.",
  "assumptions": [
    "Underlying generating distribution exhibits stationarity across the forecast horizon",
    "Linear regression trend model minimizes mean squared residuals"
  ],
  "limitations": [
    "Confidence intervals expand non-linearly with step distance from t=N",
    "Exogenous macro shocks are not accounted for in univariate projection"
  ]
}
```

### 4.2 Non-Linear Confidence Expansion
Forecast confidence intervals are computed using residual standard errors where prediction variance expands with horizon distance:
$$SE_{pred}(x_h) = RSE \cdot \sqrt{1 + \frac{1}{n} + \frac{(x_h - \bar{x})^2}{\sum (x_i - \bar{x})^2}}$$
Upper and lower bounds widen truthfully as $x_h$ moves further into the future.

---

## 5. Security & Prompt Injection Defense
- **Scenario Assumption Sanitization**:
  Adversarial prompts embedded in scenario names, descriptions, or assumption text (`ignore previous instructions`, `system override`, `eval(`, `exec(`) are intercepted and quarantined prior to mathematical evaluation.
- **Execution Safeguards**:
  Monte Carlo iterations are bounded by `max_monte_carlo_trials` (default 10,000) to protect against algorithmic resource exhaustion attacks.

---

## 6. Provider Replaceability
`SimulationPredictionProvider` integrates seamlessly into `CapabilityIntelligence` via `BaseCapabilityProvider`. The underlying `StochasticSimulationBackend` can be swapped for alternative numeric engines (e.g. Scipy ODE solvers, PyMC Bayesian samplers, or external physics engines) without impacting JARVIS cognitive reasoning or task planning.
