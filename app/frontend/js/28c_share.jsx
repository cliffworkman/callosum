// Share-selection modal (SP4b, backlog #15). End-to-end encrypts an ad-hoc picked set of Library papers
// (metadata + tags + annotations, NO PDFs -- the same portable payload the library-bundle export already
// uses) to one collaborator's own public key. Reuses SP4a's own identity-lookup endpoint for the recipient
// picker, with the SAME fingerprint-confirmation copy ("35c_sync.jsx"'s SharingIdentityPanel) -- never a raw
// unchecked id. Sender-only: there is no "list what I've sent" surface yet.

function ShareModal({ ids, onClose }) {
  const [recipientId, setRecipientId] = useState("");
  const [lookingUp, setLookingUp] = useState(false);
  const [recipient, setRecipient] = useState(null);   // {public_key, display_name, fingerprint}
  const [lookupErr, setLookupErr] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [sharing, setSharing] = useState(false);
  const [result, setResult] = useState(null);          // {share_id, recipient_fingerprint}
  const [shareErr, setShareErr] = useState("");

  const count = ids ? ids.length : 0;

  const lookup = async () => {
    if (!recipientId.trim()) return;
    setLookingUp(true); setLookupErr(""); setRecipient(null); setResult(null);
    const r = await api(`/sync/identity/lookup?sub=${encodeURIComponent(recipientId.trim())}`);
    setLookingUp(false);
    if (r.ok) setRecipient(r.data);
    else setLookupErr("Couldn't look up that id: " + r.error);
  };

  const share = async () => {
    if (!recipient || !passphrase) return;
    setSharing(true); setShareErr("");
    const r = await apiPost("/sync/share", { recipient_sub: recipientId.trim(), paper_ids: ids, passphrase });
    setSharing(false); setPassphrase("");
    if (r.ok) setResult(r.data);
    else setShareErr("Couldn't share: " + r.error);
  };

  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Share {count} paper{count === 1 ? "" : "s"}</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Sends the selected papers' metadata + your tags + annotations, end-to-end encrypted to one
          collaborator — <b>no PDFs</b>, and only they can decrypt it. Requires your own sharing identity
          (Settings → Cross-device sync) and theirs.
        </div>

        {!result &&
          <>
            <div className="settings-field">
              <label className="settings-field-label">Recipient
                <span className="settings-sub">
                  Paste the sharing ID they gave you, then confirm the fingerprint below matches what they
                  told you — before sharing anything.
                </span>
              </label>
              <div className="settings-keyrow">
                <input className="settings-input" placeholder="Their sharing ID"
                  value={recipientId} onChange={e => setRecipientId(e.target.value)} />
                <button className="btn btn-ghost" disabled={lookingUp || !recipientId.trim()} onClick={lookup}>
                  {lookingUp ? "Looking up…" : "Look up"}
                </button>
              </div>
              {recipient &&
                <div className="settings-note">
                  {recipient.display_name ? recipient.display_name + " — " : ""}
                  fingerprint: {recipient.fingerprint}
                </div>}
              {lookupErr && <div className="settings-note settings-note-err">{lookupErr}</div>}
            </div>

            {recipient &&
              <div className="settings-field">
                <label className="settings-field-label">Your sync passphrase</label>
                <div className="settings-keyrow">
                  <input className="settings-input" type="password" autoComplete="off" placeholder="Passphrase"
                    value={passphrase} onChange={e => setPassphrase(e.target.value)} />
                  <button className="btn btn-primary" disabled={sharing || !passphrase} onClick={share}>
                    {sharing ? "Sharing…" : `Share ${count} paper${count === 1 ? "" : "s"}`}
                  </button>
                </div>
                {sharing && <ProgressBar label="Encrypting and sending…" />}
                {shareErr && <div className="settings-note settings-note-err">{shareErr}</div>}
              </div>}
          </>}

        {result &&
          <div className="settings-note">
            Sent — encrypted to fingerprint {result.recipient_fingerprint}. They'll need their own callosum,
            signed in, to receive it.
          </div>}

        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
