// Self-update through Tauri's updater plugin.
//
// The app checks a GitHub release (configured in tauri.conf.json), and when a
// newer version exists it downloads and installs it, then restarts. The whole
// app is replaced, so a backend change ships inside the same update.

import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { invoke } from "@tauri-apps/api/core";

export interface UpdateInfo {
  version: string;
  notes: string;
  date?: string;
}

/** Ask GitHub whether a newer release exists; null when up to date. */
export async function checkForUpdate(): Promise<UpdateInfo | null> {
  const update = await check();
  if (!update) return null;
  return { version: update.version, notes: update.body ?? "", date: update.date };
}

/**
 * Stop the Python engine before the installer runs.
 *
 * The engine is a separate process (a sidecar the Rust shell spawns), so the
 * Tauri updater quitting the window does not stop it. A running engine keeps
 * its loaded .pyd/.dll files open, and the NSIS installer then fails with
 * "Error opening file for writing" on the first locked file. Ask it to shut
 * down cleanly and give it a moment to release the files.
 */
async function stopEngine(): Promise<void> {
  try {
    await invoke("api_post", { path: "/api/shutdown", body: {} });
  } catch {
    // Engine already gone, or unreachable: nothing to stop.
    return;
  }
  // The engine runs its cleanup (resume game, deactivate Pengu, kill
  // mod-tools) before exiting; wait for it to release its files.
  await new Promise((resolve) => setTimeout(resolve, 4000));
}

/** Download and install an available update, then restart the app. */
export async function installUpdate(onProgress?: (downloaded: number, total?: number) => void): Promise<void> {
  const update: Update | null = await check();
  if (!update) return;
  await stopEngine();
  let downloaded = 0;
  let total: number | undefined;
  await update.downloadAndInstall((event) => {
    if (event.event === "Started") {
      total = event.data.contentLength;
    } else if (event.event === "Progress") {
      downloaded += event.data.chunkLength;
      onProgress?.(downloaded, total);
    } else if (event.event === "Finished") {
      onProgress?.(total ?? downloaded, total);
    }
  });
  // The update is applied on disk; restart so the new version runs.
  await relaunch();
}
