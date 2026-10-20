import type { Status } from "../api";

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

export function Dashboard({ status, error }: { status: Status | null; error?: string | null }) {
  if (error) {
    return (
      <section>
        <h2>Dashboard</h2>
        <p className="subtitle">Live view of the engine.</p>
        <div className="card">
          <p className="bad">Cannot reach the engine: {error}</p>
          <p className="muted">Is the engine running? Check the Logs tab.</p>
        </div>
      </section>
    );
  }
  if (!status) {
    return (
      <section>
        <h2>Dashboard</h2>
        <p className="subtitle">Live view of the engine.</p>
        <p className="muted">Waiting for the engine…</p>
      </section>
    );
  }

  // While the engine prepares (patcher, hashes, skins) show that instead of
  // an empty dashboard; this used to be a separate launcher window.
  const startup = status.startup;
  if (startup && !startup.ready) {
    return (
      <section>
        <h2>Dashboard</h2>
        <p className="subtitle">Preparing Dat-Rose…</p>
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
      <h2>Dashboard</h2>
      <p className="subtitle">Live view of the engine.</p>

      <div className="card">
        <h3>Session</h3>
        <Row label="App" value={`${status.app} ${status.version}`} />
        <Row label="Phase" value={status.phase || "—"} />
        <Row label="Game mode" value={status.current_game_mode || "—"} />
        <Row label="Locked champion" value={status.locked_champion_id ?? "—"} />
        <Row label="Selected skin" value={status.selected_skin_id ?? "—"} />
        <Row label="Historic mode" value={<Pill on={!!status.historic_mode_active} onText="on" offText="off" />} />
        <Row label="Random mode" value={<Pill on={!!status.random_mode_active} onText="on" offText="off" />} />
        {!inGame && <p className="muted" style={{ marginTop: 12, marginBottom: 0 }}>Enter a champ select to pick a skin.</p>}
      </div>

      {status.downloads && (
        <div className="card">
          <h3>Downloads</h3>
          <Row label="Skins" value={<Pill on={status.downloads.skins_downloaded} />} />
          <Row label="Previews" value={<Pill on={status.downloads.previews_downloaded} />} />
        </div>
      )}
    </section>
  );
}
