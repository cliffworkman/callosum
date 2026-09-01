; Tauri's NSIS updater overlays bundle resources but does not remove files that disappeared between releases.
; A Python package upgrade can therefore leave multiple *.dist-info generations beside the new package code,
; causing importlib.metadata to report the wrong dependency version. The app-running check has completed before
; this hook runs. Remove only Callosum-owned immutable bundle resources; NSIS immediately copies fresh versions.
!macro NSIS_HOOK_PREINSTALL
  RMDir /r "$INSTDIR\python-runtime"
  RMDir /r "$INSTDIR\callosum-src"
!macroend
