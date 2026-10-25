import { memo } from "react";
import type { Status } from "../api";
import { useI18n } from "../i18n";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="row">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

function Pill({ on, onText = "ready", offText = "pending" }: { on: boolean; onText?: string; offText?: string }) {
  return <span className={`pill ${on ? "good" : "warn"}`}>{on ? onText : offText}</span>;
}

// Memoised so the 2s status poll only re-renders the dashboard when the status
// object actually changed (App keeps the reference stable otherwise).
export const Dashboard = memo(function Dashboard({ status, error }: { status: Status | null; error?: string | null }) {
  const { t } = useI18n();

  if (error) {
    return (
      <section>
        <h2>{t("Dashboard")}</h2>
        <p className="subtitle">{t("Live view of the engine.")}</p>
        <div className="card">
          <p className="bad">{t("Cannot reach the engine: {error}", { error })}</p>
          <p className="muted">{t("Is the engine running? Check the Logs tab.")}</p>
        </div>
      </section>
    );
  }
  if (!status) {
    return (
      <section>
        <h2>{t("Dashboard")}</h2>
        <p className="subtitle">{t("Live view of the engine.")}</p>
        <p className="muted">{t("Waiting for the engine…")}</p>
      </section>
    );
  }

  // While the engine prepares (patcher, hashes, skins) show that instead of
  // an empty dashboard; this used to be a separate launcher window.
  const startup = status.startup;
  if (startup && !startup.ready) {
    return (
      <section>
        <h2>{t("Dashboard")}</h2>
        <p className="subtitle">{t("Preparing Dat-Rose…")}</p>
        <div className="card">
          <h3>{startup.message}</h3>
          {startup.detail && <p className="muted">{startup.detail}</p>}
          {startup.error ? (
            <p className="bad">{startup.error}</p>
          ) : (
            <div className="progress">
              <div className={`bar ${startup.marquee ? "marquee" : ""}`} style={{ width: `${startup.progress}%` }} />
            </div>
          )}
        </div>
      </section>
    );
  }

  const inGame = status.phase && status.phase !== "None" && status.phase !== "Lobby";

  return (
    <section>
      <h2>{t("Dashboard")}</h2>
      <p className="subtitle">{t("Live view of the engine.")}</p>

      <div className="card">
        <h3>{t("Session")}</h3>
        <Row label={t("App")} value={`${status.app} ${status.version}`} />
        <Row label={t("Phase")} value={status.phase || "—"} />
        <Row label={t("Game mode")} value={status.current_game_mode || "—"} />
        <Row label={t("Locked champion")} value={status.locked_champion_id ?? "—"} />
        <Row label={t("Selected skin")} value={status.selected_skin_id ?? "—"} />
        <Row label={t("Historic mode")} value={<Pill on={!!status.historic_mode_active} onText={t("on")} offText={t("off")} />} />
        <Row label={t("Random mode")} value={<Pill on={!!status.random_mode_active} onText={t("on")} offText={t("off")} />} />
        {!inGame && <p className="muted" style={{ marginTop: 12, marginBottom: 0 }}>{t("Enter a champ select to pick a skin.")}</p>}
      </div>

      {status.downloads && (
        <div className="card">
          <h3>{t("Downloads")}</h3>
          <Row label={t("Skins")} value={<Pill on={status.downloads.skins_downloaded} onText={t("ready")} offText={t("pending")} />} />
          <Row label={t("Previews")} value={<Pill on={status.downloads.previews_downloaded} onText={t("ready")} offText={t("pending")} />} />
        </div>
      )}
    </section>
  );
});
