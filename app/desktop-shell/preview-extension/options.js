"use strict";
document.getElementById("verify").addEventListener("click", () => {
  const button = document.getElementById("verify");
  const status = document.getElementById("status");
  button.disabled = true;
  status.textContent = "Checking the packaged Callosum connection…";
  chrome.runtime.sendNativeMessage("org.callosum.connector", {
    id: crypto.randomUUID(), protocol_version: 1, operation: "verify_preview",
    extension_version: chrome.runtime.getManifest().version,
  }, (reply) => {
    button.disabled = false;
    const error = chrome.runtime.lastError;
    const messages = {
      available: "Connection verified. Return to Callosum Settings to see the result.",
      verification_not_requested: "In Callosum Settings, click Verify connection first, then try again within 60 seconds.",
      preview_disabled: "Enable early access in Callosum Settings first.",
      callosum_closed: "Open the packaged Callosum app, then try again.",
      callosum_starting: "Callosum is starting. Wait until its Library opens, then try again.",
      pairing_unavailable: "The local pairing could not be verified. Restart Callosum and try again.",
      version_incompatible: "Prepare the current extension in Callosum, then Reload it on the browser's Extensions page.",
    };
    status.textContent = error ? "Native host unavailable or this extension identity is not authorized. Reopen the installed Callosum app and use its prepared preview folder."
      : (messages[reply?.runtime_state] || "Connection not verified. Reopen Callosum and try again.");
  });
});
