// Privacy-safe, one-click diagnostics for early adopters reporting failures in Slack.
// Callers supply already-sanitized fields; this formatter never reads logs, paths,
// documents, credentials, environment variables, or browser storage.
function callosumDiagnosticText(diagnostic) {
  if (!diagnostic) return "";
  const lines = [
    "Callosum diagnostic",
    `Error: ${diagnostic.code || "UNKNOWN"}`,
    `Feature: ${diagnostic.feature || "Unknown"}`,
    `Message: ${diagnostic.message || "No detail available."}`,
    `Suggested action: ${diagnostic.suggested_action || "Retry and report this diagnostic if the problem continues."}`,
    `Callosum: ${diagnostic.callosum_version || "unknown"}`,
    `Platform: ${diagnostic.platform || navigator.platform || "unknown"}`,
  ];
  Object.entries(diagnostic.details || {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      lines.push(`${key.replaceAll("_", " ")}: ${String(value)}`);
    }
  });
  lines.push(`Timestamp: ${diagnostic.timestamp || new Date().toISOString()}`);
  return lines.join("\n");
}

function callosumClientDiagnostic(code, feature, message, suggestedAction, details = {}) {
  return {
    code,
    feature,
    message,
    suggested_action: suggestedAction,
    platform: navigator.platform || "unknown",
    timestamp: new Date().toISOString(),
    details,
  };
}

function CopyDiagnosticButton({ diagnostic }) {
  const [copied, setCopied] = useState(false);
  if (!diagnostic) return null;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(callosumDiagnosticText(diagnostic));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch (_error) {
      setCopied(false);
    }
  };
  return <button type="button" className="btn btn-ghost" onClick={copy}>{copied ? "Diagnostics copied ✓" : "Copy diagnostics"}</button>;
}
