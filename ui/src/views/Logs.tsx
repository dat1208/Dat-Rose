import { useEffect, useRef, useState } from "react";
import { api } from "../api";

export function Logs() {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [auto, setAuto] = useState(true);
  const boxRef = useRef<HTMLPreElement>(null);

  const refresh = async () => {
    try {
      setText(await api.logs(400));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  // Poll while auto-refresh is on, so the log follows the engine live.
  useEffect(() => {
    if (!auto) return;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [auto]);

  useEffect(() => {
    if (auto && boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight;
    }
  }, [text, auto]);

  return (
    <section>
      <h2>Logs</h2>
      <p className="subtitle">Live engine output, newest at the bottom.</p>
      <div className="logbar">
        <button className="ghost" onClick={refresh}>Refresh</button>
        <label>
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Auto
        </label>
      </div>
      {error && <p className="bad">{error}</p>}
      <pre className="logs" ref={boxRef}>
        {text || "No log output yet."}
      </pre>
    </section>
  );
}
