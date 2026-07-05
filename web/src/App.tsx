import { useEffect, useState } from "react";
import { Code2, FileSearch, Play, RefreshCw, Settings2 } from "lucide-react";
import "./styles.css";

type SystemStatus = {
  status: string;
  data_dir: string;
  metadata_store: {
    kind: string;
    path: string;
    initialized: boolean;
  };
  analytical_store: {
    kind: string;
    duckdb_path: string;
    parquet_dir: string;
    initialized: boolean;
  };
};

type LoadState =
  | { state: "loading" }
  | { state: "loaded"; status: SystemStatus }
  | { state: "failed"; message: string };

type JobStatus = {
  id: string;
  type: string;
  status: string;
  parameters?: Record<string, unknown>;
  progress: Record<string, unknown>;
  error: string | null;
  result_ref?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
};

type SyncSchedule = {
  enabled: boolean;
  provider: string;
  instrument_types: string[];
  adjustment: string;
  start_date: string;
  overlap_days: number;
  schedule_time: string;
  timezone: string;
  trading_days_only: boolean;
};

type SyncDiagnostics = {
  schedule: SyncSchedule;
  last_successful_sync_time: string | null;
  last_successful_job: JobStatus | null;
  running_jobs: JobStatus[];
  recent_failures: JobStatus[];
  recent_jobs: JobStatus[];
};

type StrategyParamDefinition = {
  type?: string;
  default?: unknown;
  min?: number;
  max?: number;
  options?: unknown[];
};

type StrategySummary = {
  strategy_id: string;
  name: string;
  description: string;
  file_path: string;
  params: Record<string, StrategyParamDefinition>;
  latest_version: {
    source_hash: string;
    source_snapshot: string;
    git_commit: string | null;
    git_dirty: boolean | null;
    created_at: string;
  };
};

type Candidate = {
  instrument_id: string;
  score: number;
  explanation: string;
  rank_basis: string | null;
  tags: string[];
  metrics: Record<string, unknown>;
};

type StrategyRun = {
  id: string;
  strategy_id: string;
  strategy_version: {
    source_hash: string;
    source_snapshot: string;
    git_commit: string | null;
    git_dirty: boolean | null;
    created_at: string;
  };
  params: Record<string, unknown>;
  as_of_date: string;
  adjustment: string;
  market_data_snapshot_ref: string;
  candidates: Candidate[];
  created_at: string;
};

type HorizonMetrics = {
  observation_count: number;
  average_return: number | null;
  win_rate: number | null;
  max_drawdown: number | null;
  average_benchmark_return: number | null;
  average_excess_return: number | null;
};

type SelectionBacktest = {
  id: string;
  strategy_id: string;
  strategy_version: {
    source_hash: string;
    source_snapshot: string;
    git_commit: string | null;
    git_dirty: boolean | null;
    created_at: string;
  };
  params: Record<string, unknown>;
  start_date: string;
  end_date: string;
  selection_dates: string[];
  top_n: number;
  horizons: number[];
  benchmark: { instrument_id: string } | null;
  market_data_snapshot_ref: string;
  selection_results: {
    selection_date: string;
    candidates: Candidate[];
    horizon_results: Record<string, Record<string, unknown>[]>;
  }[];
  summary_metrics: Record<string, HorizonMetrics>;
  created_at: string;
};

type PagedResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

type ComparisonValue = {
  values: Record<string, number>;
  delta: number | null;
};

type ResultSnapshotComparison = {
  snapshot_type: "strategy_run" | "selection_backtest";
  candidate_score_deltas?: Record<string, ComparisonValue>;
  metric_deltas?: Record<string, Record<string, ComparisonValue>>;
};

function todayIso() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultStrategyParams(strategy: StrategySummary) {
  return Object.fromEntries(
    Object.entries(strategy.params).map(([name, definition]) => [
      name,
      definition.default,
    ]),
  );
}

function strategyParamType(definition: StrategyParamDefinition) {
  return String(definition.type ?? "string");
}

function inputValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string" || typeof value === "number") {
    return value;
  }
  return String(value);
}

function coerceParamValue(
  definition: StrategyParamDefinition,
  value: string | boolean,
) {
  const type = strategyParamType(definition);
  if (type === "bool" || type === "boolean") {
    return Boolean(value);
  }
  if (type === "int" || type === "integer") {
    return Number.parseInt(String(value), 10);
  }
  if (type === "float" || type === "number") {
    return Number.parseFloat(String(value));
  }
  return value;
}

function formatMetric(value: number | null) {
  if (value === null) {
    return "n/a";
  }
  return value.toFixed(4);
}

function toggleComparisonId(current: string[], id: string) {
  if (current.includes(id)) {
    return current.filter((value) => value !== id);
  }
  return [...current, id].slice(-2);
}

export function App() {
  const [loadState, setLoadState] = useState<LoadState>({ state: "loading" });
  const [syncStartDate, setSyncStartDate] = useState("2024-01-01");
  const [syncEndDate, setSyncEndDate] = useState(todayIso());
  const [syncJob, setSyncJob] = useState<JobStatus | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncDiagnostics, setSyncDiagnostics] = useState<SyncDiagnostics | null>(null);
  const [syncDiagnosticsError, setSyncDiagnosticsError] = useState<string | null>(null);
  const [strategyPath, setStrategyPath] = useState("");
  const [sourceStrategyPath, setSourceStrategyPath] = useState<string | null>(null);
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [strategyError, setStrategyError] = useState<string | null>(null);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [isSyncingSourceStrategies, setIsSyncingSourceStrategies] = useState(false);
  const [strategyParamValues, setStrategyParamValues] = useState<
    Record<string, unknown>
  >({});
  const [runAsOfDate, setRunAsOfDate] = useState("");
  const [isRunningStrategy, setIsRunningStrategy] = useState(false);
  const [strategyRun, setStrategyRun] = useState<StrategyRun | null>(null);
  const [strategyRunError, setStrategyRunError] = useState<string | null>(null);
  const [backtestStartDate, setBacktestStartDate] = useState("2024-01-01");
  const [backtestEndDate, setBacktestEndDate] = useState("");
  const [backtestTopN, setBacktestTopN] = useState(20);
  const [backtestHorizons, setBacktestHorizons] = useState("1,5,10,20");
  const [backtestBenchmark, setBacktestBenchmark] = useState("");
  const [isRunningBacktest, setIsRunningBacktest] = useState(false);
  const [selectionBacktest, setSelectionBacktest] =
    useState<SelectionBacktest | null>(null);
  const [selectionBacktestError, setSelectionBacktestError] =
    useState<string | null>(null);
  const [strategyRunSnapshots, setStrategyRunSnapshots] = useState<StrategyRun[]>([]);
  const [backtestSnapshots, setBacktestSnapshots] = useState<SelectionBacktest[]>([]);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [activeSnapshotType, setActiveSnapshotType] =
    useState<"strategy_run" | "selection_backtest">("strategy_run");
  const [selectedStrategyRunSnapshotId, setSelectedStrategyRunSnapshotId] =
    useState<string | null>(null);
  const [selectedBacktestSnapshotId, setSelectedBacktestSnapshotId] =
    useState<string | null>(null);
  const [strategyRunComparisonIds, setStrategyRunComparisonIds] = useState<string[]>(
    [],
  );
  const [backtestComparisonIds, setBacktestComparisonIds] = useState<string[]>([]);
  const [snapshotComparison, setSnapshotComparison] =
    useState<ResultSnapshotComparison | null>(null);

  useEffect(() => {
    fetch("/api/system/status")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`status request failed: ${response.status}`);
        }
        return response.json() as Promise<SystemStatus>;
      })
      .then((status) => setLoadState({ state: "loaded", status }))
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "Unknown error";
        setLoadState({ state: "failed", message });
      });
  }, []);

  useEffect(() => {
    syncSourceStrategies();
  }, []);

  useEffect(() => {
    refreshResultSnapshots();
  }, []);

  useEffect(() => {
    refreshSyncDiagnostics();
  }, []);

  useEffect(() => {
    const selected = strategies.find(
      (strategy) => strategy.strategy_id === selectedStrategyId,
    );
    setStrategyParamValues(selected ? defaultStrategyParams(selected) : {});
  }, [selectedStrategyId, strategies]);

  async function syncSourceStrategies() {
    setIsSyncingSourceStrategies(true);
    setStrategyError(null);
    try {
      const response = await fetch("/api/strategies/sync-source", {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`source Strategy sync failed: ${response.status}`);
      }
      const body = (await response.json()) as {
        source_path: string;
        strategies: StrategySummary[];
      };
      setSourceStrategyPath(body.source_path);
      await refreshStrategies();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setStrategyError(message);
    } finally {
      setIsSyncingSourceStrategies(false);
    }
  }

  async function refreshStrategies() {
    try {
      const response = await fetch("/api/strategies");
      if (!response.ok) {
        throw new Error(`strategy request failed: ${response.status}`);
      }
      const loadedStrategies = (await response.json()) as StrategySummary[];
      setStrategies(loadedStrategies);
      setSelectedStrategyId((current) => {
        if (
          current &&
          loadedStrategies.some((strategy) => strategy.strategy_id === current)
        ) {
          return current;
        }
        return loadedStrategies[0]?.strategy_id ?? null;
      });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setStrategyError(message);
    }
  }

  async function refreshResultSnapshots() {
    try {
      const [runResponse, backtestResponse] = await Promise.all([
        fetch("/api/strategy-runs?limit=25"),
        fetch("/api/selection-backtests?limit=25"),
      ]);
      if (!runResponse.ok || !backtestResponse.ok) {
        throw new Error("Result Snapshot request failed.");
      }
      const runBody = (await runResponse.json()) as PagedResponse<StrategyRun>;
      const backtestBody =
        (await backtestResponse.json()) as PagedResponse<SelectionBacktest>;
      setStrategyRunSnapshots(runBody.items);
      setBacktestSnapshots(backtestBody.items);
      if (!selectedStrategyRunSnapshotId && runBody.items.length > 0) {
        setSelectedStrategyRunSnapshotId(runBody.items[0].id);
      }
      if (!selectedBacktestSnapshotId && backtestBody.items.length > 0) {
        setSelectedBacktestSnapshotId(backtestBody.items[0].id);
      }
      setSnapshotError(null);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setSnapshotError(message);
    }
  }

  async function refreshSyncDiagnostics() {
    try {
      const response = await fetch("/api/market-data/sync-diagnostics");
      if (!response.ok) {
        throw new Error(`sync diagnostics failed: ${response.status}`);
      }
      setSyncDiagnostics((await response.json()) as SyncDiagnostics);
      setSyncDiagnosticsError(null);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setSyncDiagnosticsError(message);
    }
  }

  async function runMarketDataSync() {
    setIsSyncing(true);
    setSyncError(null);
    setSyncJob(null);

    try {
      const response = await fetch("/api/market-data/sync", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider: "akshare",
          instrument_types: ["stock", "etf"],
          adjustment: "hfq",
          start_date: syncStartDate,
          end_date: syncEndDate,
          overlap_days: 5,
        }),
      });
      const body = await response.json();
      if (!response.ok) {
        const failedJob = body.detail as JobStatus | undefined;
        if (failedJob) {
          setSyncJob(failedJob);
          setSyncError(failedJob.error ?? "Market Data synchronization failed.");
        } else {
          setSyncError("Market Data synchronization failed.");
        }
        return;
      }
      setSyncJob(body.job as JobStatus);
      await refreshSyncDiagnostics();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setSyncError(message);
    } finally {
      setIsSyncing(false);
    }
  }

  async function discoverStrategies() {
    if (!strategyPath.trim()) {
      setStrategyError("Enter a Strategy file or directory path.");
      return;
    }
    setIsDiscovering(true);
    setStrategyError(null);
    try {
      const response = await fetch("/api/strategies/discover", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ paths: [strategyPath.trim()] }),
      });
      if (!response.ok) {
        throw new Error(`strategy discovery failed: ${response.status}`);
      }
      const body = (await response.json()) as { strategies: StrategySummary[] };
      await refreshStrategies();
      if (body.strategies.length > 0) {
        setSelectedStrategyId(body.strategies[0].strategy_id);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setStrategyError(message);
    } finally {
      setIsDiscovering(false);
    }
  }

  function updateStrategyParamValue(
    name: string,
    definition: StrategyParamDefinition,
    value: string | boolean,
  ) {
    setStrategyParamValues((current) => ({
      ...current,
      [name]: coerceParamValue(definition, value),
    }));
  }

  function renderStrategyParamControl(
    name: string,
    definition: StrategyParamDefinition,
  ) {
    const value = strategyParamValues[name] ?? definition.default ?? "";
    const type = strategyParamType(definition);

    if (Array.isArray(definition.options) && definition.options.length > 0) {
      return (
        <label className="param-control" key={name}>
          {name}
          <select
            value={String(value)}
            onChange={(event) =>
              updateStrategyParamValue(name, definition, event.target.value)
            }
          >
            {definition.options.map((option) => (
              <option key={String(option)} value={String(option)}>
                {String(option)}
              </option>
            ))}
          </select>
        </label>
      );
    }

    if (type === "bool" || type === "boolean") {
      return (
        <label className="param-control checkbox-control" key={name}>
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(event) =>
              updateStrategyParamValue(name, definition, event.target.checked)
            }
          />
          {name}
        </label>
      );
    }

    if (type === "int" || type === "integer" || type === "float" || type === "number") {
      return (
        <label className="param-control" key={name}>
          {name}
          <input
            type="number"
            min={definition.min}
            max={definition.max}
            step={type === "int" || type === "integer" ? 1 : "any"}
            value={inputValue(value)}
            onChange={(event) =>
              updateStrategyParamValue(name, definition, event.target.value)
            }
          />
        </label>
      );
    }

    return (
      <label className="param-control" key={name}>
        {name}
        <input
          type="text"
          value={inputValue(value)}
          onChange={(event) =>
            updateStrategyParamValue(name, definition, event.target.value)
          }
        />
      </label>
    );
  }

  async function runSelectedStrategy() {
    if (!selectedStrategy) {
      return;
    }
    setIsRunningStrategy(true);
    setStrategyRun(null);
    setStrategyRunError(null);

    try {
      const response = await fetch("/api/strategy-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          strategy_id: selectedStrategy.strategy_id,
          params: strategyParamValues,
          as_of_date: runAsOfDate || undefined,
        }),
      });
      const body = await response.json();
      if (!response.ok) {
        const failedJob = body.detail as JobStatus | undefined;
        setStrategyRunError(
          failedJob?.error ?? `Strategy Run failed: ${response.status}`,
        );
        return;
      }
      const createdRun = body.strategy_run as StrategyRun;
      setStrategyRun(createdRun);
      setRunAsOfDate(createdRun.as_of_date);
      setSelectedStrategyRunSnapshotId(createdRun.id);
      setActiveSnapshotType("strategy_run");
      await refreshResultSnapshots();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setStrategyRunError(message);
    } finally {
      setIsRunningStrategy(false);
    }
  }

  async function runSelectionBacktest() {
    if (!selectedStrategy) {
      return;
    }
    if (!backtestStartDate || !backtestEndDate) {
      setSelectionBacktestError("Enter a Backtest start and end date.");
      return;
    }
    const horizons = backtestHorizons
      .split(",")
      .map((value) => Number.parseInt(value.trim(), 10))
      .filter((value) => Number.isFinite(value));
    if (horizons.length === 0 || horizons.some((value) => value <= 0)) {
      setSelectionBacktestError("Horizons must be positive day counts.");
      return;
    }

    setIsRunningBacktest(true);
    setSelectionBacktest(null);
    setSelectionBacktestError(null);

    try {
      const response = await fetch("/api/selection-backtests", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          strategy_id: selectedStrategy.strategy_id,
          params: strategyParamValues,
          start_date: backtestStartDate,
          end_date: backtestEndDate,
          top_n: backtestTopN,
          horizons,
          benchmark: backtestBenchmark.trim()
            ? { instrument_id: backtestBenchmark.trim() }
            : undefined,
        }),
      });
      const body = await response.json();
      if (!response.ok) {
        const failedJob = body.detail as JobStatus | undefined;
        setSelectionBacktestError(
          failedJob?.error ?? `Selection Backtest failed: ${response.status}`,
        );
        return;
      }
      const createdBacktest = body.selection_backtest as SelectionBacktest;
      setSelectionBacktest(createdBacktest);
      setSelectedBacktestSnapshotId(createdBacktest.id);
      setActiveSnapshotType("selection_backtest");
      await refreshResultSnapshots();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setSelectionBacktestError(message);
    } finally {
      setIsRunningBacktest(false);
    }
  }

  async function compareSelectedSnapshots(snapshotType: "strategy_run" | "selection_backtest") {
    const snapshotIds =
      snapshotType === "strategy_run"
        ? strategyRunComparisonIds
        : backtestComparisonIds;
    if (snapshotIds.length !== 2) {
      setSnapshotError("Select exactly two Result Snapshots to compare.");
      return;
    }
    try {
      const response = await fetch("/api/result-snapshots/compare", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          snapshot_type: snapshotType,
          snapshot_ids: snapshotIds,
        }),
      });
      if (!response.ok) {
        throw new Error(`Result Snapshot comparison failed: ${response.status}`);
      }
      setSnapshotComparison((await response.json()) as ResultSnapshotComparison);
      setSnapshotError(null);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setSnapshotError(message);
    }
  }

  const selectedStrategy =
    strategies.find((strategy) => strategy.strategy_id === selectedStrategyId) ?? null;
  const selectedStrategyRunSnapshot =
    strategyRunSnapshots.find(
      (snapshot) => snapshot.id === selectedStrategyRunSnapshotId,
    ) ?? null;
  const selectedBacktestSnapshot =
    backtestSnapshots.find((snapshot) => snapshot.id === selectedBacktestSnapshotId) ??
    null;

  return (
    <main className="shell">
      <section className="status-panel">
        <p className="eyebrow">TradeMiner</p>
        <h1>MVP Research Loop</h1>
        {loadState.state === "loading" && <p>Loading system status...</p>}
        {loadState.state === "failed" && (
          <p className="error">Unable to load system status: {loadState.message}</p>
        )}
        {loadState.state === "loaded" && (
          <dl className="status-grid">
            <div>
              <dt>Status</dt>
              <dd>{loadState.status.status}</dd>
            </div>
            <div>
              <dt>Data Directory</dt>
              <dd>{loadState.status.data_dir}</dd>
            </div>
            <div>
              <dt>Metadata Store</dt>
              <dd>{loadState.status.metadata_store.path}</dd>
            </div>
            <div>
              <dt>Analytical Store</dt>
              <dd>{loadState.status.analytical_store.duckdb_path}</dd>
            </div>
          </dl>
        )}
      </section>
      <section className="status-panel sync-panel" data-testid="sync-panel">
        <div>
          <p className="eyebrow">Market Data</p>
          <h2>Manual Synchronization</h2>
        </div>
        <div className="sync-form">
          <label>
            Start Date
            <input
              type="date"
              value={syncStartDate}
              onChange={(event) => setSyncStartDate(event.target.value)}
            />
          </label>
          <label>
            End Date
            <input
              type="date"
              value={syncEndDate}
              onChange={(event) => setSyncEndDate(event.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={runMarketDataSync}
            disabled={isSyncing}
            data-testid="sync-market-data"
          >
            <RefreshCw aria-hidden="true" size={18} />
            {isSyncing ? "Syncing" : "Sync"}
          </button>
        </div>
        {syncJob && (
          <dl className="status-grid job-grid">
            <div>
              <dt>Job</dt>
              <dd>{syncJob.id}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{syncJob.status}</dd>
            </div>
          </dl>
        )}
        {syncError && <p className="error">{syncError}</p>}
        <div className="sync-diagnostics">
          <div className="section-heading-row">
            <h3>Sync Diagnostics</h3>
            <button type="button" onClick={refreshSyncDiagnostics}>
              <RefreshCw aria-hidden="true" size={18} />
              Refresh
            </button>
          </div>
          {syncDiagnosticsError && (
            <p className="error">{syncDiagnosticsError}</p>
          )}
          {syncDiagnostics && (
            <>
              <dl className="status-grid">
                <div>
                  <dt>Schedule</dt>
                  <dd>
                    {syncDiagnostics.schedule.schedule_time}{" "}
                    {syncDiagnostics.schedule.timezone}
                  </dd>
                </div>
                <div>
                  <dt>Provider</dt>
                  <dd>{syncDiagnostics.schedule.provider}</dd>
                </div>
                <div>
                  <dt>Instrument Types</dt>
                  <dd>{syncDiagnostics.schedule.instrument_types.join(", ")}</dd>
                </div>
                <div>
                  <dt>Last Success</dt>
                  <dd>{syncDiagnostics.last_successful_sync_time ?? "none"}</dd>
                </div>
                <div>
                  <dt>Running Jobs</dt>
                  <dd>{syncDiagnostics.running_jobs.length}</dd>
                </div>
                <div>
                  <dt>Recent Failures</dt>
                  <dd>{syncDiagnostics.recent_failures.length}</dd>
                </div>
              </dl>
              {syncDiagnostics.recent_failures.length > 0 && (
                <div className="diagnostic-list">
                  {syncDiagnostics.recent_failures.map((failure) => (
                    <div key={failure.id}>
                      <strong>{failure.id}</strong>
                      <span>{failure.error ?? "Unknown failure"}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </section>
      <section className="status-panel strategy-panel" data-testid="strategy-panel">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Strategies</p>
            <h2>Strategy Management</h2>
          </div>
          <button
            type="button"
            onClick={syncSourceStrategies}
            disabled={isSyncingSourceStrategies}
            data-testid="sync-source-strategies"
          >
            <Code2 aria-hidden="true" size={18} />
            {isSyncingSourceStrategies ? "Syncing Source" : "Sync Source"}
          </button>
        </div>
        {sourceStrategyPath && (
          <dl className="status-grid source-grid">
            <div>
              <dt>Source Strategy Directory</dt>
              <dd>{sourceStrategyPath}</dd>
            </div>
            <div>
              <dt>Available Strategies</dt>
              <dd>{strategies.length}</dd>
            </div>
          </dl>
        )}
        <div className="strategy-discovery">
          <label className="path-field">
            Additional Strategy Path
            <input
              type="text"
              placeholder="/path/to/strategies"
              value={strategyPath}
              onChange={(event) => setStrategyPath(event.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={discoverStrategies}
            disabled={isDiscovering}
            data-testid="discover-strategies"
          >
            <FileSearch aria-hidden="true" size={18} />
            {isDiscovering ? "Discovering" : "Discover"}
          </button>
        </div>
        {strategyError && <p className="error">{strategyError}</p>}
        <div className="strategy-layout">
          <div className="strategy-list" aria-label="Strategy list">
            {strategies.length === 0 && <p>No Strategies available yet.</p>}
            {strategies.map((strategy) => (
              <button
                className="strategy-row"
                type="button"
                key={strategy.strategy_id}
                onClick={() => setSelectedStrategyId(strategy.strategy_id)}
                data-selected={strategy.strategy_id === selectedStrategyId}
                data-testid={`strategy-row-${strategy.strategy_id}`}
              >
                <span>{strategy.name}</span>
                <small>{strategy.strategy_id}</small>
                <small>{strategy.file_path}</small>
              </button>
            ))}
          </div>
          {selectedStrategy && (
            <article className="strategy-detail">
              <div className="strategy-title-row">
                <div>
                  <h3>{selectedStrategy.name}</h3>
                  <p>{selectedStrategy.description || "No description provided."}</p>
                </div>
                <button
                  type="button"
                  onClick={runSelectedStrategy}
                  disabled={isRunningStrategy}
                  data-testid="quick-run-strategy"
                >
                  <Play aria-hidden="true" size={18} />
                  {isRunningStrategy ? "Running" : "Run Strategy"}
                </button>
              </div>
              <dl className="detail-list">
                <div>
                  <dt>File</dt>
                  <dd>{selectedStrategy.file_path}</dd>
                </div>
                <div>
                  <dt>Source Hash</dt>
                  <dd>{selectedStrategy.latest_version.source_hash}</dd>
                </div>
                <div>
                  <dt>Git Commit</dt>
                  <dd>{selectedStrategy.latest_version.git_commit ?? "not available"}</dd>
                </div>
                <div>
                  <dt>Git Dirty</dt>
                  <dd>
                    {selectedStrategy.latest_version.git_dirty === null
                      ? "not available"
                      : String(selectedStrategy.latest_version.git_dirty)}
                  </dd>
                </div>
              </dl>
              <div className="subsection-heading">
                <h4>
                  <Settings2 aria-hidden="true" size={18} />
                  Parameters
                </h4>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() =>
                    setStrategyParamValues(defaultStrategyParams(selectedStrategy))
                  }
                >
                  Reset
                </button>
              </div>
              <div className="param-grid">
                {Object.entries(selectedStrategy.params).length === 0 && (
                  <p>No parameters.</p>
                )}
                {Object.entries(selectedStrategy.params).map(([name, definition]) =>
                  renderStrategyParamControl(name, definition),
                )}
              </div>
              <details className="source-view">
                <summary>Source Snapshot</summary>
                <pre>{selectedStrategy.latest_version.source_snapshot}</pre>
              </details>
              <div className="run-controls">
                <label>
                  As-Of Date
                  <input
                    type="date"
                    value={runAsOfDate}
                    onChange={(event) => setRunAsOfDate(event.target.value)}
                  />
                </label>
                <button
                  type="button"
                  onClick={runSelectedStrategy}
                  disabled={isRunningStrategy}
                  data-testid="run-strategy"
                >
                  <Play aria-hidden="true" size={18} />
                  {isRunningStrategy ? "Running" : "Run Strategy"}
                </button>
              </div>
              {strategyRunError && <p className="error">{strategyRunError}</p>}
              {strategyRun && (
                <section className="candidate-results" data-testid="candidate-results">
                  <h4>Candidates</h4>
                  {strategyRun.candidates.length === 0 && <p>No Candidates returned.</p>}
                  {strategyRun.candidates.map((candidate) => (
                    <article className="candidate-row" key={candidate.instrument_id}>
                      <div>
                        <strong>{candidate.instrument_id}</strong>
                        <span>{candidate.explanation}</span>
                      </div>
                      <dl>
                        <div>
                          <dt>Score</dt>
                          <dd>{candidate.score}</dd>
                        </div>
                        <div>
                          <dt>Rank Basis</dt>
                          <dd>{candidate.rank_basis ?? "not provided"}</dd>
                        </div>
                        <div>
                          <dt>Tags</dt>
                          <dd>{candidate.tags.join(", ") || "none"}</dd>
                        </div>
                      </dl>
                      <pre>{JSON.stringify(candidate.metrics, null, 2)}</pre>
                    </article>
                  ))}
                </section>
              )}
              <section className="backtest-section">
                <h4>Selection Backtest</h4>
                <div className="backtest-controls">
                  <label>
                    Start Date
                    <input
                      type="date"
                      value={backtestStartDate}
                      onChange={(event) => setBacktestStartDate(event.target.value)}
                    />
                  </label>
                  <label>
                    End Date
                    <input
                      type="date"
                      value={backtestEndDate}
                      onChange={(event) => setBacktestEndDate(event.target.value)}
                    />
                  </label>
                  <label>
                    Top N
                    <input
                      type="number"
                      min="1"
                      value={backtestTopN}
                      onChange={(event) =>
                        setBacktestTopN(Number.parseInt(event.target.value, 10))
                      }
                    />
                  </label>
                  <label>
                    Horizons
                    <input
                      type="text"
                      value={backtestHorizons}
                      onChange={(event) => setBacktestHorizons(event.target.value)}
                    />
                  </label>
                  <label>
                    Benchmark
                    <input
                      type="text"
                      value={backtestBenchmark}
                      onChange={(event) => setBacktestBenchmark(event.target.value)}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={runSelectionBacktest}
                    disabled={isRunningBacktest}
                    data-testid="run-backtest"
                  >
                    <Play aria-hidden="true" size={18} />
                    {isRunningBacktest ? "Running" : "Backtest"}
                  </button>
                </div>
                {selectionBacktestError && (
                  <p className="error">{selectionBacktestError}</p>
                )}
                {selectionBacktest && (
                  <div className="backtest-results" data-testid="backtest-results">
                    <dl className="detail-list">
                      <div>
                        <dt>Result</dt>
                        <dd>{selectionBacktest.id}</dd>
                      </div>
                      <div>
                        <dt>Selection Dates</dt>
                        <dd>{selectionBacktest.selection_dates.length}</dd>
                      </div>
                      <div>
                        <dt>Top N</dt>
                        <dd>{selectionBacktest.top_n}</dd>
                      </div>
                      <div>
                        <dt>Benchmark</dt>
                        <dd>
                          {selectionBacktest.benchmark?.instrument_id ??
                            "not configured"}
                        </dd>
                      </div>
                    </dl>
                    <div className="metric-table">
                      <div className="metric-header">
                        <span>Horizon</span>
                        <span>Obs</span>
                        <span>Avg Return</span>
                        <span>Win Rate</span>
                        <span>Drawdown</span>
                        <span>Excess</span>
                      </div>
                      {Object.entries(selectionBacktest.summary_metrics).map(
                        ([horizon, metrics]) => (
                          <div className="metric-row" key={horizon}>
                            <span>{horizon}</span>
                            <span>{metrics.observation_count}</span>
                            <span>{formatMetric(metrics.average_return)}</span>
                            <span>{formatMetric(metrics.win_rate)}</span>
                            <span>{formatMetric(metrics.max_drawdown)}</span>
                            <span>
                              {formatMetric(metrics.average_excess_return)}
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
              </section>
            </article>
          )}
        </div>
      </section>
      <section className="status-panel snapshots-panel" data-testid="snapshots-panel">
        <div>
          <p className="eyebrow">Result Snapshots</p>
          <h2>Research Memory</h2>
        </div>
        <div className="snapshot-tabs">
          <button
            type="button"
            data-selected={activeSnapshotType === "strategy_run"}
            onClick={() => setActiveSnapshotType("strategy_run")}
            data-testid="strategy-run-snapshots-tab"
          >
            Strategy Runs
          </button>
          <button
            type="button"
            data-selected={activeSnapshotType === "selection_backtest"}
            onClick={() => setActiveSnapshotType("selection_backtest")}
            data-testid="backtest-snapshots-tab"
          >
            Backtests
          </button>
          <button type="button" onClick={refreshResultSnapshots}>
            <RefreshCw aria-hidden="true" size={18} />
            Refresh
          </button>
        </div>
        {snapshotError && <p className="error">{snapshotError}</p>}
        {activeSnapshotType === "strategy_run" && (
          <div className="snapshot-layout">
            <div className="snapshot-list" aria-label="Strategy Run snapshots">
              {strategyRunSnapshots.length === 0 && <p>No Strategy Runs saved yet.</p>}
              {strategyRunSnapshots.map((snapshot) => (
                <div className="snapshot-row" key={snapshot.id}>
                  <label className="compare-toggle">
                    <input
                      type="checkbox"
                      checked={strategyRunComparisonIds.includes(snapshot.id)}
                      data-testid={`compare-strategy-run-${snapshot.id}`}
                      onChange={() =>
                        setStrategyRunComparisonIds((current) =>
                          toggleComparisonId(current, snapshot.id),
                        )
                      }
                    />
                    Compare
                  </label>
                  <button
                    className="snapshot-select"
                    type="button"
                    data-selected={snapshot.id === selectedStrategyRunSnapshotId}
                    onClick={() => setSelectedStrategyRunSnapshotId(snapshot.id)}
                    data-testid={`strategy-run-snapshot-${snapshot.id}`}
                  >
                    <span>{snapshot.strategy_id}</span>
                    <small>{snapshot.as_of_date}</small>
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => compareSelectedSnapshots("strategy_run")}
                disabled={strategyRunComparisonIds.length !== 2}
                data-testid="compare-strategy-runs"
              >
                Compare Runs
              </button>
            </div>
            {selectedStrategyRunSnapshot && (
              <article className="snapshot-detail">
                <h3>{selectedStrategyRunSnapshot.strategy_id}</h3>
                <dl className="detail-list">
                  <div>
                    <dt>Snapshot</dt>
                    <dd>{selectedStrategyRunSnapshot.id}</dd>
                  </div>
                  <div>
                    <dt>As-Of Date</dt>
                    <dd>{selectedStrategyRunSnapshot.as_of_date}</dd>
                  </div>
                  <div>
                    <dt>Market Data</dt>
                    <dd>{selectedStrategyRunSnapshot.market_data_snapshot_ref}</dd>
                  </div>
                  <div>
                    <dt>Source Hash</dt>
                    <dd>{selectedStrategyRunSnapshot.strategy_version.source_hash}</dd>
                  </div>
                </dl>
                <h4>Candidates</h4>
                <div className="candidate-results">
                  {selectedStrategyRunSnapshot.candidates.map((candidate) => (
                    <article className="candidate-row" key={candidate.instrument_id}>
                      <div>
                        <strong>{candidate.instrument_id}</strong>
                        <span>{candidate.explanation}</span>
                      </div>
                      <dl>
                        <div>
                          <dt>Score</dt>
                          <dd>{candidate.score}</dd>
                        </div>
                        <div>
                          <dt>Rank Basis</dt>
                          <dd>{candidate.rank_basis ?? "not provided"}</dd>
                        </div>
                        <div>
                          <dt>Tags</dt>
                          <dd>{candidate.tags.join(", ") || "none"}</dd>
                        </div>
                      </dl>
                      <pre>{JSON.stringify(candidate.metrics, null, 2)}</pre>
                    </article>
                  ))}
                </div>
                {snapshotComparison?.snapshot_type === "strategy_run" &&
                  snapshotComparison.candidate_score_deltas && (
                    <section className="comparison-results">
                      <h4>Comparison</h4>
                      <div className="comparison-table">
                        <div className="comparison-header">
                          <span>Instrument</span>
                          <span>Scores</span>
                          <span>Delta</span>
                        </div>
                        {Object.entries(
                          snapshotComparison.candidate_score_deltas,
                        ).map(([instrumentId, comparison]) => (
                          <div className="comparison-row" key={instrumentId}>
                            <span>{instrumentId}</span>
                            <span>
                              {Object.entries(comparison.values)
                                .map(
                                  ([snapshotId, value]) =>
                                    `${snapshotId.slice(0, 8)}: ${formatMetric(value)}`,
                                )
                                .join(" | ")}
                            </span>
                            <span>{formatMetric(comparison.delta)}</span>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}
              </article>
            )}
          </div>
        )}
        {activeSnapshotType === "selection_backtest" && (
          <div className="snapshot-layout">
            <div className="snapshot-list" aria-label="Backtest snapshots">
              {backtestSnapshots.length === 0 && <p>No Backtests saved yet.</p>}
              {backtestSnapshots.map((snapshot) => (
                <div className="snapshot-row" key={snapshot.id}>
                  <label className="compare-toggle">
                    <input
                      type="checkbox"
                      checked={backtestComparisonIds.includes(snapshot.id)}
                      data-testid={`compare-backtest-${snapshot.id}`}
                      onChange={() =>
                        setBacktestComparisonIds((current) =>
                          toggleComparisonId(current, snapshot.id),
                        )
                      }
                    />
                    Compare
                  </label>
                  <button
                    className="snapshot-select"
                    type="button"
                    data-selected={snapshot.id === selectedBacktestSnapshotId}
                    onClick={() => setSelectedBacktestSnapshotId(snapshot.id)}
                    data-testid={`backtest-snapshot-${snapshot.id}`}
                  >
                    <span>{snapshot.strategy_id}</span>
                    <small>
                      {snapshot.start_date} to {snapshot.end_date}
                    </small>
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => compareSelectedSnapshots("selection_backtest")}
                disabled={backtestComparisonIds.length !== 2}
                data-testid="compare-backtests"
              >
                Compare Backtests
              </button>
            </div>
            {selectedBacktestSnapshot && (
              <article className="snapshot-detail">
                <h3>{selectedBacktestSnapshot.strategy_id}</h3>
                <dl className="detail-list">
                  <div>
                    <dt>Snapshot</dt>
                    <dd>{selectedBacktestSnapshot.id}</dd>
                  </div>
                  <div>
                    <dt>Date Range</dt>
                    <dd>
                      {selectedBacktestSnapshot.start_date} to{" "}
                      {selectedBacktestSnapshot.end_date}
                    </dd>
                  </div>
                  <div>
                    <dt>Market Data</dt>
                    <dd>{selectedBacktestSnapshot.market_data_snapshot_ref}</dd>
                  </div>
                  <div>
                    <dt>Source Hash</dt>
                    <dd>{selectedBacktestSnapshot.strategy_version.source_hash}</dd>
                  </div>
                </dl>
                <h4>Summary Metrics</h4>
                <div className="metric-table">
                  <div className="metric-header">
                    <span>Horizon</span>
                    <span>Obs</span>
                    <span>Avg Return</span>
                    <span>Win Rate</span>
                    <span>Drawdown</span>
                    <span>Excess</span>
                  </div>
                  {Object.entries(selectedBacktestSnapshot.summary_metrics).map(
                    ([horizon, metrics]) => (
                      <div className="metric-row" key={horizon}>
                        <span>{horizon}</span>
                        <span>{metrics.observation_count}</span>
                        <span>{formatMetric(metrics.average_return)}</span>
                        <span>{formatMetric(metrics.win_rate)}</span>
                        <span>{formatMetric(metrics.max_drawdown)}</span>
                        <span>{formatMetric(metrics.average_excess_return)}</span>
                      </div>
                    ),
                  )}
                </div>
                <h4>Per-Date Details</h4>
                <div className="per-date-list">
                  {selectedBacktestSnapshot.selection_results.map((result) => (
                    <details key={result.selection_date}>
                      <summary>{result.selection_date}</summary>
                      <pre>{JSON.stringify(result, null, 2)}</pre>
                    </details>
                  ))}
                </div>
                {snapshotComparison?.snapshot_type === "selection_backtest" &&
                  snapshotComparison.metric_deltas && (
                    <section className="comparison-results">
                      <h4>Comparison</h4>
                      <div className="comparison-table">
                        <div className="comparison-header">
                          <span>Metric</span>
                          <span>Values</span>
                          <span>Delta</span>
                        </div>
                        {Object.entries(snapshotComparison.metric_deltas).flatMap(
                          ([horizon, metrics]) =>
                            Object.entries(metrics).map(([metric, comparison]) => (
                              <div
                                className="comparison-row"
                                key={`${horizon}-${metric}`}
                              >
                                <span>
                                  {horizon} {metric}
                                </span>
                                <span>
                                  {Object.entries(comparison.values)
                                    .map(
                                      ([snapshotId, value]) =>
                                        `${snapshotId.slice(0, 8)}: ${formatMetric(
                                          value,
                                        )}`,
                                    )
                                    .join(" | ")}
                                </span>
                                <span>{formatMetric(comparison.delta)}</span>
                              </div>
                            )),
                        )}
                      </div>
                    </section>
                  )}
              </article>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
