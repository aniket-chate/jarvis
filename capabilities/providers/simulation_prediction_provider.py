"""Capability 47: Simulation & Prediction Provider.

Provides structured mathematical simulation, Monte Carlo uncertainty analysis,
predictive forecasting, what-if comparison, model validation, and sensitivity testing:
- Generic scenario definitions with arbitrary labels (no hardcoded scenario names)
- Deterministic iterative difference simulation
- Stochastic Monte Carlo simulation with empirical confidence intervals
- Predictive trend forecasting with explicit uncertainty bounds
- Sensitivity analysis calculating parameter elasticity
- Model validation reporting MAE, RMSE, and R-squared
- Strict epistemic tagging: OBSERVED_FACT vs MODEL_OUTPUT vs SIMULATION_RESULT vs PREDICTION vs ASSUMPTION
- Rule: Never present a prediction as a fact.
- Provenance, assumptions, and limitations tracking on all outputs
- Security: Prompt injection quarantine on scenario definitions
- Zero domain-specific hardcoding: operates on arbitrary targets and variables
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import math
from pathlib import Path
import random
import re
import statistics
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata

logger = logging.getLogger("JARVIS.Capabilities.Providers.Simulation")


class EpistemicCategory(str, Enum):
    OBSERVED_FACT = "OBSERVED_FACT"
    MODEL_OUTPUT = "MODEL_OUTPUT"
    SIMULATION_RESULT = "SIMULATION_RESULT"
    PREDICTION = "PREDICTION"
    ASSUMPTION = "ASSUMPTION"


@dataclass
class SimulationConfig:
    """Runtime configuration for Simulation & Prediction Provider."""
    default_monte_carlo_trials: int = 200
    max_monte_carlo_trials: int = 10_000
    confidence_level: float = 0.95
    default_forecast_horizon: int = 5
    quarantine_prompt_injections: bool = True
    random_seed: Optional[int] = 42


@dataclass
class ScenarioDefinition:
    """Generic description of a simulation scenario."""
    scenario_id: str
    name: str
    variables: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "variables": dict(self.variables),
            "parameters": dict(self.parameters),
            "assumptions": list(self.assumptions),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


# -----------------------------------------------------------------------------
# Provider Abstraction: Simulation Backend Interface
# -----------------------------------------------------------------------------

class SimulationBackend(ABC):
    """Abstract interface for simulation computation backends."""

    @abstractmethod
    def run_deterministic(
        self,
        variables: Dict[str, float],
        steps: int,
        step_delta: Dict[str, float],
    ) -> List[Dict[str, float]]:
        pass

    @abstractmethod
    def run_stochastic(
        self,
        base_variables: Dict[str, float],
        noise_std: Dict[str, float],
        trials: int,
        steps: int,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def forecast(
        self,
        history: List[float],
        horizon: int,
        confidence_level: float,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def validate_model(
        self,
        actuals: List[float],
        predicted: List[float],
    ) -> Dict[str, float]:
        pass

    @abstractmethod
    def sensitivity_analysis(
        self,
        base_variables: Dict[str, float],
        target_expression: Callable[[Dict[str, float]], float],
        parameter_to_sweep: str,
        sweep_percentages: List[float],
    ) -> Dict[str, Any]:
        pass


class StochasticSimulationBackend(SimulationBackend):
    """Deterministic-ready stochastic backend for Monte Carlo and predictive math."""

    def __init__(self, seed: Optional[int] = 42):
        self._seed = seed

    def run_deterministic(
        self,
        variables: Dict[str, float],
        steps: int,
        step_delta: Dict[str, float],
    ) -> List[Dict[str, float]]:
        trajectory = []
        current = dict(variables)
        for s in range(steps):
            pt = {"step": s}
            for k, v in current.items():
                pt[k] = round(v, 4)
                # Apply step delta
                delta = step_delta.get(k, 0.0)
                current[k] += delta
            trajectory.append(pt)
        return trajectory

    def run_stochastic(
        self,
        base_variables: Dict[str, float],
        noise_std: Dict[str, float],
        trials: int = 200,
        steps: int = 10,
    ) -> Dict[str, Any]:
        rng = random.Random(self._seed)
        var_trials: Dict[str, List[List[float]]] = {k: [] for k in base_variables}

        for _ in range(trials):
            curr = dict(base_variables)
            trial_traj: Dict[str, List[float]] = {k: [v] for k, v in curr.items()}
            for _ in range(steps):
                for k in base_variables:
                    std = noise_std.get(k, 0.05 * abs(curr[k]) if curr[k] != 0 else 0.1)
                    noise = rng.gauss(0.0, std)
                    curr[k] += noise
                    trial_traj[k].append(curr[k])
            for k in base_variables:
                var_trials[k].append(trial_traj[k])

        # Compute summary statistics across trials per step
        summary: Dict[str, List[Dict[str, float]]] = {k: [] for k in base_variables}
        for k in base_variables:
            for step_idx in range(steps + 1):
                vals = [var_trials[k][t][step_idx] for t in range(trials)]
                vals.sort()
                n = len(vals)
                mean_v = statistics.mean(vals)
                std_v = statistics.stdev(vals) if n > 1 else 0.0
                p5 = vals[int(n * 0.05)]
                p25 = vals[int(n * 0.25)]
                p50 = vals[int(n * 0.50)]
                p75 = vals[int(n * 0.75)]
                p95 = vals[int(n * 0.95)]
                summary[k].append({
                    "step": step_idx,
                    "mean": round(mean_v, 4),
                    "std": round(std_v, 4),
                    "lower_95_ci": round(p5, 4),
                    "upper_95_ci": round(p95, 4),
                    "median": round(p50, 4),
                    "q25": round(p25, 4),
                    "q75": round(p75, 4),
                })

        return {
            "trials": trials,
            "steps": steps,
            "summary": summary,
        }

    def forecast(
        self,
        history: List[float],
        horizon: int = 5,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        if len(history) < 2:
            return {"error": "Need at least 2 historical observations to forecast"}

        n = len(history)
        xs = list(range(n))
        ys = history

        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(ys)

        denom = sum((x - mean_x) ** 2 for x in xs)
        if denom == 0:
            slope = 0.0
            intercept = mean_y
        else:
            slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
            intercept = mean_y - slope * mean_x

        # Residual standard error
        residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
        rse = math.sqrt(sum(r ** 2 for r in residuals) / (n - 2)) if n > 2 else 0.5

        # Normal critical value approx for 95% CI is 1.96
        z_crit = 1.96 if confidence_level >= 0.95 else 1.645

        forecast_points = []
        for step in range(1, horizon + 1):
            future_x = n - 1 + step
            predicted_y = intercept + slope * future_x
            # Variance expands with prediction horizon
            se_pred = rse * math.sqrt(1 + 1/n + ((future_x - mean_x) ** 2) / denom) if denom > 0 else rse
            lower_bound = predicted_y - z_crit * se_pred
            upper_bound = predicted_y + z_crit * se_pred

            forecast_points.append({
                "step": step,
                "predicted_value": round(predicted_y, 4),
                "lower_bound": round(lower_bound, 4),
                "upper_bound": round(upper_bound, 4),
                "uncertainty_interval": round(upper_bound - lower_bound, 4),
                "epistemic_tag": EpistemicCategory.PREDICTION.value,
            })

        return {
            "horizon": horizon,
            "historical_count": n,
            "slope": round(slope, 4),
            "intercept": round(intercept, 4),
            "residual_standard_error": round(rse, 4),
            "forecast_points": forecast_points,
            "epistemic_tag": EpistemicCategory.PREDICTION.value,
        }

    def validate_model(
        self,
        actuals: List[float],
        predicted: List[float],
    ) -> Dict[str, float]:
        if len(actuals) != len(predicted) or not actuals:
            return {"error": "Lengths of actuals and predicted must match and not be empty"}

        n = len(actuals)
        errors = [p - a for a, p in zip(actuals, predicted)]
        abs_errors = [abs(e) for e in errors]
        sq_errors = [e ** 2 for e in errors]

        mae = statistics.mean(abs_errors)
        rmse = math.sqrt(statistics.mean(sq_errors))

        # MAPE (avoiding division by zero)
        non_zero_pairs = [(a, abs(e)) for a, e in zip(actuals, errors) if a != 0]
        mape = (statistics.mean(err / abs(a) for a, err in non_zero_pairs) * 100.0) if non_zero_pairs else 0.0

        # R-squared
        mean_a = statistics.mean(actuals)
        ss_tot = sum((a - mean_a) ** 2 for a in actuals)
        ss_res = sum(sq_errors)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "mape": round(mape, 2),
            "r_squared": round(r2, 4),
            "sample_size": n,
        }

    def sensitivity_analysis(
        self,
        base_variables: Dict[str, float],
        target_expression: Callable[[Dict[str, float]], float],
        parameter_to_sweep: str,
        sweep_percentages: List[float],
    ) -> Dict[str, Any]:
        if parameter_to_sweep not in base_variables:
            return {"error": f"Parameter '{parameter_to_sweep}' not found in base variables"}

        base_val = base_variables[parameter_to_sweep]
        base_output = target_expression(base_variables)

        sweep_results = []
        for pct in sweep_percentages:
            mult = 1.0 + (pct / 100.0)
            swept_vars = dict(base_variables)
            swept_val = base_val * mult
            swept_vars[parameter_to_sweep] = swept_val
            output_val = target_expression(swept_vars)

            output_pct_change = ((output_val - base_output) / base_output * 100.0) if base_output != 0 else 0.0
            elasticity = (output_pct_change / pct) if pct != 0 else 1.0

            sweep_results.append({
                "sweep_percent": pct,
                "input_value": round(swept_val, 4),
                "output_value": round(output_val, 4),
                "output_percent_change": round(output_pct_change, 2),
                "elasticity": round(elasticity, 4),
            })

        return {
            "parameter_swept": parameter_to_sweep,
            "base_parameter_value": base_val,
            "base_output": round(base_output, 4),
            "sweep_results": sweep_results,
        }


# -----------------------------------------------------------------------------
# Capability 47 Provider Implementation
# -----------------------------------------------------------------------------

class SimulationPredictionProvider(BaseCapabilityProvider):
    """Capability 47: Simulation & Prediction Provider."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"state\s+prediction\s+as\s+fact", re.IGNORECASE),
        re.compile(r"treat\s+simulation\s+as\s+certainty", re.IGNORECASE),
    ]

    def __init__(
        self,
        config: Optional[SimulationConfig] = None,
        backend: Optional[SimulationBackend] = None,
    ):
        self.config = config or SimulationConfig()
        self.backend = backend or StochasticSimulationBackend(seed=self.config.random_seed)
        self._scenarios: Dict[str, ScenarioDefinition] = {}
        self._provenance_records: Dict[str, Dict[str, Any]] = {}

        metadata = ProviderMetadata(
            provider_id="provider.simulation.prediction_engine",
            name="Simulation & Prediction Provider",
            supported_capabilities=[
                "simulation.define_scenario",
                "simulation.run_simulation",
                "simulation.run_what_if",
                "simulation.predict",
                "simulation.forecast",
                "simulation.validate_model",
                "simulation.sensitivity_analysis",
                "simulation.compare_scenarios",
                "simulation.get_provenance",
            ],
            priority=10,
            estimated_latency_ms=20.0,
            safety_level="read_only",
            device_target="local",
            description="Statistical simulation, predictive bounds, and scenario evaluation engine.",
        )
        super().__init__(metadata)

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        t0 = time.perf_counter()

        # Prompt injection quarantine
        param_str = json.dumps(parameters)
        for pat in self.PROMPT_INJECTION_PATTERNS:
            if pat.search(param_str):
                logger.warning("[SimulationPredictionProvider] Prompt injection detected: %s", pat.pattern)
                return ActionResult(
                    status="FAILED",
                    action=capability,
                    provider_id=self.provider_id,
                    output={"error": f"Security refusal: prompt injection pattern detected ({pat.pattern})"},
                    message="Security refusal: prompt injection quarantined",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

        if capability == "simulation.define_scenario":
            return self._define_scenario(parameters, t0)
        elif capability in ["simulation.run_simulation", "simulation.run_what_if"]:
            return self._run_simulation(parameters, t0, capability)
        elif capability in ["simulation.predict", "simulation.forecast"]:
            return self._forecast(parameters, t0, capability)
        elif capability == "simulation.validate_model":
            return self._validate_model(parameters, t0)
        elif capability == "simulation.sensitivity_analysis":
            return self._sensitivity_analysis(parameters, t0)
        elif capability == "simulation.compare_scenarios":
            return self._compare_scenarios(parameters, t0)
        elif capability == "simulation.get_provenance":
            return self._get_provenance(parameters, t0)
        else:
            return ActionResult(
                status="FAILED",
                action=capability,
                provider_id=self.provider_id,
                output={"error": f"Unsupported simulation capability '{capability}'"},
                message="Operation not implemented",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    # -------------------------------------------------------------------------
    # Internal Handlers
    # -------------------------------------------------------------------------

    def _define_scenario(self, params: Dict[str, Any], t0: float) -> ActionResult:
        scenario_id = params.get("scenario_id", f"scen_{uuid.uuid4().hex[:8]}")
        name = params.get("name", "Generic Scenario")
        variables = params.get("variables", {})
        assumptions = params.get("assumptions", [
            "Baseline linear dynamics hold over simulation interval",
            "Exogenous variables assumed constant unless perturbed",
        ])

        scen = ScenarioDefinition(
            scenario_id=scenario_id,
            name=name,
            variables={k: float(v) for k, v in variables.items()},
            parameters=params.get("parameters", {}),
            assumptions=assumptions,
            metadata=params.get("metadata", {}),
        )

        self._scenarios[scenario_id] = scen
        return ActionResult(
            status="SUCCESS",
            action="simulation.define_scenario",
            provider_id=self.provider_id,
            output={
                "scenario_id": scenario_id,
                "scenario": scen.to_dict(),
                "epistemic_tag": EpistemicCategory.ASSUMPTION.value,
            },
            message=f"Scenario '{scenario_id}' defined successfully",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _run_simulation(self, params: Dict[str, Any], t0: float, action: str) -> ActionResult:
        mode = params.get("mode", "stochastic").lower()
        steps = params.get("steps", 10)
        scen_id = params.get("scenario_id")

        base_vars = {}
        if scen_id and scen_id in self._scenarios:
            base_vars = dict(self._scenarios[scen_id].variables)
        elif "variables" in params:
            base_vars = {k: float(v) for k, v in params["variables"].items()}

        if not base_vars:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": "No variables provided or scenario not found"},
                message="Variables missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        sim_id = f"sim_{uuid.uuid4().hex[:8]}"

        if mode == "deterministic":
            step_delta = {k: float(v) for k, v in params.get("step_delta", {}).items()}
            trajectory = self.backend.run_deterministic(base_vars, steps, step_delta)
            result = {
                "simulation_id": sim_id,
                "mode": "deterministic",
                "steps": steps,
                "trajectory": trajectory,
                "epistemic_tag": EpistemicCategory.SIMULATION_RESULT.value,
                "epistemic_note": "Deterministic simulation result conditional upon fixed step deltas",
            }
        else:
            trials = min(self.config.max_monte_carlo_trials, params.get("trials", self.config.default_monte_carlo_trials))
            noise_std = {k: float(v) for k, v in params.get("noise_std", {}).items()}
            stoch_res = self.backend.run_stochastic(base_vars, noise_std, trials=trials, steps=steps)
            result = {
                "simulation_id": sim_id,
                "mode": "stochastic_monte_carlo",
                "trials": trials,
                "steps": steps,
                "results": stoch_res["summary"],
                "epistemic_tag": EpistemicCategory.SIMULATION_RESULT.value,
                "epistemic_note": "Stochastic Monte Carlo simulation result; bounds reflect 95% empirical confidence",
            }

        self._provenance_records[sim_id] = {
            "simulation_id": sim_id,
            "action": action,
            "base_variables": base_vars,
            "mode": mode,
            "timestamp": time.time(),
        }

        return ActionResult(
            status="SUCCESS",
            action=action,
            provider_id=self.provider_id,
            output=result,
            message=f"Simulation executed ({mode}, {steps} steps)",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _forecast(self, params: Dict[str, Any], t0: float, action: str) -> ActionResult:
        history = params.get("history", [])
        horizon = params.get("horizon", self.config.default_forecast_horizon)
        target_name = params.get("target_name", "target")

        if len(history) < 2:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": "Insufficient history: need at least 2 observations to forecast"},
                message="Insufficient observations",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        numeric_history = []
        for h in history:
            try:
                numeric_history.append(float(h))
            except (ValueError, TypeError):
                pass

        res = self.backend.forecast(numeric_history, horizon=horizon, confidence_level=self.config.confidence_level)
        if "error" in res:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output=res,
                message=res["error"],
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        pred_id = f"pred_{uuid.uuid4().hex[:8]}"
        output = {
            "prediction_id": pred_id,
            "target": target_name,
            "forecast": res,
            "epistemic_tag": EpistemicCategory.PREDICTION.value,
            "epistemic_warning": "Predictions are probabilistic estimates based on historical trajectory; never present as guaranteed fact.",
            "assumptions": [
                "Underlying generating distribution exhibits stationarity across the forecast horizon",
                "Linear regression trend model minimizes mean squared residuals",
            ],
            "limitations": [
                f"Confidence intervals expand non-linearly with step distance from t={len(numeric_history)}",
                "Exogenous macro shocks are not accounted for in univariate projection",
            ],
            "timestamp": time.time(),
        }

        self._provenance_records[pred_id] = {
            "prediction_id": pred_id,
            "target": target_name,
            "sample_size": len(numeric_history),
            "horizon": horizon,
            "timestamp": time.time(),
        }

        return ActionResult(
            status="SUCCESS",
            action=action,
            provider_id=self.provider_id,
            output=output,
            message=f"Generated {horizon}-step prediction with confidence intervals for '{target_name}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _validate_model(self, params: Dict[str, Any], t0: float) -> ActionResult:
        actuals = params.get("actuals", [])
        predicted = params.get("predicted", [])

        if not actuals or not predicted:
            return ActionResult(
                status="FAILED",
                action="simulation.validate_model",
                provider_id=self.provider_id,
                output={"error": "actuals and predicted lists are required and cannot be empty"},
                message="Validation data missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        report = self.backend.validate_model(
            [float(a) for a in actuals],
            [float(p) for p in predicted],
        )

        return ActionResult(
            status="SUCCESS",
            action="simulation.validate_model",
            provider_id=self.provider_id,
            output={
                "validation_report": report,
                "epistemic_tag": EpistemicCategory.MODEL_OUTPUT.value,
            },
            message=f"Model validation completed (MAE={report.get('mae')}, R2={report.get('r_squared')})",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _sensitivity_analysis(self, params: Dict[str, Any], t0: float) -> ActionResult:
        scen_id = params.get("scenario_id")
        base_vars = {}
        if scen_id and scen_id in self._scenarios:
            base_vars = dict(self._scenarios[scen_id].variables)
        elif "variables" in params:
            base_vars = {k: float(v) for k, v in params["variables"].items()}

        param_to_sweep = params.get("parameter")
        if not param_to_sweep or param_to_sweep not in base_vars:
            return ActionResult(
                status="FAILED",
                action="simulation.sensitivity_analysis",
                provider_id=self.provider_id,
                output={"error": f"Parameter '{param_to_sweep}' not found in variables"},
                message="Sweep parameter not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        sweep_pcts = params.get("percentages", [-20.0, -10.0, 0.0, 10.0, 20.0])

        # Target expression: either formula or sum of variables
        formula = params.get("formula")
        if formula == "sum":
            expr = lambda v: sum(v.values())
        elif formula == "product":
            expr = lambda v: math.prod(v.values())
        else:
            # Default linear sum with weights
            weights = params.get("weights", {})
            expr = lambda v: sum(v.get(k, 0.0) * weights.get(k, 1.0) for k in v)

        res = self.backend.sensitivity_analysis(base_vars, expr, param_to_sweep, sweep_pcts)

        return ActionResult(
            status="SUCCESS",
            action="simulation.sensitivity_analysis",
            provider_id=self.provider_id,
            output={
                "sensitivity": res,
                "epistemic_tag": EpistemicCategory.MODEL_OUTPUT.value,
            },
            message=f"Completed sensitivity sweep for '{param_to_sweep}' across {len(sweep_pcts)} perturbations",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _compare_scenarios(self, params: Dict[str, Any], t0: float) -> ActionResult:
        scenario_ids = params.get("scenario_ids")
        if not scenario_ids:
            base_id = params.get("baseline_scenario_id")
            alt_ids = params.get("alternative_scenario_ids", [])
            if base_id:
                scenario_ids = [base_id] + list(alt_ids)
            else:
                scenario_ids = []

        if len(scenario_ids) < 2:
            return ActionResult(
                status="FAILED",
                action="simulation.compare_scenarios",
                provider_id=self.provider_id,
                output={"error": "At least 2 scenario_ids required for comparison"},
                message="Insufficient scenarios",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        scenarios = []
        for sid in scenario_ids:
            if sid in self._scenarios:
                scenarios.append(self._scenarios[sid])
            else:
                return ActionResult(
                    status="FAILED",
                    action="simulation.compare_scenarios",
                    provider_id=self.provider_id,
                    output={"error": f"Scenario '{sid}' not found"},
                    message=f"Scenario '{sid}' missing",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

        baseline = scenarios[0]
        comparisons = []
        for s in scenarios[1:]:
            var_diffs = {}
            for k in set(list(baseline.variables.keys()) + list(s.variables.keys())):
                b_val = baseline.variables.get(k, 0.0)
                s_val = s.variables.get(k, 0.0)
                delta = s_val - b_val
                pct = ((delta / b_val) * 100.0) if b_val != 0 else 0.0
                var_diffs[k] = {"baseline": b_val, "scenario": s_val, "delta": round(delta, 4), "pct_change": round(pct, 2)}

            comparisons.append({
                "scenario_id": s.scenario_id,
                "name": s.name,
                "variable_diffs": var_diffs,
                "assumption_diffs": list(set(s.assumptions) - set(baseline.assumptions)),
            })

        return ActionResult(
            status="SUCCESS",
            action="simulation.compare_scenarios",
            provider_id=self.provider_id,
            output={
                "baseline": baseline.to_dict(),
                "baseline_id": baseline.scenario_id,
                "comparisons": {c["scenario_id"]: c for c in comparisons},
                "epistemic_tag": EpistemicCategory.ASSUMPTION.value,
            },
            message=f"Compared {len(comparisons)} scenario(s) against baseline '{baseline.scenario_id}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _get_provenance(self, params: Dict[str, Any], t0: float) -> ActionResult:
        rec_id = params.get("id") or params.get("record_id")
        if not rec_id or rec_id not in self._provenance_records:
            return ActionResult(
                status="FAILED",
                action="simulation.get_provenance",
                provider_id=self.provider_id,
                output={"error": f"Provenance record for id '{rec_id}' not found"},
                message="Record not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        return ActionResult(
            status="SUCCESS",
            action="simulation.get_provenance",
            provider_id=self.provider_id,
            output={"record": self._provenance_records[rec_id]},
            message=f"Retrieved provenance record for '{rec_id}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )


simulation_prediction_provider = SimulationPredictionProvider()
