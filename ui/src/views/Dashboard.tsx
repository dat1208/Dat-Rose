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
  const champion = status.locked_champion_id ?? null;
  const skin = status.selected_skin_id ?? null;

  return (
    <section>
      <h2>{t("Dashboard")}</h2>
      <p className="subtitle">{t("Live view of the engine.")}</p>

      <div className="hero">
        <div className="eyebrow">{inGame ? t("In champ select") : t("Waiting for champ select")}</div>
        <p className="hero-title">
          {champion !== null ? (
            <>
              {t("Champion ID")} <span className="accent">#{champion}</span>
            </>
          ) : (
            <span className="accent">{t("No champion locked")}</span>
          )}
        </p>
        <p className="hero-sub">
          {skin !== null ? t("Selected skin: #{id}", { id: skin }) : t("Enter a champ select to pick a skin.")}
        </p>
      </div>

      <div className="tiles">
        <div className="tile">
          <div className="tile-label">{t("Phase")}</div>
          <div className="tile-value">{status.phase || "—"}</div>
        </div>
        <div className="tile">
          <div className="tile-label">{t("Game mode")}</div>
          <div className="tile-value">{status.current_game_mode || "—"}</div>
        </div>
        <div className="tile">
          <div className="tile-label">{t("Historic mode")}</div>
          <div className="tile-value">
            <Pill on={!!status.historic_mode_active} onText={t("on")} offText={t("off")} />
          </div>
        </div>
        <div className="tile">
          <div className="tile-label">{t("Random mode")}</div>
          <div className="tile-value">
            <Pill on={!!status.random_mode_active} onText={t("on")} offText={t("off")} />
          </div>
        </div>
      </div>

      <div className="card">
        <h3>{t("Session")}</h3>
        <Row label={t("App")} value={`${status.app} ${status.version}`} />
        <Row label={t("Locked champion")} value={champion ?? "—"} />
        <Row label={t("Selected skin")} value={skin ?? "—"} />
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
