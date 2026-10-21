import { useEffect, useState } from "react";
import { api, type Updates } from "../api";
import { checkForUpdate, installUpdate, type UpdateInfo } from "../updater";
import { useI18n } from "../i18n";

export function Diagnostics() {
  const { t } = useI18n();
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
      setUpdateMsg(info ? t("Version {version} is available.", { version: info.version }) : t("You are up to date."));
    } catch (e) {
      setUpdateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setUpdateBusy(false);
    }
  };

  const doUpdate = async () => {
    setUpdateBusy(true);
    setUpdateMsg(t("Downloading update…"));
    try {
      await installUpdate((done, total) => {
        setUpdateMsg(total ? t("Downloading… {percent}%", { percent: Math.round((done / total) * 100) }) : t("Downloading…"));
      });
      // relaunch() restarts the app, so this only runs if it did not.
      setUpdateMsg(t("Update installed. Restarting…"));
    } catch (e) {
      setUpdateMsg(e instanceof Error ? e.message : String(e));
      setUpdateBusy(false);
    }
  };

  return (
    <section>
      <h2>{t("Diagnostics")}</h2>
      <p className="subtitle">{t("Problems the engine hit, and the versions it tracks.")}</p>

      <div className="card">
        <h3>{t("App update")}</h3>
        {updateMsg && <p className="muted">{updateMsg}</p>}
        <div className="logbar">
          <button className="ghost" onClick={checkApp} disabled={updateBusy}>
            {t("Check for updates")}
          </button>
          {appUpdate && (
            <button onClick={doUpdate} disabled={updateBusy}>
              {t("Install {version}", { version: appUpdate.version })}
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <h3>{t("Problems")}</h3>
        {issues.length ? (
          <ul className="issues">
            {issues.map((line, i) => (
              <li key={i} className={line.startsWith("Fix:") ? "fix" : ""}>
                {line}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">{t("No problems reported.")}</p>
        )}
      </div>

      <div className="card">
        <h3>{t("Upstream versions")}</h3>
        {loading && <p className="muted">{t("Checking…")}</p>}
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
          {t("Re-check")}
        </button>
      </div>
    </section>
  );
}
