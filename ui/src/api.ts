// Client for the Python engine's local JSON API (backend/api.py).
//
// Requests go through Rust commands (api_get / api_post in src-tauri/src/main.rs)
// rather than a direct fetch: a packaged Tauri window runs on its own origin and
// the platform webview blocks cross-host fetches, so the request is made in Rust
// and the JSON comes back over IPC.

import { invoke } from "@tauri-apps/api/core";

export interface Startup {
  message: string;
  detail: string;
  progress: number;
  marquee: boolean;
  ready: boolean;
  error: string;
}

export interface Status {
  app: string;
  version: string;
  engine_ready: boolean;
  phase?: string | null;
  locked_champion_id?: number | null;
  selected_skin_id?: number | null;
  current_game_mode?: string | null;
  historic_mode_active?: boolean;
  random_mode_active?: boolean;
  startup?: Startup;
  downloads?: {
    skins_downloaded: boolean;
    previews_downloaded: boolean;
    all_ready: boolean;
  };
}

export interface Profile {
  puuid: string;
  name: string;
  updated_at: number;
}

export interface ProfilesResponse {
  current: string | null;
  profiles: Profile[];
}

export interface Account {
  puuid: string | null;
  name: string | null;
}

export interface Updates {
  ltk_manager: string | null;
  league_skins_sha: string | null;
  pengu_loader: string | null;
  rose: string | null;
}

export interface DiagnosticsResponse {
  issues: string[];
}

export interface FailedSkin {
  path: string;
  reason: string;
}

export interface FailedSkinsResponse {
  files: FailedSkin[];
}

// A failed invoke rejects with the Rust error string; normalise it to Error.
function toError(e: unknown): Error {
  return e instanceof Error ? e : new Error(String(e));
}

async function get<T>(path: string): Promise<T> {
  try {
    return (await invoke("api_get", { path })) as T;
  } catch (e) {
    throw toError(e);
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  try {
    return (await invoke("api_post", { path, body })) as T;
  } catch (e) {
    throw toError(e);
  }
}

export const api = {
  status: () => get<Status>("/api/status"),
  profiles: () => get<ProfilesResponse>("/api/profiles"),
  account: () => get<Account>("/api/account"),
  updates: () => get<Updates>("/api/updates"),
  diagnostics: () => get<DiagnosticsResponse>("/api/diagnostics"),
  failedSkins: () => get<FailedSkinsResponse>("/api/skins/failed"),
  retrySkin: (path: string) =>
    post<{ retried: boolean; path: string }>("/api/skins/retry", { path }),
  saveProfile: (puuid: string, name: string) =>
    post<{ puuid: string; name: string }>("/api/profiles/save", { puuid, name }),
  loadProfile: (puuid: string) =>
    post<{ loaded: boolean }>("/api/profiles/load", { puuid }),
  deleteProfile: (puuid: string) =>
    post<{ deleted: boolean }>("/api/profiles/delete", { puuid }),
  logs: (lines = 300) => invoke<string>("read_logs", { lines }),
};
