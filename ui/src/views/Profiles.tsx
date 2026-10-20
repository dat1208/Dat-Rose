import { useEffect, useState } from "react";
import { api, type Account, type ProfilesResponse } from "../api";

export function Profiles() {
  const [data, setData] = useState<ProfilesResponse | null>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [profiles, current] = await Promise.all([api.profiles(), api.account()]);
      setData(profiles);
      setAccount(current);
      // Default the name field to the signed-in summoner's name.
      if (current.name && !name) setName(current.name);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (action: () => Promise<unknown>, ok: string) => {
    try {
      await action();
      setMessage(ok);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const saveCurrent = () => {
    if (!account?.puuid) return;
    run(() => api.saveProfile(account.puuid!, name || account.name || ""), "Profile saved");
  };

  return (
    <section>
      <h2>Profiles</h2>
      <p className="subtitle">One set of skin choices per League account.</p>

      <div className="card">
        <h3>Current account</h3>
        {account?.puuid ? (
          <>
            <p>
              Signed in as <strong>{account.name || "unknown"}</strong>
            </p>
            <div className="form">
              <input
                placeholder="Display name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <button onClick={saveCurrent}>Save current account</button>
            </div>
          </>
        ) : (
          <p className="muted">Open the League client to detect your account.</p>
        )}
      </div>

      <div className="card">
        <h3>Stored profiles</h3>
        {data?.profiles.length ? (
          <ul className="profiles">
            {data.profiles.map((p) => (
              <li key={p.puuid}>
                <span className={`name ${p.puuid === data.current ? "active" : ""}`}>
                  {p.name} {p.puuid === data.current ? "· active" : ""}
                </span>
                <span className="actions">
                  <button className="ghost" onClick={() => run(() => api.loadProfile(p.puuid), "Profile loaded")}>Load</button>
                  <button className="ghost" onClick={() => run(() => api.deleteProfile(p.puuid), "Profile deleted")}>Delete</button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No profiles yet.</p>
        )}
      </div>

      {message && <p className="message">{message}</p>}
    </section>
  );
}
