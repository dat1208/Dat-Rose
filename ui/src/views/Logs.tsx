import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n";

export function Logs() {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [auto, setAuto] = useState(true);
  const boxRef = useRef<HTMLPreElement>(null);
  // The last text we rendered; used to skip a state update when the log has
  // not grown, so the pane is not rewritten (and reflowed) every poll.
  const lastText = useRef("");

  const refresh = useCallback(async () => {
    try {
      const next = await api.logs(400);
      if (next !== lastText.current) {
        lastText.current = next;
        setText(next);
      }
      setError((prev) => (prev === null ? prev : null));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while auto-refresh is on, so the log follows the engine live. The next
  // poll is scheduled after the previous one settles, so a slow read cannot
  // stack up overlapping requests.
  useEffect(() => {
    if (!auto) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      await refresh();
      if (alive) timer = setTimeout(tick, 2000);
    };
    timer = setTimeout(tick, 2000);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [auto, refresh]);

  useEffect(() => {
    if (auto && boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight;
    }
  }, [text, auto]);

  return (
    <section className="logs-view">
      <h2>{t("Logs")}</h2>
      <p className="subtitle">{t("Live engine output, newest at the bottom.")}</p>
      <div className="logbar">
        <button className="ghost" onClick={refresh}>{t("Refresh")}</button>
        <label>
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> {t("Auto")}
        </label>
      </div>
      {error && <p className="bad">{error}</p>}
      <pre className="logs" ref={boxRef}>
        {text || t("No log output yet.")}
      </pre>
    </section>
  );
}
