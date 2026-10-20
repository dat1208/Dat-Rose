// Self-update through Tauri's updater plugin.
//
// The app checks a GitHub release (configured in tauri.conf.json), and when a
// newer version exists it downloads and installs it, then restarts. The whole
// app is replaced, so a backend change ships inside the same update.

import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

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

/** Download and install an available update, then restart the app. */
export async function installUpdate(onProgress?: (downloaded: number, total?: number) => void): Promise<void> {
  const update: Update | null = await check();
  if (!update) return;
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
