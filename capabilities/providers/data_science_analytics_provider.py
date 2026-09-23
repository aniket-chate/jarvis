"""Capability 46: Data Science & Analytics Provider.

Provides robust, data-driven structured data inspection, profiling, transformation,
statistical analysis, anomaly detection, visualization specification, and explanation:
- Generic tabular dataset ingestion (CSV, JSON, records)
- Schema discovery & automatic type inference
- Data quality, missingness, and duplicate analysis
- Descriptive statistics, aggregations, multi-column grouping, filtering, sorting
- Pearson correlation matrix and distribution histograms
- Outlier detection via IQR and z-score methods
- Transformations: imputation, scaling, normalization, deduplication, derived columns
- Structured chart specifications (bar, line, scatter, histogram, box)
- Explanations explicitly distinguishing CORRELATION from CAUSATION
- Strict data provenance tracking
- Security: untrusted cell quarantine; cell contents are NEVER executed
- Zero domain-specific hardcoding: operates on arbitrary schemas and columns
"""

from abc import ABC, abstractmethod
import csv
from dataclasses import dataclass, field
from datetime import datetime
import io
import json
import logging
import math
from pathlib import Path
import re
import statistics
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata

logger = logging.getLogger("JARVIS.Capabilities.Providers.DataScience")


@dataclass
class AnalyticsConfig:
    """Runtime configuration for Data Science & Analytics Provider."""
    max_dataset_rows: int = 100_000
    default_outlier_z_score: float = 3.0
    default_iqr_multiplier: float = 1.5
    correlation_sample_limit: int = 10_000
    histogram_default_bins: int = 10
    quarantine_prompt_injections: bool = True


@dataclass
class ColumnProfile:
    """Statistical and structural profile of a single dataset column."""
    name: str
    inferred_type: str  # "integer", "float", "boolean", "datetime", "string", "null"
    total_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "inferred_type": self.inferred_type,
            "total_count": self.total_count,
            "null_count": self.null_count,
            "null_percentage": round(self.null_percentage, 2),
            "unique_count": self.unique_count,
            "stats": dict(self.stats),
        }


@dataclass
class DatasetProfile:
    """Comprehensive quality and schema profile of a dataset."""
    dataset_id: str
    row_count: int
    column_count: int
    columns: Dict[str, ColumnProfile]
    duplicate_row_count: int
    duplicate_percentage: float
    memory_estimate_bytes: int
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": {k: v.to_dict() for k, v in self.columns.items()},
            "duplicate_row_count": self.duplicate_row_count,
            "duplicate_percentage": round(self.duplicate_percentage, 2),
            "memory_estimate_bytes": self.memory_estimate_bytes,
            "created_at": self.created_at,
        }


# -----------------------------------------------------------------------------
# Provider Abstraction: Analytics Backend Interface
# -----------------------------------------------------------------------------

class AnalyticsBackend(ABC):
    """Abstract interface for data science computation backends."""

    @abstractmethod
    def load_dataset(self, dataset_id: str, raw_data: Any, format_hint: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        pass

    @abstractmethod
    def profile_dataset(self, dataset_id: str, columns: List[str], rows: List[Dict[str, Any]]) -> DatasetProfile:
        pass

    @abstractmethod
    def compute_stats(self, rows: List[Dict[str, Any]], column: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def compute_correlations(self, rows: List[Dict[str, Any]], numeric_cols: List[str]) -> Dict[str, Dict[str, float]]:
        pass

    @abstractmethod
    def detect_outliers(self, rows: List[Dict[str, Any]], column: str, method: str) -> Dict[str, Any]:
        pass


class PurePythonAnalyticsBackend(AnalyticsBackend):
    """Pure Python + math/statistics analytics backend with zero external dependencies."""

    def load_dataset(self, dataset_id: str, raw_data: Any, format_hint: str = "auto") -> Tuple[List[str], List[Dict[str, Any]]]:
        if isinstance(raw_data, list):
            if not raw_data:
                return [], []
            if isinstance(raw_data[0], dict):
                cols = list(raw_data[0].keys())
                # Normalize all rows to have these columns
                rows = [{c: r.get(c) for c in cols} for r in raw_data if isinstance(r, dict)]
                return cols, rows
            elif isinstance(raw_data[0], list):
                # First row is header
                cols = [str(c) for c in raw_data[0]]
                rows = []
                for row_vals in raw_data[1:]:
                    row_dict = {cols[i]: (row_vals[i] if i < len(row_vals) else None) for i in range(len(cols))}
                    rows.append(row_dict)
                return cols, rows

        elif isinstance(raw_data, dict):
            # Column-oriented dict: {"col1": [...], "col2": [...]}
            cols = list(raw_data.keys())
            if not cols:
                return [], []
            lengths = [len(raw_data[c]) for c in cols if isinstance(raw_data[c], list)]
            row_count = max(lengths) if lengths else 0
            rows = []
            for i in range(row_count):
                row = {c: (raw_data[c][i] if isinstance(raw_data[c], list) and i < len(raw_data[c]) else None) for c in cols}
                rows.append(row)
            return cols, rows

        elif isinstance(raw_data, str):
            # Parse CSV text
            text = raw_data.strip()
            if not text:
                return [], []
            reader = csv.reader(io.StringIO(text))
            try:
                header = next(reader)
            except StopIteration:
                return [], []
            cols = [h.strip() for h in header]
            rows = []
            for r in reader:
                if not r:
                    continue
                row_dict = {}
                for i, col in enumerate(cols):
                    val = r[i].strip() if i < len(r) else None
                    # Type parse basic values
                    if val is None or val == "" or val.lower() in ["none", "null", "nan"]:
                        parsed_val = None
                    elif val.lower() == "true":
                        parsed_val = True
                    elif val.lower() == "false":
                        parsed_val = False
                    else:
                        try:
                            parsed_val = int(val)
                        except ValueError:
                            try:
                                parsed_val = float(val)
                            except ValueError:
                                parsed_val = val
                    row_dict[col] = parsed_val
                rows.append(row_dict)
            return cols, rows

        raise ValueError(f"Unsupported dataset input type: {type(raw_data).__name__}")

    def profile_dataset(self, dataset_id: str, columns: List[str], rows: List[Dict[str, Any]]) -> DatasetProfile:
        total_rows = len(rows)
        col_profiles = {}

        for col in columns:
            vals = [r.get(col) for r in rows]
            non_null = [v for v in vals if v is not None]
            null_count = total_rows - len(non_null)
            null_pct = (null_count / total_rows * 100.0) if total_rows > 0 else 0.0

            # Infer type
            inferred_type = "null"
            if non_null:
                sample = non_null[:100]
                if all(isinstance(v, bool) for v in sample):
                    inferred_type = "boolean"
                elif all(isinstance(v, int) for v in sample):
                    inferred_type = "integer"
                elif all(isinstance(v, (int, float)) for v in sample):
                    inferred_type = "float"
                else:
                    # Check ISO datetime
                    dt_count = 0
                    for v in sample:
                        if isinstance(v, str) and len(v) >= 10:
                            try:
                                datetime.fromisoformat(v.replace("Z", "+00:00"))
                                dt_count += 1
                            except Exception:
                                pass
                    if dt_count > len(sample) * 0.8:
                        inferred_type = "datetime"
                    else:
                        inferred_type = "string"

            # Compute column statistics
            stats = {}
            unique_vals = set()
            try:
                for v in non_null:
                    unique_vals.add(str(v))
            except Exception:
                pass

            if inferred_type in ["integer", "float"] and non_null:
                numeric_vals = [float(v) for v in non_null]
                numeric_vals.sort()
                n = len(numeric_vals)
                mean_val = statistics.mean(numeric_vals)
                std_val = statistics.stdev(numeric_vals) if n > 1 else 0.0
                median_val = statistics.median(numeric_vals)
                q1 = numeric_vals[int(n * 0.25)]
                q3 = numeric_vals[int(n * 0.75)]
                stats = {
                    "min": numeric_vals[0],
                    "max": numeric_vals[-1],
                    "mean": round(mean_val, 4),
                    "median": round(median_val, 4),
                    "std": round(std_val, 4),
                    "q25": q1,
                    "q75": q3,
                    "iqr": round(q3 - q1, 4),
                }

            col_profiles[col] = ColumnProfile(
                name=col,
                inferred_type=inferred_type,
                total_count=total_rows,
                null_count=null_count,
                null_percentage=null_pct,
                unique_count=len(unique_vals),
                stats=stats,
            )

        # Estimate duplicates
        seen_rows = set()
        duplicate_count = 0
        for r in rows:
            try:
                row_key = json.dumps(r, sort_keys=True)
                if row_key in seen_rows:
                    duplicate_count += 1
                else:
                    seen_rows.add(row_key)
            except Exception:
                pass

        dup_pct = (duplicate_count / total_rows * 100.0) if total_rows > 0 else 0.0
        mem_bytes = sum(len(str(r)) for r in rows)

        return DatasetProfile(
            dataset_id=dataset_id,
            row_count=total_rows,
            column_count=len(columns),
            columns=col_profiles,
            duplicate_row_count=duplicate_count,
            duplicate_percentage=dup_pct,
            memory_estimate_bytes=mem_bytes,
        )

    def compute_stats(self, rows: List[Dict[str, Any]], column: str) -> Dict[str, Any]:
        vals = [r.get(column) for r in rows if r.get(column) is not None]
        if not vals:
            return {"count": 0, "error": "No non-null values found in column"}

        numeric = []
        for v in vals:
            try:
                numeric.append(float(v))
            except (ValueError, TypeError):
                pass

        if not numeric:
            # String / categorical stats
            freq: Dict[str, int] = {}
            for v in vals:
                k = str(v)
                freq[k] = freq.get(k, 0) + 1
            sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            return {
                "count": len(vals),
                "distinct_count": len(freq),
                "top_categories": sorted_freq[:5],
                "mode": sorted_freq[0][0] if sorted_freq else None,
            }

        numeric.sort()
        n = len(numeric)
        mean_v = statistics.mean(numeric)
        median_v = statistics.median(numeric)
        std_v = statistics.stdev(numeric) if n > 1 else 0.0
        min_v = numeric[0]
        max_v = numeric[-1]
        q1 = numeric[int(n * 0.25)]
        q3 = numeric[int(n * 0.75)]
        iqr = q3 - q1

        # Skewness estimation
        skewness = 0.0
        if n > 2 and std_v > 0:
            skewness = sum((x - mean_v) ** 3 for x in numeric) / ((n - 1) * (std_v ** 3))

        return {
            "count": n,
            "min": min_v,
            "max": max_v,
            "mean": round(mean_v, 4),
            "median": round(median_v, 4),
            "std": round(std_v, 4),
            "variance": round(std_v ** 2, 4),
            "q25": q1,
            "q75": q3,
            "iqr": round(iqr, 4),
            "skewness": round(skewness, 4),
        }

    def compute_correlations(self, rows: List[Dict[str, Any]], numeric_cols: List[str]) -> Dict[str, Dict[str, float]]:
        matrix: Dict[str, Dict[str, float]] = {c: {} for c in numeric_cols}

        # Extract vectors
        vectors: Dict[str, List[float]] = {}
        for c in numeric_cols:
            vectors[c] = []
            for r in rows:
                try:
                    val = float(r[c]) if r.get(c) is not None else float("nan")
                except (ValueError, TypeError):
                    val = float("nan")
                vectors[c].append(val)

        for i, c1 in enumerate(numeric_cols):
            for j, c2 in enumerate(numeric_cols):
                if c1 == c2:
                    matrix[c1][c2] = 1.0
                    continue
                v1 = vectors[c1]
                v2 = vectors[c2]
                pairs = [(x, y) for x, y in zip(v1, v2) if not math.isnan(x) and not math.isnan(y)]
                if len(pairs) < 3:
                    matrix[c1][c2] = 0.0
                    continue
                xs, ys = zip(*pairs)
                try:
                    mean_x = statistics.mean(xs)
                    mean_y = statistics.mean(ys)
                    std_x = statistics.stdev(xs)
                    std_y = statistics.stdev(ys)
                    if std_x == 0 or std_y == 0:
                        corr = 0.0
                    else:
                        cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs) / (len(pairs) - 1)
                        corr = cov / (std_x * std_y)
                        corr = max(-1.0, min(1.0, corr))
                except Exception:
                    corr = 0.0
                matrix[c1][c2] = round(corr, 4)

        return matrix

    def detect_outliers(self, rows: List[Dict[str, Any]], column: str, method: str = "iqr") -> Dict[str, Any]:
        vals_with_idx = []
        for idx, r in enumerate(rows):
            v = r.get(column)
            if v is not None:
                try:
                    vals_with_idx.append((idx, float(v)))
                except (ValueError, TypeError):
                    pass

        if len(vals_with_idx) < 4:
            return {"outlier_count": 0, "outliers": [], "method": method, "thresholds": {}}

        numeric_vals = [v for _, v in vals_with_idx]
        numeric_vals.sort()
        n = len(numeric_vals)

        outliers = []
        thresholds = {}

        if method.lower() == "zscore":
            mean_v = statistics.mean(numeric_vals)
            std_v = statistics.stdev(numeric_vals) if n > 1 else 0.0
            thresholds = {"mean": round(mean_v, 4), "std": round(std_v, 4), "cutoff_z": 3.0}
            if std_v > 0:
                for idx, val in vals_with_idx:
                    z = abs(val - mean_v) / std_v
                    if z > 3.0:
                        outliers.append({"row_index": idx, "value": val, "z_score": round(z, 2)})
        else:  # IQR default
            q1 = numeric_vals[int(n * 0.25)]
            q3 = numeric_vals[int(n * 0.75)]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            thresholds = {"q1": q1, "q3": q3, "iqr": round(iqr, 4), "lower_bound": round(lower_bound, 4), "upper_bound": round(upper_bound, 4)}
            for idx, val in vals_with_idx:
                if val < lower_bound or val > upper_bound:
                    outliers.append({"row_index": idx, "value": val, "reason": "beyond_iqr_fence"})

        return {
            "column": column,
            "method": method,
            "outlier_count": len(outliers),
            "outliers": outliers[:50],  # Return top 50
            "thresholds": thresholds,
        }


# -----------------------------------------------------------------------------
# Capability 46 Provider Implementation
# -----------------------------------------------------------------------------

class DataScienceAnalyticsProvider(BaseCapabilityProvider):
    """Capability 46: Data Science & Analytics Provider."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"exec\(", re.IGNORECASE),
        re.compile(r"eval\(", re.IGNORECASE),
        re.compile(r"import\s+os", re.IGNORECASE),
        re.compile(r"subprocess\.", re.IGNORECASE),
    ]

    def __init__(
        self,
        config: Optional[AnalyticsConfig] = None,
        backend: Optional[AnalyticsBackend] = None,
    ):
        self.config = config or AnalyticsConfig()
        self.backend = backend or PurePythonAnalyticsBackend()
        self._datasets: Dict[str, Dict[str, Any]] = {}
        self._provenance_ledger: Dict[str, List[Dict[str, Any]]] = {}

        metadata = ProviderMetadata(
            provider_id="provider.analytics.data_science_engine",
            name="Data Science & Analytics Provider",
            supported_capabilities=[
                "analytics.load_dataset",
                "analytics.discover_schema",
                "analytics.profile_data",
                "analytics.quality_check",
                "analytics.compute_stats",
                "analytics.aggregate_group",
                "analytics.filter_sort",
                "analytics.correlation_analysis",
                "analytics.distribution_analysis",
                "analytics.detect_anomalies",
                "analytics.transform_data",
                "analytics.generate_visualization",
                "analytics.generate_plot",
                "analytics.explain_results",
            ],
            priority=10,
            estimated_latency_ms=15.0,
            safety_level="read_only",
            device_target="local",
            description="Pure mathematical data science, profiling, and analytics engine.",
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

        # Security quarantine: inspect all incoming parameters for prompt injection
        param_str = json.dumps(parameters)
        for pat in self.PROMPT_INJECTION_PATTERNS:
            if pat.search(param_str):
                logger.warning("[DataScienceAnalyticsProvider] Prompt injection detected: %s", pat.pattern)
                return ActionResult(
                    status="FAILED",
                    action=capability,
                    provider_id=self.provider_id,
                    output={"error": f"Security refusal: prompt injection pattern detected ({pat.pattern})"},
                    message="Security refusal: untrusted code or prompt injection pattern quarantined",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

        if capability == "analytics.load_dataset":
            return self._load_dataset(parameters, t0)
        elif capability in ["analytics.discover_schema", "analytics.profile_data", "analytics.quality_check"]:
            return self._profile_data(parameters, t0, capability)
        elif capability == "analytics.compute_stats":
            return self._compute_stats(parameters, t0)
        elif capability == "analytics.aggregate_group":
            return self._aggregate_group(parameters, t0)
        elif capability == "analytics.filter_sort":
            return self._filter_sort(parameters, t0)
        elif capability == "analytics.correlation_analysis":
            return self._correlation_analysis(parameters, t0)
        elif capability == "analytics.distribution_analysis":
            return self._distribution_analysis(parameters, t0)
        elif capability == "analytics.detect_anomalies":
            return self._detect_anomalies(parameters, t0)
        elif capability == "analytics.transform_data":
            return self._transform_data(parameters, t0)
        elif capability in ["analytics.generate_visualization", "analytics.generate_plot"]:
            return self._generate_visualization(parameters, t0, capability)
        elif capability == "analytics.explain_results":
            return self._explain_results(parameters, t0)
        else:
            return ActionResult(
                status="FAILED",
                action=capability,
                provider_id=self.provider_id,
                output={"error": f"Unsupported analytics operation '{capability}'"},
                message="Operation not implemented",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    # -------------------------------------------------------------------------
    # Internal Handlers
    # -------------------------------------------------------------------------

    def _load_dataset(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dataset_id = params.get("dataset_id", f"ds_{uuid.uuid4().hex[:8]}")
        data = params.get("data")
        fmt = params.get("format", "auto")

        if data is None:
            return ActionResult(
                status="FAILED",
                action="analytics.load_dataset",
                provider_id=self.provider_id,
                output={"error": "Missing 'data' parameter"},
                message="Data parameter required",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        try:
            cols, rows = self.backend.load_dataset(dataset_id, data, fmt)
        except Exception as err:
            return ActionResult(
                status="FAILED",
                action="analytics.load_dataset",
                provider_id=self.provider_id,
                output={"error": f"Failed to parse dataset: {err}"},
                message="Dataset parsing error",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        self._datasets[dataset_id] = {
            "columns": cols,
            "rows": rows,
            "loaded_at": time.time(),
            "source": params.get("source", "user_input"),
        }
        self._provenance_ledger[dataset_id] = [{
            "operation": "load_dataset",
            "timestamp": time.time(),
            "row_count": len(rows),
            "column_count": len(cols),
        }]

        return ActionResult(
            status="SUCCESS",
            action="analytics.load_dataset",
            provider_id=self.provider_id,
            output={
                "dataset_id": dataset_id,
                "row_count": len(rows),
                "column_count": len(cols),
                "columns": cols,
            },
            message=f"Dataset '{dataset_id}' loaded with {len(rows)} rows and {len(cols)} columns",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _get_dataset_rows(self, params: Dict[str, Any]) -> Tuple[Optional[str], Optional[List[str]], Optional[List[Dict[str, Any]]]]:
        # Check inline data first
        if "data" in params:
            ds_id = params.get("dataset_id", f"ds_{uuid.uuid4().hex[:6]}")
            cols, rows = self.backend.load_dataset(ds_id, params["data"], params.get("format", "auto"))
            return ds_id, cols, rows

        dataset_id = params.get("dataset_id")
        if dataset_id and dataset_id in self._datasets:
            info = self._datasets[dataset_id]
            return dataset_id, info["columns"], info["rows"]
        return None, None, None

    def _profile_data(self, params: Dict[str, Any], t0: float, action: str) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        profile = self.backend.profile_dataset(ds_id or "ephemeral", cols, rows)
        return ActionResult(
            status="SUCCESS",
            action=action,
            provider_id=self.provider_id,
            output=profile.to_dict(),
            message=f"Profiled {len(rows)} rows across {len(cols)} columns",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _compute_stats(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action="analytics.compute_stats",
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        target_col = params.get("column")
        if not target_col:
            # Compute stats for all columns
            all_stats = {}
            for c in cols:
                all_stats[c] = self.backend.compute_stats(rows, c)
            return ActionResult(
                status="SUCCESS",
                action="analytics.compute_stats",
                provider_id=self.provider_id,
                output={"columns": all_stats},
                message=f"Computed statistics across all {len(cols)} columns",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        if target_col not in cols:
            return ActionResult(
                status="FAILED",
                action="analytics.compute_stats",
                provider_id=self.provider_id,
                output={"error": f"Column '{target_col}' not found in dataset"},
                message=f"Column '{target_col}' not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        col_stats = self.backend.compute_stats(rows, target_col)
        out_dict = {"column": target_col, "statistics": col_stats}
        if isinstance(col_stats, dict):
            out_dict.update(col_stats)
        return ActionResult(
            status="SUCCESS",
            action="analytics.compute_stats",
            provider_id=self.provider_id,
            output=out_dict,
            message=f"Computed statistics for column '{target_col}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _aggregate_group(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action="analytics.aggregate_group",
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        group_by = params.get("group_by")
        target_col = params.get("target_column") or params.get("metric") or params.get("column")
        agg_func = (params.get("function") or params.get("aggregator") or "mean").lower()

        if not group_by or not target_col:
            return ActionResult(
                status="FAILED",
                action="analytics.aggregate_group",
                provider_id=self.provider_id,
                output={"error": "group_by and target_column (or metric) are required"},
                message="Missing grouping parameters",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Partition by group_by value
        buckets: Dict[str, List[float]] = {}
        for r in rows:
            g_val = str(r.get(group_by, "UNKNOWN"))
            t_val = r.get(target_col)
            if t_val is not None:
                try:
                    num_val = float(t_val)
                    buckets.setdefault(g_val, []).append(num_val)
                except (ValueError, TypeError):
                    pass

        results = {}
        for g_val, nums in buckets.items():
            if not nums:
                results[g_val] = None
            elif agg_func == "sum":
                results[g_val] = round(sum(nums), 4)
            elif agg_func == "mean":
                results[g_val] = round(statistics.mean(nums), 4)
            elif agg_func == "median":
                results[g_val] = round(statistics.median(nums), 4)
            elif agg_func == "min":
                results[g_val] = min(nums)
            elif agg_func == "max":
                results[g_val] = max(nums)
            elif agg_func == "count":
                results[g_val] = len(nums)
            elif agg_func == "std":
                results[g_val] = round(statistics.stdev(nums), 4) if len(nums) > 1 else 0.0

        return ActionResult(
            status="SUCCESS",
            action="analytics.aggregate_group",
            provider_id=self.provider_id,
            output={
                "group_by": group_by,
                "target_column": target_col,
                "function": agg_func,
                "aggregations": results,
                "groups": results,
                "group_count": len(results),
            },
            message=f"Aggregated '{target_col}' by '{group_by}' using '{agg_func}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _filter_sort(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action="analytics.filter_sort",
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        filter_col = params.get("filter_column")
        op = params.get("operator", "==")
        operand = params.get("value")

        filtered_rows = rows
        if filter_col:
            res = []
            for r in filtered_rows:
                v = r.get(filter_col)
                match = False
                try:
                    if op == "==":
                        match = (v == operand) or (str(v) == str(operand))
                    elif op == "!=":
                        match = (v != operand)
                    elif op == ">":
                        match = float(v) > float(operand)
                    elif op == "<":
                        match = float(v) < float(operand)
                    elif op == ">=":
                        match = float(v) >= float(operand)
                    elif op == "<=":
                        match = float(v) <= float(operand)
                    elif op == "in" and isinstance(operand, list):
                        match = v in operand
                    elif op == "contains":
                        match = str(operand).lower() in str(v).lower()
                except Exception:
                    match = False
                if match:
                    res.append(r)
            filtered_rows = res

        sort_by = params.get("sort_by")
        ascending = params.get("ascending", True)
        if sort_by:
            def sort_key(x):
                val = x.get(sort_by)
                if val is None:
                    return ""
                try:
                    return (0, float(val))
                except Exception:
                    return (1, str(val))
            filtered_rows = sorted(filtered_rows, key=sort_key, reverse=not ascending)

        limit = params.get("limit", 100)
        return ActionResult(
            status="SUCCESS",
            action="analytics.filter_sort",
            provider_id=self.provider_id,
            output={
                "total_matched": len(filtered_rows),
                "rows": filtered_rows[:limit],
            },
            message=f"Filtered and sorted: {len(filtered_rows)} rows matched",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _correlation_analysis(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action="analytics.correlation_analysis",
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Find numeric columns
        specified_cols = params.get("columns")
        if specified_cols:
            num_cols = [c for c in specified_cols if c in cols]
        else:
            num_cols = []
            for c in cols:
                non_null = [r.get(c) for r in rows if r.get(c) is not None]
                if non_null and all(isinstance(v, (int, float)) for v in non_null[:20]):
                    num_cols.append(c)

        if len(num_cols) < 2:
            return ActionResult(
                status="FAILED",
                action="analytics.correlation_analysis",
                provider_id=self.provider_id,
                output={"error": "Need at least 2 numeric columns for correlation analysis"},
                message="Insufficient numeric columns",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        matrix = self.backend.compute_correlations(rows, num_cols)
        return ActionResult(
            status="SUCCESS",
            action="analytics.correlation_analysis",
            provider_id=self.provider_id,
            output={
                "columns": num_cols,
                "correlation_matrix": matrix,
                "epistemic_warning": "CORRELATION DOES NOT IMPLY CAUSATION",
            },
            message=f"Computed correlation matrix for {len(num_cols)} columns",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _distribution_analysis(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action="analytics.distribution_analysis",
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        column = params.get("column")
        num_bins = params.get("bins", self.config.histogram_default_bins)

        if not column or column not in cols:
            return ActionResult(
                status="FAILED",
                action="analytics.distribution_analysis",
                provider_id=self.provider_id,
                output={"error": f"Column '{column}' not found"},
                message="Column missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        vals = []
        for r in rows:
            v = r.get(column)
            if v is not None:
                try:
                    vals.append(float(v))
                except (ValueError, TypeError):
                    pass

        if not vals:
            return ActionResult(
                status="FAILED",
                action="analytics.distribution_analysis",
                provider_id=self.provider_id,
                output={"error": f"No numeric values in column '{column}'"},
                message="Non-numeric column",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        min_v = min(vals)
        max_v = max(vals)
        bin_width = (max_v - min_v) / num_bins if max_v > min_v else 1.0

        bins = [{"bin_start": min_v + i * bin_width, "bin_end": min_v + (i + 1) * bin_width, "count": 0} for i in range(num_bins)]
        for v in vals:
            idx = int((v - min_v) / bin_width) if bin_width > 0 else 0
            if idx >= num_bins:
                idx = num_bins - 1
            bins[idx]["count"] += 1

        return ActionResult(
            status="SUCCESS",
            action="analytics.distribution_analysis",
            provider_id=self.provider_id,
            output={
                "column": column,
                "total_observations": len(vals),
                "min": min_v,
                "max": max_v,
                "bins": bins,
            },
            message=f"Computed distribution histogram for '{column}' into {num_bins} bins",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _detect_anomalies(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action="analytics.detect_anomalies",
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        target_col = params.get("column")
        method = params.get("method", "iqr")

        if not target_col or target_col not in cols:
            return ActionResult(
                status="FAILED",
                action="analytics.detect_anomalies",
                provider_id=self.provider_id,
                output={"error": f"Column '{target_col}' not found"},
                message="Column missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        outlier_res = self.backend.detect_outliers(rows, target_col, method)
        return ActionResult(
            status="SUCCESS",
            action="analytics.detect_anomalies",
            provider_id=self.provider_id,
            output=outlier_res,
            message=f"Detected {outlier_res['outlier_count']} outlier(s) in '{target_col}' using {method.upper()}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _transform_data(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        if cols is None or rows is None:
            return ActionResult(
                status="FAILED",
                action="analytics.transform_data",
                provider_id=self.provider_id,
                output={"error": "Dataset not found or no data provided"},
                message="Dataset missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        transformation = params.get("transformation", "")
        new_rows = [dict(r) for r in rows]
        new_cols = list(cols)

        if transformation == "dropna":
            col = params.get("column")
            if col:
                new_rows = [r for r in new_rows if r.get(col) is not None]
            else:
                new_rows = [r for r in new_rows if all(v is not None for v in r.values())]

        elif transformation == "fillna":
            col = params.get("column")
            fill_val = params.get("value")
            strategy = params.get("strategy")
            if col in new_cols:
                if strategy == "mean":
                    numeric = [float(r[col]) for r in new_rows if r.get(col) is not None]
                    fill_val = statistics.mean(numeric) if numeric else 0.0
                elif strategy == "median":
                    numeric = [float(r[col]) for r in new_rows if r.get(col) is not None]
                    fill_val = statistics.median(numeric) if numeric else 0.0
                for r in new_rows:
                    if r.get(col) is None:
                        r[col] = fill_val

        elif transformation == "normalize":
            col = params.get("column")
            method = params.get("method", "minmax")
            if col in new_cols:
                numeric = [float(r[col]) for r in new_rows if r.get(col) is not None]
                if numeric:
                    min_v = min(numeric)
                    max_v = max(numeric)
                    mean_v = statistics.mean(numeric)
                    std_v = statistics.stdev(numeric) if len(numeric) > 1 else 1.0
                    norm_col = f"{col}_norm"
                    new_cols.append(norm_col)
                    for r in new_rows:
                        if r.get(col) is not None:
                            val = float(r[col])
                            if method == "zscore":
                                r[norm_col] = round((val - mean_v) / (std_v if std_v > 0 else 1.0), 4)
                            else:  # minmax
                                r[norm_col] = round((val - min_v) / (max_v - min_v if max_v > min_v else 1.0), 4)
                        else:
                            r[norm_col] = None

        elif transformation == "derive_column":
            new_col_name = params.get("new_column", f"derived_{uuid.uuid4().hex[:4]}")
            op = params.get("operation", "add")
            col1 = params.get("column1")
            col2 = params.get("column2")
            scalar = params.get("scalar", 0.0)
            if col1 in new_cols:
                new_cols.append(new_col_name)
                for r in new_rows:
                    v1 = float(r.get(col1, 0.0) or 0.0)
                    v2 = float(r.get(col2, scalar) or scalar) if col2 else float(scalar)
                    if op == "add":
                        r[new_col_name] = round(v1 + v2, 4)
                    elif op == "subtract":
                        r[new_col_name] = round(v1 - v2, 4)
                    elif op == "multiply":
                        r[new_col_name] = round(v1 * v2, 4)
                    elif op == "divide":
                        r[new_col_name] = round(v1 / v2, 4) if v2 != 0 else None

        # Update or store as new dataset if requested
        out_ds_id = params.get("output_dataset_id", ds_id)
        if out_ds_id:
            self._datasets[out_ds_id] = {
                "columns": new_cols,
                "rows": new_rows,
                "loaded_at": time.time(),
                "source": f"transformed_{transformation}",
            }
            self._provenance_ledger.setdefault(out_ds_id, []).append({
                "operation": f"transform_{transformation}",
                "timestamp": time.time(),
                "row_count": len(new_rows),
            })

        return ActionResult(
            status="SUCCESS",
            action="analytics.transform_data",
            provider_id=self.provider_id,
            output={
                "dataset_id": out_ds_id,
                "transformation": transformation,
                "row_count": len(new_rows),
                "columns": new_cols,
                "sample_rows": new_rows[:5],
            },
            message=f"Applied transformation '{transformation}' successfully",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _generate_visualization(self, params: Dict[str, Any], t0: float, action: str) -> ActionResult:
        ds_id, cols, rows = self._get_dataset_rows(params)
        chart_type = params.get("chart_type", "bar")
        x_field = params.get("x_field")
        y_field = params.get("y_field")
        title = params.get("title", f"{chart_type.capitalize()} Chart")

        if not x_field:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": "x_field is required for visualization"},
                message="Missing x_field",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        data_points = []
        if rows:
            for r in rows[:100]:
                dp = {"x": r.get(x_field)}
                if y_field:
                    dp["y"] = r.get(y_field)
                data_points.append(dp)

        spec = {
            "chart_type": chart_type,
            "title": title,
            "x_axis": {"field": x_field, "label": x_field},
            "y_axis": {"field": y_field, "label": y_field} if y_field else None,
            "data_point_count": len(data_points),
            "data_points": data_points,
            "theme": "dark_modern",
        }

        return ActionResult(
            status="SUCCESS",
            action=action,
            provider_id=self.provider_id,
            output={"specification": spec},
            message=f"Generated {chart_type} chart specification with {len(data_points)} points",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _explain_results(self, params: Dict[str, Any], t0: float) -> ActionResult:
        ds_id = params.get("dataset_id", "generic")
        calculation = params.get("calculation", "Statistical Analysis")
        findings = params.get("findings", {})

        provenance = self._provenance_ledger.get(ds_id, [{
            "operation": "direct_analysis",
            "timestamp": time.time(),
        }])

        explanation = {
            "dataset_id": ds_id,
            "calculation_summary": calculation,
            "findings": findings,
            "assumptions": [
                "Data assumed to follow observational distribution",
                "Null entries handled via configured missing-value policy",
            ],
            "limitations": [
                "Sample bounds apply to empirical observations only",
                "Observational statistics reflect sample slice",
            ],
            "causality_disclaimer": "CORRELATION DOES NOT IMPLY CAUSATION",
            "provenance_chain": provenance,
            "timestamp": time.time(),
        }

        return ActionResult(
            status="SUCCESS",
            action="analytics.explain_results",
            provider_id=self.provider_id,
            output=explanation,
            message="Generated analytical explanation with strict epistemic disclaimers",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )


data_science_analytics_provider = DataScienceAnalyticsProvider()
