; connector-identity.generated.nsh is produced by packaging/generate_connector_nsh.py from
; connector/identity.json -- CONNECTOR_NATIVE_HOST_NAME and the CONNECTOR_WRITE_ALLOWED_ORIGINS_JSON
; macro come from there, not repeated here.
!include "connector-identity.generated.nsh"

!define CONNECTOR_CHROME_KEY "Software\Google\Chrome\NativeMessagingHosts\${CONNECTOR_NATIVE_HOST_NAME}"
!define CONNECTOR_EDGE_KEY "Software\Microsoft\Edge\NativeMessagingHosts\${CONNECTOR_NATIVE_HOST_NAME}"

; Tauri's NSIS updater overlays bundle resources but does not remove files that changed between releases.
; Source is still an app resource, so replace it as one immutable unit. Do NOT remove a legacy python-runtime
; directory here: the first persistent-runtime release can verify and copy that old bundle into per-user local
; data, avoiding a redundant one-time download for existing Windows installations. New installers contain no
; python-runtime resource; all later runtime versions live outside $INSTDIR and are unaffected by this hook.
!macro NSIS_HOOK_PREINSTALL
  RMDir /r "$INSTDIR\callosum-src"
  ; The connector host binary is a bundled resource exactly like callosum-src above -- replace it as
  ; one immutable unit rather than letting a stale prior-version exe linger beside a fresh manifest.
  RMDir /r "$INSTDIR\connector"
!macroend

; ---------------------------------------------------------------------------------------------
; Browser-capture connector registration (#61 Phase 2, Part 2).
;
; Registers a Chrome/Edge native-messaging host manifest pointing at the connector binary this same
; installer just wrote to $INSTDIR\connector\. HKCU only -- installMode is "currentUser" for this
; whole installer, so this introduces no elevation requirement beyond what already exists.
;
; Ownership is exact-path in both directions:
;   - install:   only ever point the registry at THIS install's manifest file.
;   - uninstall: only ever remove a registry value that STILL points at THIS install's manifest
;                file (exact string equality, not "starts with $INSTDIR" -- see PREUNINSTALL), and
;                only outside update mode (see below). A third-party NativeMessagingHosts sibling
;                registered under a different name is never read, written, or deleted by either
;                hook; a DIFFERENT Callosum install's manifest path is never matched either.
; ---------------------------------------------------------------------------------------------

!macro NSIS_HOOK_POSTINSTALL
  ; $INSTDIR is only known now, at install time, so the manifest is generated here rather than
  ; baked in at build time. allowed_origins and the host name ARE known at build time and come
  ; from connector-identity.generated.nsh (above), which is the one place identity.json's values
  ; become NSIS text.
  ;
  ; JSON needs backslashes escaped, but Windows (and Chrome's own native-host launcher, which uses
  ; CreateProcess) accepts forward slashes interchangeably -- the same technique backend.rs's own
  ; sqlite:/// db_url construction already uses ("sqlite:/// URLs want forward slashes even on
  ; Windows"), applied here to sidestep JSON escaping entirely rather than hand-rolling it in NSIS.
  nsis_tauri_utils::StrReplace "$INSTDIR" "\" "/"
  Pop $0

  FileOpen $1 "$INSTDIR\connector\${CONNECTOR_NATIVE_HOST_NAME}.json" w
  FileWrite $1 '{$\r$\n'
  FileWrite $1 '  "name": "${CONNECTOR_NATIVE_HOST_NAME}",$\r$\n'
  FileWrite $1 '  "description": "Callosum browser-capture connector",$\r$\n'
  FileWrite $1 '  "path": "$0/connector/callosum-connector.exe",$\r$\n'
  FileWrite $1 '  "type": "stdio",$\r$\n'
  FileWrite $1 '  "allowed_origins": '
  !insertmacro CONNECTOR_WRITE_ALLOWED_ORIGINS_JSON
  FileWrite $1 '}$\r$\n'
  FileClose $1

  WriteRegStr HKCU "${CONNECTOR_CHROME_KEY}" "" "$INSTDIR\connector\${CONNECTOR_NATIVE_HOST_NAME}.json"
  WriteRegStr HKCU "${CONNECTOR_EDGE_KEY}" "" "$INSTDIR\connector\${CONNECTOR_NATIVE_HOST_NAME}.json"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; Tauri's own updater runs the OLD version's uninstaller with /UPDATE before the new version's
  ; files land -- confirmed against the actual NSIS template Tauri embeds (not assumed): the
  ; installer, when itself launched with /UPDATE by tauri-plugin-updater, re-invokes
  ; "$INSTDIR\uninstall.exe" with /UPDATE appended to its own recorded UninstallString. The stock
  ; template guards shortcut/autostart removal the same way (${If} $UpdateMode <> 1) for exactly
  ; this reason. Without the same guard here, EVERY auto-update would silently unregister the
  ; connector, breaking capture with no obvious cause until a manual reinstall.
  ${If} $UpdateMode <> 1
    StrCpy $9 "$INSTDIR\connector\${CONNECTOR_NATIVE_HOST_NAME}.json"

    ReadRegStr $8 HKCU "${CONNECTOR_CHROME_KEY}" ""
    ${If} $8 == $9
      DeleteRegKey HKCU "${CONNECTOR_CHROME_KEY}"
    ${EndIf}

    ReadRegStr $8 HKCU "${CONNECTOR_EDGE_KEY}" ""
    ${If} $8 == $9
      DeleteRegKey HKCU "${CONNECTOR_EDGE_KEY}"
    ${EndIf}
  ${EndIf}
!macroend
