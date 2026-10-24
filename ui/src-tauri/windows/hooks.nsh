; NSIS installer hooks for Dat-Rose.
;
; The Python engine (dchanger-backend.exe) is a separate, elevated process the
; shell spawns through the UAC "runas" verb. The Tauri updater quits the window
; before installing, but that does not stop the engine, and a running engine
; keeps its loaded .pyd/.dll files open. The installer then fails with
; "Error opening file for writing" on the first locked file
; (e.g. PIL\_imaging.cp312-win_amd64.pyd).
;
; The engine needs a moment to run its cleanup (resume the game, deactivate
; Pengu, kill mod-tools), so ask it to stop first and only force it if it hangs.
; The installer is elevated, so taskkill can reach the elevated engine.

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Stopping Dat-Rose and its engine..."
  nsExec::Exec 'taskkill /F /IM Dat-Rose.exe'
  Pop $0

  ; Ask the engine to shut down cleanly. Best effort: a missing engine is fine.
  nsExec::Exec 'powershell -NoProfile -NonInteractive -Command "try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:56700/api/shutdown -TimeoutSec 3 | Out-Null } catch { }"'
  Pop $0

  ; Wait for it to exit, then force it.
  nsExec::Exec 'powershell -NoProfile -NonInteractive -Command "Wait-Process -Name dchanger-backend -Timeout 10 -ErrorAction SilentlyContinue"'
  Pop $0
  nsExec::Exec 'taskkill /F /IM dchanger-backend.exe'
  Pop $0

  ; Give Windows a moment to release the file handles.
  Sleep 2000
!macroend
