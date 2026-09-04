// Actionable PDF recovery states (inc 576). The API deliberately sends no path: diagnostics identify the attachment
// state without leaking a username, library location, document title, or other private filesystem information.
const PDF_UNAVAILABLE_COPY = {
  PDF_LIBRARY_FOLDER_MISSING: {
    title: "Callosum's library folder is unavailable",
    message: "The folder that holds managed PDFs is not currently visible. If it is synced, reconnect or restart the sync service, then retry.",
    action: "Reconnect the library folder or make it available on this device, then retry.",
  },
  PDF_ATTACHMENT_UNREADABLE: {
    title: "This PDF is temporarily unreadable",
    message: "The file is present, but its drive or sync provider did not make the contents readable.",
    action: "Reconnect the drive or make the PDF available offline, then retry.",
  },
  PDF_ATTACHMENT_MARKED_MISSING: {
    title: "Callosum can't find this PDF",
    message: "The attachment was previously marked missing. You can reconnect an exact copy without losing its chunks, notes, or annotations.",
    action: "Choose the folder containing the PDF and scan it again.",
  },
  PDF_ATTACHMENT_FILE_MISSING: {
    title: "Callosum can't find this PDF",
    message: "The recorded attachment has moved or its folder is unavailable. An exact copy can be reconnected safely.",
    action: "Choose the folder containing the PDF and scan it again.",
  },
  PDF_ATTACHMENT_PATH_MISSING: {
    title: "This PDF needs to be reconnected",
    message: "The library record has no usable local file location.",
    action: "Choose the folder containing the PDF and scan it again.",
  },
  PDF_REMOTE_ONLY: {
    title: "No local PDF is attached",
    message: "This paper currently has a web link or metadata, but no PDF stored on this device.",
    action: "Add a local PDF if you want to read and annotate it in Callosum.",
  },
  PDF_ATTACHMENT_NOT_PDF: {
    title: "This attachment is not a PDF",
    message: "The selected attachment cannot be opened in the PDF reader.",
    action: "Choose a PDF attachment for this paper.",
  },
  PDF_ATTACHMENT_NOT_FOUND: {
    title: "No local PDF is attached",
    message: "This paper may be a URL-only or metadata-only library entry.",
    action: "Add a local PDF if you want to read and annotate it in Callosum.",
  },
};

function pdfUnavailableIssue(code, apiDetail, metadata = {}) {
  const safeCode = code || "PDF_LOCAL_FILE_UNAVAILABLE";
  const copy = PDF_UNAVAILABLE_COPY[safeCode] || {
    title: "PDF not available locally",
    message: apiDetail || "Callosum could not open this paper's local PDF.",
    action: "Retry, then reconnect the PDF if the problem continues.",
  };
  const diagnostic = callosumClientDiagnostic(safeCode, "PDF reader", apiDetail || copy.message, copy.action, {
    http_status: metadata.httpStatus,
    paper_id: metadata.paperId,
    attachment_id: metadata.attachmentId,
    storage_mode: metadata.storageMode,
    recorded_availability: metadata.availability,
  });
  diagnostic.callosum_version = metadata.appVersion || undefined;
  return { ...copy, diagnostic };
}

async function pdfUnavailableFromResponse(response, paperId) {
  let detail = "PDF not available locally.";
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") detail = body.detail;
  } catch (_error) { /* stable headers still carry the machine-readable failure */ }
  return pdfUnavailableIssue(response.headers.get("x-callosum-error-code"), detail, {
    httpStatus: response.status,
    paperId,
    attachmentId: response.headers.get("x-callosum-attachment-id"),
    storageMode: response.headers.get("x-callosum-storage-mode"),
    availability: response.headers.get("x-callosum-attachment-availability"),
    appVersion: response.headers.get("x-callosum-app-version"),
  });
}

function PdfUnavailableState({ issue, onRetry, onReconnect }) {
  const value = issue || pdfUnavailableIssue("PDF_LOCAL_FILE_UNAVAILABLE");
  return (
    <div className="state pdf-unavailable-state">
      <div className="big">{value.title}</div>
      <div>{value.message}</div>
      <div className="pdf-unavailable-actions">
        <button type="button" className="btn btn-primary" onClick={onRetry}>Retry</button>
        {onReconnect && <button type="button" className="btn btn-ghost" onClick={onReconnect}>Find or Reconnect PDF</button>}
        <CopyDiagnosticButton diagnostic={value.diagnostic} />
      </div>
      <div className="axis-hint">Exact matching uses the PDF's checksum; existing chunks, notes, and annotations are preserved.</div>
    </div>
  );
}
