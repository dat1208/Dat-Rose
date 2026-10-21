import { useEffect, useState } from "react";
import { api, type Account, type ProfilesResponse } from "../api";
import { useI18n } from "../i18n";

export function Profiles() {
  const { t } = useI18n();
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
    run(() => api.saveProfile(account.puuid!, name || account.name || ""), t("Profile saved"));
  };

  return (
    <section>
      <h2>{t("Profiles")}</h2>
      <p className="subtitle">{t("One set of skin choices per League account.")}</p>

      <div className="card">
        <h3>{t("Current account")}</h3>
        {account?.puuid ? (
          <>
            <p>
              {t("Signed in as {name}", { name: account.name || t("unknown") })}
            </p>
            <div className="form">
              <input
                placeholder={t("Display name")}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <button onClick={saveCurrent}>{t("Save current account")}</button>
            </div>
          </>
        ) : (
          <p className="muted">{t("Open the League client to detect your account.")}</p>
        )}
      </div>

      <div className="card">
        <h3>{t("Stored profiles")}</h3>
        {data?.profiles.length ? (
          <ul className="profiles">
            {data.profiles.map((p) => (
              <li key={p.puuid}>
                <span className={`name ${p.puuid === data.current ? "active" : ""}`}>
                  {p.name} {p.puuid === data.current ? `· ${t("active")}` : ""}
                </span>
                <span className="actions">
                  <button className="ghost" onClick={() => run(() => api.loadProfile(p.puuid), t("Profile loaded"))}>{t("Load")}</button>
                  <button className="ghost" onClick={() => run(() => api.deleteProfile(p.puuid), t("Profile deleted"))}>{t("Delete")}</button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">{t("No profiles yet.")}</p>
        )}
      </div>

      {message && <p className="message">{message}</p>}
    </section>
  );
}
