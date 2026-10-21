; NSIS installer hooks for Dat-Rose.
;
; The Python engine (dchanger-backend.exe) is a separate, elevated process the
; shell spawns. The Tauri updater quits the window before installing, but that
; does not stop the engine, and a running engine keeps its loaded .pyd/.dll
; files open. The NSIS installer then fails with "Error opening file for
; writing" on the first locked file (e.g. PIL\_imaging.cp32-win_amd64.pyd).
;
; Stop both processes before copying files. The in-app updater already asks the
; engine to shut down cleanly first; this is the safety net for a manual run of
; the installer while the app is open.

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Stopping Dat-Rose and its engine..."
  nsExec::Exec 'taskkill /F /IM dchanger-backend.exe'
  Pop $0
  nsExec::Exec 'taskkill /F /IM Dat-Rose.exe'
  Pop $0
  ; Give Windows a moment to release the file handles.
  Sleep 1500
!macroend
