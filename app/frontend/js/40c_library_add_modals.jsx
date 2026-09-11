// The library "add / import" modal cluster, split out of 40_app.jsx (issue #58, rule #1 600-line cap).
// A function declaration hoisted across the shared esbuild IIFE, so App (40_app.jsx) renders it unchanged.
// Pure wiring: it only chooses which add/import modal is open and hands each its close + refresh callbacks.
function LibraryAddModals({
  scanOpen, importOpen, addDoiOpen, zoteroImportOpen, bundleImportOpen, sharedWithMeOpen,
  onCloseScan, onCloseImport, onCloseAddDoi, onCloseZotero, onCloseBundle, onCloseShared,
  onShowUnsorted, refreshLibrary, refreshLibraryAndAxes, onSharedOpenSettings,
}) {
  return (
    <>
      {scanOpen && <ScanModal onClose={onCloseScan} onScanned={refreshLibrary} onShowUnsorted={onShowUnsorted} />}
      {importOpen && <ImportModal onClose={onCloseImport} onImported={refreshLibrary} />}
      {addDoiOpen && <AddDoiModal onClose={onCloseAddDoi} onImported={refreshLibrary} />}
      {zoteroImportOpen && <ZoteroImportModal onClose={onCloseZotero} onImported={refreshLibraryAndAxes} />}
      {bundleImportOpen && <BundleImportModal onClose={onCloseBundle} onImported={refreshLibraryAndAxes} />}
      {sharedWithMeOpen &&
        <SharedWithMeModal onClose={onCloseShared} onImported={refreshLibraryAndAxes} onOpenSettings={onSharedOpenSettings} />}
    </>
  );
}
