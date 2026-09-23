# Capability 46: Data Science & Analytics

## 1. Overview & Purpose
Capability 46 provides JARVIS with a high-performance, pure Python and NumPy-powered data science, statistical analysis, and data transformation engine. It enables automated ingestion, profiling, statistical analysis, anomaly detection, data manipulation, visualization specification, and empirical explanation across arbitrary structured datasets.

### Core Architectural Invariants:
- **Zero Domain-Specific Hardcoding**: Operates on arbitrary column names, schemas, row counts, and data distributions. Zero hardcoded references to classical benchmark datasets (`iris`, `titanic`, `boston_housing`).
- **Untrusted Data Isolation**: Dataset cells are treated as strictly untrusted text/values. Cells are **never** evaluated as executable code (`eval`, `exec`). Prompt injection payloads embedded in dataset cells are quarantined.
- **Mandatory Epistemic Integrity**: Analytical explanations explicitly distinguish **Correlation** from **Causation**, enforcing the invariant: `"CORRELATION DOES NOT IMPLY CAUSATION"`.
- **Complete Provenance**: Every output maintains a cryptographic/UUID provenance trail capturing dataset hash, transformation steps, computation timestamp, and schema snapshot.

---

## 2. Architecture & Data Processing Pipeline
```
Untrusted Data Source (CSV, JSON, Dicts)
               ↓
Data Ingestion & Sanitization
               ↓
Schema Discovery & Type Inference
               ↓
Data Quality Assessment & Profiling
               ↓
Analytical Planning & Validation
               ↓
Computation (Pure Python & NumPy Engine)
               ↓
Visualization Specification Generation
               ↓
Natural Explanation & Causality Tagging
               ↓
Persistent Provenance Chain
```

---

## 3. Supported Operations & Capability Contracts

| Capability Operation | Description | Safety / Output |
| :--- | :--- | :--- |
| `analytics.load_dataset` | Ingests CSV strings, JSON records, or dictionaries | Safe Storage |
| `analytics.discover_schema` | Inspects data types (`int`, `float`, `datetime`, `string`, `bool`) | Schema Dict |
| `analytics.profile_data` | Profiles null counts, distinct values, duplicate rows, memory | Dataset Profile |
| `analytics.quality_check` | Audits completeness, type consistency, and anomalies | Quality Report |
| `analytics.compute_stats` | Computes mean, median, std, min, max, Q1, Q3, and IQR | Descriptive Stats |
| `analytics.aggregate_group` | Groups by categorical column with sum, mean, median, min, max | Group Summary |
| `analytics.filter_sort` | Filters on operators (`==`, `!=`, `>`, `<`, `in`, `contains`) | Filtered Dataset |
| `analytics.correlation_analysis` | Computes multi-column Pearson correlation matrix | Correlation Matrix |
| `analytics.distribution_analysis`| Computes dynamic histogram binning and frequency distributions | Bin Counts |
| `analytics.detect_anomalies` | Discovers outliers via IQR fence or Z-score thresholds | Outlier List |
| `analytics.transform_data` | Imputes missing values, normalizes (min-max, z-score), derives columns | Transformed Data |
| `analytics.generate_visualization` | Generates declarative chart specifications (bar, line, scatter, box) | Chart Spec |
| `analytics.explain_results` | Synthesizes insights with explicit causality disclaimer | Epistemic Expl |

---

## 4. Epistemic Principles & Causality Integrity
Whenever JARVIS summarizes or explains analytical findings:
1. **Correlation is Not Causation**:
   Statistical co-variation between columns (e.g. Pearson $r \approx 0.98$) is presented strictly as mathematical association. Explanations explicitly tag:
   ```json
   {
     "causality_disclaimer": "CORRELATION DOES NOT IMPLY CAUSATION",
     "epistemic_warning": "Statistical association does not prove underlying causal mechanism"
   }
   ```
2. **Honest Significance**:
   No fabrication of statistical significance or p-values without sufficient sample size ($N \ge 30$).

---

## 5. Security & Untrusted Data Isolation
1. **Adversarial Cell Quarantine**:
   Every incoming dataset cell is screened against regex signatures for prompt injection (`ignore previous instructions`, `system override`, `eval(`, `import os`). Any adversarial pattern immediately aborts ingestion and quarantines the payload.
2. **Zero Eval Execution**:
   Derived column calculations use deterministic arithmetic dispatch (`add`, `subtract`, `multiply`, `divide`) rather than dynamic python `eval()`.
3. **Memory & Size Safeguards**:
   Row limits and streaming safeguards prevent uncontrolled memory allocation on malformed or malicious inputs.

---

## 6. Provider Replaceability
`DataScienceAnalyticsProvider` implements `BaseCapabilityProvider` with an isolated `PurePythonAnalyticsBackend`. If external engines (e.g., DuckDB, Polars, PySpark) are configured, the provider backend can be hot-swapped without altering higher-order reasoning or cognitive orchestration.
