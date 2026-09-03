; Tauri's NSIS updater overlays bundle resources but does not remove files that changed between releases.
; Source is still an app resource, so replace it as one immutable unit. Do NOT remove a legacy python-runtime
; directory here: the first persistent-runtime release can verify and copy that old bundle into per-user local
; data, avoiding a redundant one-time download for existing Windows installations. New installers contain no
; python-runtime resource; all later runtime versions live outside $INSTDIR and are unaffected by this hook.
!macro NSIS_HOOK_PREINSTALL
  RMDir /r "$INSTDIR\callosum-src"
!macroend
