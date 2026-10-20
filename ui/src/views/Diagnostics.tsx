import { useEffect, useState } from "react";
import { api, type Updates } from "../api";
import { checkForUpdate, installUpdate, type UpdateInfo } from "../updater";

export function Diagnostics() {
  const [updates, setUpdates] = useState<Updates | null>(null);
  const [issues, setIssues] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [appUpdate, setAppUpdate] = useState<UpdateInfo | null>(null);
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);

  const check = async () => {
    setLoading(true);
    try {
      const [u, d] = await Promise.all([api.updates(), api.diagnostics()]);
      setUpdates(u);
      setIssues(d.issues);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    check();
  }, []);

  const checkApp = async () => {
    setUpdateBusy(true);
    setUpdateMsg(null);
    try {
      const info = await checkForUpdate();
      setAppUpdate(info);
      setUpdateMsg(info ? `Version ${info.version} is available.` : "You are up to date.");
    } catch (e) {
      setUpdateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setUpdateBusy(false);
    }
  };

  const doUpdate = async () => {
    setUpdateBusy(true);
    setUpdateMsg("Downloading update…");
    try {
      await installUpdate((done, total) => {
        setUpdateMsg(total ? `Downloading… ${Math.round((done / total) * 100)}%` : "Downloading…");
      });
      // relaunch() restarts the app, so this only runs if it did not.
      setUpdateMsg("Update installed. Restarting…");
    } catch (e) {
      setUpdateMsg(e instanceof Error ? e.message : String(e));
      setUpdateBusy(false);
    }
  };

  return (
    <section>
      <h2>Diagnostics</h2>
      <p className="subtitle">Problems the engine hit, and the versions it tracks.</p>

      <div className="card">
        <h3>App update</h3>
        {updateMsg && <p className="muted">{updateMsg}</p>}
        <div className="logbar">
          <button className="ghost" onClick={checkApp} disabled={updateBusy}>
            Check for updates
          </button>
          {appUpdate && (
            <button onClick={doUpdate} disabled={updateBusy}>
              Install {appUpdate.version}
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Problems</h3>
        {issues.length ? (
          <ul className="issues">
            {issues.map((line, i) => (
              <li key={i} className={line.startsWith("Fix:") ? "fix" : ""}>
                {line}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No problems reported.</p>
        )}
      </div>

      <div className="card">
        <h3>Upstream versions</h3>
        {loading && <p className="muted">Checking…</p>}
        {error && <p className="bad">{error}</p>}
        {updates && (
          <ul className="kv">
            <li>LTK Manager: {updates.ltk_manager ?? "—"}</li>
            <li>LeagueSkins: {updates.league_skins_sha?.slice(0, 8) ?? "—"}</li>
            <li>Pengu Loader: {updates.pengu_loader ?? "—"}</li>
            <li>Rose upstream: {updates.rose ?? "—"}</li>
          </ul>
        )}
        <button className="ghost" onClick={check} disabled={loading}>
          Re-check
        </button>
      </div>
    </section>
  );
}

