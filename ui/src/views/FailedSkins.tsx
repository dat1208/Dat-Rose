import { useEffect, useState } from "react";
import { api, type FailedSkin } from "../api";
import { useI18n } from "../i18n";

// Skins that failed to download or extract. The engine records them in
// failed_skins.json; here they are listed with a per-file retry.
export function FailedSkins() {
  const { t } = useI18n();
  const [files, setFiles] = useState<FailedSkin[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const data = await api.failedSkins();
      setFiles(data.files);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const retry = async (path: string) => {
    setBusy(path);
    setMessage(null);
    try {
      const res = await api.retrySkin(path);
      setMessage(res.retried ? t("Retried {name}", { name: path }) : t("Retry failed: {error}", { error: path }));
      await refresh();
    } catch (e) {
      setMessage(t("Retry failed: {error}", { error: e instanceof Error ? e.message : String(e) }));
    } finally {
      setBusy(null);
    }
  };

  const retryAll = async () => {
    for (const f of files) {
      // Sequential so we do not hammer the raw host; refresh happens at the end.
      // eslint-disable-next-line no-await-in-loop
      await retry(f.path);
    }
  };

  return (
    <section>
      <h2>{t("Failed skins")}</h2>
      <p className="subtitle">{t("Skins that failed to download. Retry them individually.")}</p>

      <div className="card">
        {error && <p className="bad">{error}</p>}
        {files.length ? (
          <>
            <div className="logbar">
              <button onClick={retryAll} disabled={!!busy}>{t("Retry all")}</button>
            </div>
            <ul className="profiles">
              {files.map((f) => (
                <li key={f.path}>
                  <span className="name">
                    {f.path}
                    {f.reason ? <span className="muted"> — {f.reason}</span> : null}
                  </span>
                  <span className="actions">
                    <button className="ghost" onClick={() => retry(f.path)} disabled={busy === f.path}>
                      {busy === f.path ? t("Retrying…") : t("Retry")}
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">{t("No failed skins.")}</p>
        )}
      </div>

      {message && <p className="message">{message}</p>}
    </section>
  );
}
