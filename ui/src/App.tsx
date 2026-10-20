import { useEffect, useState } from "react";
import { api, type Status } from "./api";
import { Dashboard } from "./views/Dashboard";
import { Profiles } from "./views/Profiles";
import { Diagnostics } from "./views/Diagnostics";
import { Logs } from "./views/Logs";
import { checkForUpdate, installUpdate, type UpdateInfo } from "./updater";
import logo from "./assets/logo.png";

type Tab = "dashboard" | "profiles" | "diagnostics" | "logs";

export function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [updating, setUpdating] = useState(false);

  // Poll the engine status; the UI is a read-only view over the Python state.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const next = await api.status();
        if (alive) {
          setStatus(next);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    };
    tick();
    const timer = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  // Check once on startup; a newer release shows a banner instead of a dialog.
  useEffect(() => {
    checkForUpdate().then(setUpdate).catch(() => {});
  }, []);

  const applyUpdate = async () => {
    setUpdating(true);
    try {
      await installUpdate();
    } catch {
      setUpdating(false);
    }
  };

  const engineState = error ? "bad" : status?.engine_ready ? "good" : "warn";
  const engineLabel = error ? "Engine offline" : status?.engine_ready ? "Engine ready" : "Starting…";

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <img className="mark" src={logo} alt="" />
          <h1>Dat-Rose</h1>
        </div>
        <nav>
          <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>
            Dashboard
          </button>
          <button className={tab === "profiles" ? "active" : ""} onClick={() => setTab("profiles")}>
            Profiles
          </button>
          <button className={tab === "diagnostics" ? "active" : ""} onClick={() => setTab("diagnostics")}>
            Diagnostics
          </button>
          <button className={tab === "logs" ? "active" : ""} onClick={() => setTab("logs")}>
            Logs
          </button>
        </nav>
        <div className="engine-state">
          <span className={`dot ${engineState}`} />
          <span className={engineState}>{engineLabel}</span>
        </div>
      </aside>
      <main className="content">
        {update && (
          <div className="update-banner">
            <span>
              Version <strong>{update.version}</strong> is available.
            </span>
            <button onClick={applyUpdate} disabled={updating}>
              {updating ? "Updating…" : "Update now"}
            </button>
          </div>
        )}
        {tab === "dashboard" && <Dashboard status={status} error={error} />}
        {tab === "profiles" && <Profiles />}
        {tab === "diagnostics" && <Diagnostics />}
        {tab === "logs" && <Logs />}
      </main>
    </div>
  );
}
