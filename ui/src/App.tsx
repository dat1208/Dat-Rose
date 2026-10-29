import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Status } from "./api";
import { Dashboard } from "./views/Dashboard";
import { Profiles } from "./views/Profiles";
import { Diagnostics } from "./views/Diagnostics";
import { Logs } from "./views/Logs";
import { FailedSkins } from "./views/FailedSkins";
import { checkForUpdate, installUpdate, type UpdateInfo } from "./updater";
import { useI18n } from "./i18n";
import logo from "./assets/logo.png";

type Tab = "dashboard" | "profiles" | "failed" | "diagnostics" | "logs";

// Inline 18px stroke icons so the collapsed rail reads at a glance without
// pulling in an icon package.
const svg = (path: ReactNode) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {path}
  </svg>
);

const icons = {
  dashboard: svg(
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  profiles: svg(
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </>
  ),
  failed: svg(
    <>
      <path d="M10.3 3.9 2.5 17.4A1.8 1.8 0 0 0 4 20h16a1.8 1.8 0 0 0 1.5-2.6L13.7 3.9a1.9 1.9 0 0 0-3.4 0Z" />
      <path d="M12 9v4" />
      <path d="M12 16.5h.01" />
    </>
  ),
  diagnostics: svg(<path d="M3 12h4l2.5-6 4 12 2.5-6h5" />),
  logs: svg(
    <>
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="m7 9 3 3-3 3" />
      <path d="M13 15h4" />
    </>
  ),
  globe: svg(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18Z" />
    </>
  ),
};

const NAV: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: "dashboard", label: "Dashboard", icon: icons.dashboard },
  { id: "profiles", label: "Profiles", icon: icons.profiles },
  { id: "failed", label: "Failed skins", icon: icons.failed },
  { id: "diagnostics", label: "Diagnostics", icon: icons.diagnostics },
  { id: "logs", label: "Logs", icon: icons.logs },
];

export function App() {
  const { t, language, setLanguage } = useI18n();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [updating, setUpdating] = useState(false);

  // Poll the engine status; the UI is a read-only view over the Python state.
  //
  // The status object is only replaced when something the UI renders actually
  // changed. Every poll used to hand React a fresh object, which re-rendered the
  // whole tree every 2s and made clicks feel like they stalled.
  const lastStatus = useRef("");
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const next = await api.status();
        if (!alive) return;
        // Compare the serialised form: cheap, and the payload is tiny.
        const key = JSON.stringify(next);
        if (key !== lastStatus.current) {
          lastStatus.current = key;
          setStatus(next);
        }
        setError((prev) => (prev === null ? prev : null));
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
      // Chain the next poll only after this one settled, so a slow engine
      // cannot pile up overlapping requests.
      if (alive) timer = setTimeout(tick, 2000);
    };
    tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
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
  const engineLabel = error ? t("Engine offline") : status?.engine_ready ? t("Engine ready") : t("Starting…");

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <img className="mark" src={logo} alt="" />
          <h1>Dat-Rose</h1>
        </div>
        <nav>
          {NAV.map(({ id, label, icon }) => (
            <button
              key={id}
              className={tab === id ? "active" : ""}
              title={t(label)}
              aria-label={t(label)}
              onClick={() => setTab(id)}
            >
              <span className="nav-icon">{icon}</span>
              <span className="nav-label">{t(label)}</span>
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <label className="lang-switch" title={t("Language")}>
          <span className="nav-icon">{icons.globe}</span>
          <span className="sr-only">{t("Language")}</span>
          <select
            value={language}
            aria-label={t("Language")}
            onChange={(e) => setLanguage(e.target.value as "en" | "vi")}
          >
            <option value="en">{t("English")}</option>
            <option value="vi">{t("Tiếng Việt")}</option>
          </select>
        </label>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="crumb">
            <strong>Dat-Rose</strong>
            <span className="sep">/</span>
            <span>{t(NAV.find((n) => n.id === tab)?.label ?? "Dashboard")}</span>
          </div>
          <span className={`status-chip ${engineState}`}>
            <span className={`dot ${engineState}`} />
            {engineLabel}
          </span>
        </header>
        <main className="content">
          {update && (
            <div className="update-banner">
              <span>{t("Version {version} is available.", { version: update.version })}</span>
              <button onClick={applyUpdate} disabled={updating}>
                {updating ? t("Updating…") : t("Update now")}
              </button>
            </div>
          )}
          {tab === "dashboard" && <Dashboard status={status} error={error} />}
          {tab === "profiles" && <Profiles />}
          {tab === "failed" && <FailedSkins />}
          {tab === "diagnostics" && <Diagnostics />}
          {tab === "logs" && <Logs />}
        </main>
      </div>
    </div>
  );
}
