// Browser-runtime seams that must initialize before 00_lib.jsx evaluates its API configuration.

// The ordinary app has no provider and continues through the authenticated browser fetch in 00_lib. The explicit
// demo build injects one immutable provider before this script runs; every Callosum request (including PDF bytes
// and downloads) passes through this function, so the static artifact has no path to a live backend.
const CALLOSUM_DEMO = window.CALLOSUM_DEMO || null;
function isDemoMode() { return !!CALLOSUM_DEMO; }
function explainDemoLock(message, path) {
  if (!isDemoMode()) return false;
  window.dispatchEvent(new CustomEvent("callosum:demo-blocked", {
    detail: { message: message || "That operation is unavailable in the online demo.", path: path || "" },
  }));
  return true;
}
function demoWorkspaceCapability(workspaceId, tabId) {
  if (!isDemoMode()) return null;
  const capabilities = CALLOSUM_DEMO.workspace_capabilities || {};
  return capabilities[tabId ? workspaceId + "." + tabId : workspaceId] || null;
}
function DemoMethodAction({ label }) {
  if (!isDemoMode()) return null;
  return (
    <div className="statcheck-actions demo-method-action">
      <button className="btn-link" disabled title="Computation is unavailable in the static online demo.">{label}</button>
      <span className="statcheck-asof">saved result · inspectable only</span>
    </div>
  );
}
function callosumFetch(input, init) {
  const provider = window.CALLOSUM_DATA_PROVIDER;
  if (provider && typeof provider.fetch === "function") return provider.fetch(input, init || {});
  return window.fetch(input, init);
}

function DemoModeBanner() {
  const [blocked, setBlocked] = useState("");
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    const onBlocked = (event) => {
      setBlocked((event.detail && event.detail.message) || "That operation is unavailable in the online demo.");
      window.setTimeout(() => setBlocked(""), 7000);
    };
    window.addEventListener("callosum:demo-blocked", onBlocked);
    return () => window.removeEventListener("callosum:demo-blocked", onBlocked);
  }, []);
  // Dismissing the persistent orientation card must not suppress later action-specific lock explanations.
  if (!isDemoMode() || (dismissed && !blocked)) return null;
  return (
    <div className={"demo-mode-banner" + (blocked ? " blocked" : "")} role={blocked ? "alert" : "status"}>
      <b>Saved online demo</b>
      <span>{blocked || "A curated, immutable Callosum snapshot. Read, search, and inspect evidence; generation and changes are unavailable."}</span>
      <a href="demo-about.html" target="_blank" rel="noopener">Corpus, licenses &amp; limits</a>
      <button className="demo-banner-close" aria-label="Dismiss demo notice" title="Dismiss"
        onClick={() => setDismissed(true)}>×</button>
    </div>
  );
}

// PDF.js is lazy. The live app retains its established UMD/CDN path; the demo uses a patched, bundled ES module.
const PDFJS_VERSION = "3.11.174";
let pdfLibPromise = null;
function loadPdfJs() {
  if (pdfLibPromise) return pdfLibPromise;
  if (isDemoMode()) {
    pdfLibPromise = import(new URL("assets/pdf.min.mjs", document.baseURI).toString()).then(lib => {
      lib.GlobalWorkerOptions.workerSrc = new URL("assets/pdf.worker.min.mjs", document.baseURI).toString();
      return lib;
    });
    return pdfLibPromise;
  }
  pdfLibPromise = new Promise((resolve, reject) => {
    if (window.pdfjsLib) { resolve(window.pdfjsLib); return; }
    const script = document.createElement("script");
    script.src = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/pdf.min.js`;
    script.onload = () => {
      if (!window.pdfjsLib) { reject(new Error("PDF.js failed to initialize")); return; }
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/pdf.worker.min.js`;
      resolve(window.pdfjsLib);
    };
    script.onerror = () => reject(new Error("Could not load PDF.js from the CDN"));
    document.head.appendChild(script);
  });
  return pdfLibPromise;
}
