// AI features — the unified LLM provider roster (inc 256). One editable list: the four presets
// (Gemini / OpenAI / Anthropic / Local) are pre-seeded, and the user can add arbitrary custom providers
// {name, base_url, wire_format, models[]} + a key. Rides GET/POST/PUT/DELETE /settings/providers for the
// roster + custom CRUD, and PUT /settings for the ACTIVE selection / per-provider key / model / egress.
// Keys are write-only (the roster reports key_set only, never a value); egress is default-OFF; a loopback
// provider needs no consent. Hoists across the shared IIFE — SettingsModal (js/35_settings.jsx) renders it.
const AI_KEY_URLS = {
  gemini: "https://aistudio.google.com/apikey",
  openai: "https://platform.openai.com/api-keys",
  anthropic: "https://console.anthropic.com/settings/keys",
};
// The wire-format labels (the API-format dropdown). `gemini` is the builtin SDK format — shown for the Gemini
// preset but never assignable to a custom provider (the roster's wire_formats list excludes it).
const WIRE_LABELS = {
  gemini: "Gemini SDK",
  messages: "Anthropic messages (/v1/messages)",
  chat_completions: "Chat completions (/chat/completions)",
  responses: "Responses (/responses)",
};
// Client mirror of the server's is_loopback_url (app/backend/llm/providers.py) — used ONLY to decide what egress
// posture to *show* on a card (the server still enforces the real gate). A loopback provider sends nothing off-machine.
function isLoopbackUrl(u) {
  try {
    const h = new URL(u).hostname.replace(/^\[|\]$/g, "");
    return h === "127.0.0.1" || h === "localhost" || h === "::1" || h === "0.0.0.0";
  } catch (e) { return false; }
}

// Edits a list of model-name strings (used by the Add form + the custom-provider details editor).
function ProviderModelsEditor({ models, setModels, disabled }) {
  const update = (i, v) => setModels(models.map((m, j) => (j === i ? v : m)));
  return (
    <div className="provider-models">
      {models.map((m, i) => (
        <div className="settings-keyrow" key={i}>
          <input className="settings-input" placeholder="model name, e.g. gpt-4o-mini" value={m}
            disabled={disabled} onChange={e => update(i, e.target.value)} />
          <button className="btn btn-ghost" disabled={disabled}
            onClick={() => setModels(models.filter((_, j) => j !== i))} aria-label="Remove model">×</button>
        </div>
      ))}
      <button className="btn-link" disabled={disabled} onClick={() => setModels([...models, ""])}>+ Add model</button>
    </div>
  );
}

// The {name, base_url, wire_format, models[]} editor shared by the Add form + a custom provider's Edit mode.
function ProviderFields({ draft, setDraft, disabled, wireFormats }) {
  const set = (k, v) => setDraft({ ...draft, [k]: v });
  return (
    <>
      <div className="settings-field">
        <label className="settings-field-label">Name</label>
        <input className="settings-input" placeholder="e.g. DeepSeek" value={draft.name}
          disabled={disabled} onChange={e => set("name", e.target.value)} />
      </div>
      <div className="settings-field">
        <label className="settings-field-label">Base URL
          <span className="settings-sub">Just the host — Callosum adds the API path (<code>/v1/…</code>) itself. A trailing <code>/v1</code> is fine; it's trimmed.</span>
        </label>
        <input className="settings-input" placeholder="https://api.deepseek.com" value={draft.base_url}
          disabled={disabled} onChange={e => set("base_url", e.target.value)} />
      </div>
      <div className="settings-field">
        <label className="settings-field-label">API format
          <span className="settings-sub">How the provider expects the request. Most (DeepSeek, Together, Groq, OpenRouter, vLLM) use <b>Chat completions</b>; pick <b>Anthropic messages</b> only for a Claude-compatible endpoint.</span>
        </label>
        <select className="settings-input" value={draft.wire_format} disabled={disabled}
          onChange={e => set("wire_format", e.target.value)}>
          {wireFormats.map(w => <option key={w} value={w}>{WIRE_LABELS[w] || w}</option>)}
        </select>
      </div>
      <div className="settings-field">
        <label className="settings-field-label">Models</label>
        <ProviderModelsEditor models={draft.models} setModels={m => set("models", m)} disabled={disabled} />
      </div>
    </>
  );
}

// The draft card for adding a custom provider (the mockup's Add-provider form).
function AddProviderForm({ busy, wireFormats, onCancel, onCreate }) {
  const [draft, setDraft] = useState({ name: "", base_url: "", wire_format: "chat_completions", models: [""], api_key: "" });
  const canSubmit = draft.name.trim() && draft.base_url.trim() && !busy;
  const submit = () => onCreate({
    name: draft.name.trim(), base_url: draft.base_url.trim(), wire_format: draft.wire_format,
    models: draft.models.map(s => s.trim()).filter(Boolean), api_key: draft.api_key,
  });
  return (
    <div className="provider-card provider-card-draft">
      <div className="provider-card-head"><span className="provider-name">New provider</span></div>
      <div className="provider-body">
        <ProviderFields draft={draft} setDraft={setDraft} disabled={busy} wireFormats={wireFormats} />
        <div className="settings-field">
          <label className="settings-field-label">API key (optional)</label>
          <input className="settings-input" type="password" autoComplete="off" placeholder="Paste the provider's key"
            value={draft.api_key} onChange={e => setDraft({ ...draft, api_key: e.target.value })} />
        </div>
        <div className="settings-actions">
          <button className="btn btn-ghost" disabled={busy} onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={submit}>{busy ? "Adding…" : "Add provider"}</button>
        </div>
      </div>
    </div>
  );
}

// The active provider's model chooser — a <select> of its listed models, or a free-text box when it lists none
// (e.g. a local endpoint whose model you name yourself). Setting a model also (re)activates this provider.
function ProviderModelPicker({ p, activeModel, busy, onActivate }) {
  const models = p.models || [];
  const [text, setText] = useState(activeModel || "");
  if (models.length > 0) {
    const value = models.includes(activeModel) ? activeModel : models[0];
    return (
      <div className="settings-field provider-model-field">
        <label className="settings-field-label">Model</label>
        <select className="settings-input" value={value} disabled={busy} onChange={e => onActivate(p.id, e.target.value)}>
          {models.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>
    );
  }
  return (
    <div className="settings-field provider-model-field">
      <label className="settings-field-label">Model
        <span className="settings-sub">The model name your endpoint serves (e.g. <code>llama3.1</code>).</span>
      </label>
      <div className="settings-keyrow">
        <input className="settings-input" placeholder="model name" value={text} onChange={e => setText(e.target.value)} />
        <button className="btn btn-ghost" disabled={busy || !text.trim()} onClick={() => onActivate(p.id, text.trim())}>Set</button>
      </div>
    </div>
  );
}

const LOCAL_AI_SETUP_STATES = new Set([
  "checking", "downloading_runtime", "preparing_runtime", "downloading_model", "verifying", "preparing",
]);
const LOCAL_AI_SETUP_STATUS_ID = "local-ai-setup";
let _localAiSetupStatusTimer = null;
const _localAiSetupListeners = new Set();

function localAiSetupActive(status) {
  return !!(status && LOCAL_AI_SETUP_STATES.has(status.state));
}

function localAiSetupPhase(status) {
  const phases = {
    checking: ["Checking existing Local AI files…", "Callosum is checking whether verified files can be reused."],
    downloading_runtime: ["Downloading the Local AI engine…", "Keep Callosum open while the small runtime package downloads."],
    preparing_runtime: ["Preparing the Local AI engine…", "Callosum is verifying and unpacking the local runtime."],
    downloading_model: ["Downloading the Local AI model…", "This is the main 1.04 GiB download. You may continue in the background and follow it under Status."],
    verifying: ["Verifying downloaded files…", "Callosum is checking the pinned model identity before it can be used."],
    preparing: ["Starting Local AI…", "The model is installed; Callosum is starting it and waiting for authenticated readiness."],
  };
  return phases[status && status.state] || ["Setting up Local AI…", "Keep Callosum open while setup finishes."];
}

function localAiStatusLabel(status) {
  const labels = {
    ready: "Local AI: Ready",
    installed: "Installed — ready to start",
    not_installed: "Ready to set up",
    // "unsupported" means the CPU architecture genuinely has no runtime (an Intel Mac before inc 567).
    // A browser dev session is a different thing entirely and gets its own state, or it would read as a
    // hardware verdict that is simply false.
    unsupported: "Unsupported architecture",
    desktop_required: "Set up in the desktop app",
    error: "Setup needs attention",
  };
  return labels[status && status.state] || (status && status.state ? status.state.replaceAll("_", " ") : "Checking…");
}

function localAiFrontendDiagnostic(code, message, stage) {
  return callosumClientDiagnostic(code, "Local AI", message,
    "Retry Set up Local AI; if it fails again, copy these diagnostics into your report.",
    { stage, runtime: "managed llama.cpp b10516" });
}

function localAiSetupProgress(status) {
  if (!status || !(status.total_bytes > 0) || status.downloaded_bytes == null) return null;
  const unit = 1024 * 1024;
  return {
    current: Math.round(status.downloaded_bytes / unit * 10) / 10,
    total: Math.round(status.total_bytes / unit * 10) / 10,
    label: "Downloaded MiB",
    // Zero means "not measurable yet" to ProgressBar and prevents Status from deriving an ETA from the whole
    // multi-phase setup. Rust supplies the phase-local estimate once at least 0.5 s of download is observed.
    eta_seconds: status.eta_seconds ?? 0,
  };
}

function publishLocalAiSetupStatus(status) {
  const active = localAiSetupActive(status);
  if (active) {
    const phase = localAiSetupPhase(status);
    _startClientStatus({ id: LOCAL_AI_SETUP_STATUS_ID, label: "Setting up Local AI",
      nav: { modal: "local-ai" }, computeKind: "On-device setup", progress: localAiSetupProgress(status) });
    _updateClientStatus(LOCAL_AI_SETUP_STATUS_ID, { detail: phase[0], progress: localAiSetupProgress(status) });
    return;
  }
  if (status && status.state === "ready") _finishClientStatus(LOCAL_AI_SETUP_STATUS_ID, true);
  if (status && status.state === "error") _finishClientStatus(LOCAL_AI_SETUP_STATUS_ID, false, status.detail || "Local AI setup failed.");
}

function acceptLocalAiSetupStatus(status) {
  publishLocalAiSetupStatus(status);
  _localAiSetupListeners.forEach(listener => listener(status));
}

function trackLocalAiSetupInStatus() {
  if (!("__TAURI__" in window) || _localAiSetupStatusTimer) return;
  const poll = async () => {
    try {
      const status = await window.__TAURI__.core.invoke("local_ai_status");
      acceptLocalAiSetupStatus(status);
      if (!localAiSetupActive(status)) {
        clearInterval(_localAiSetupStatusTimer);
        _localAiSetupStatusTimer = null;
      }
    } catch (err) {
      _finishClientStatus(LOCAL_AI_SETUP_STATUS_ID, false, String(err));
      clearInterval(_localAiSetupStatusTimer);
      _localAiSetupStatusTimer = null;
    }
  };
  _localAiSetupStatusTimer = setInterval(poll, 1500);
  poll();
}

// One provider in the roster. Builtins expose only their key (+ Local its loopback endpoint); custom providers add
// an "Edit" mode over {name, base_url, wire_format, models}.
function ProviderRow({ p, active, activeModel, status, busy, testing, test, wireFormats, egressOn,
  localAi, onSetupLocalAi, onActivate, onSaveKey, onSaveUrl, onTest, onUpdate, onDelete }) {
  const [keyInput, setKeyInput] = useState("");
  const [urlInput, setUrlInput] = useState(p.base_url || "");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);

  const isLocal = p.id === "local";
  const isManagedLocal = p.id === "managed_local";
  const isLoopback = !isLocal && !isManagedLocal && isLoopbackUrl(p.base_url);  // a custom provider pointed at a loopback address
  const isCloud = !isLocal && !isManagedLocal && !isLoopback;  // sends library text off-machine on generate
  const endpointUrl = p.id === "gemini" ? "https://generativelanguage.googleapis.com" : p.base_url;
  const needsConsent = active && isCloud && !egressOn;  // fully configured but blocked by the egress toggle
  const keyUrl = AI_KEY_URLS[p.id];
  const keySet = p.key_set;
  const fromEnv = active && status && status.api_key_source === "env";  // env source is known only for the active builtin
  const localSetupActive = isManagedLocal && localAiSetupActive(localAi);
  const localSetupPhase = localSetupActive ? localAiSetupPhase(localAi) : null;
  const localSetupProgress = localSetupActive ? localAiSetupProgress(localAi) : null;
  const localSetupProgressRef = useRef(null);
  useEffect(() => {
    if (!localSetupActive) return;
    requestAnimationFrame(() => localSetupProgressRef.current?.scrollIntoView({ block: "nearest" }));
  }, [localSetupActive, localAi?.state]);

  const saveKey = async () => { if (await onSaveKey(p.id, keyInput)) setKeyInput(""); };
  const startEdit = () => {
    setDraft({ name: p.name, base_url: p.base_url || "", wire_format: p.wire_format, models: (p.models || []).slice() });
    setEditing(true);
  };
  const saveEdit = async () => {
    const patch = {
      name: draft.name.trim(), base_url: draft.base_url.trim(), wire_format: draft.wire_format,
      models: draft.models.map(s => s.trim()).filter(Boolean),
    };
    if (await onUpdate(p.id, patch, "Saved.")) setEditing(false);
  };

  return (
    <div className={"provider-card" + (active ? " is-active" : "")}>
      <div className="provider-card-head">
        <div className="provider-identity">
          <span className="provider-name">{p.name}</span>
          <span className="provider-badge">{WIRE_LABELS[p.wire_format] || p.wire_format}</span>
        </div>
        <span className="provider-actions">
          {active
            ? <span className="provider-active">Active</span>
            : !isManagedLocal && <button className="btn-link" disabled={busy} onClick={() => onActivate(p.id)}>Use</button>}
          {!p.builtin && <button className="btn-link danger" disabled={busy} onClick={() => onDelete(p.id)}>Delete</button>}
        </span>
      </div>

      <div className="provider-body">
          {needsConsent && !editing &&
            <div className="provider-egress-warn">⚠ AI features are off — Callosum won't contact <b>{p.name}</b> until you turn on <b>Allow AI features</b> below.</div>}
          {!editing && endpointUrl &&
            <div className="settings-sub provider-endpoint">
              Sends to <code>{endpointUrl}</code> — your library text goes there when you generate a summary.
              {isLoopbackUrl(endpointUrl) ? <> This is a loopback address — <b>nothing leaves your machine</b>.</> : null}
            </div>}
          {!editing && (isManagedLocal || p.id === "gemini") &&
            <div className="settings-sub">Overview — <b>Evaluated</b> · Other generative capabilities — <b>Testing</b></div>}
          {isManagedLocal ? (
            <div className="settings-field">
              <div className="settings-sub"><b>Runs on this device.</b> No API key, provider account, endpoint, Ollama, or terminal required.</div>
              <div className="settings-sub">
                Status: <b>{localAiStatusLabel(localAi)}</b>
              </div>
              {localAi && localAi.detail && <div className="provider-egress-warn">{localAi.detail}</div>}
              {localAi && localAi.diagnostic && <div className="settings-actions"><CopyDiagnosticButton diagnostic={localAi.diagnostic} /></div>}
              {localSetupActive && <div className="local-ai-setup-progress" role="status" aria-live="polite"
                ref={localSetupProgressRef}>
                <ProgressBar label={localSetupPhase[0]} progress={localSetupProgress} managedBy="local-ai-setup" />
                <div className="settings-sub">{localSetupPhase[1]}</div>
                <div className="settings-sub"><b>Do not close Callosum.</b> You may continue this setup in the background;
                  open <b>Status</b> and select <b>Setting up Local AI</b> to return here.</div>
              </div>}
              <div className="settings-sub">Formal comparative evaluation is ongoing. Review important claims against the underlying evidence.</div>
              <details className="settings-details">
                <summary>Technical details</summary>
                <div className="settings-sub">
                  Supported model: <b>{localAi && localAi.model_id ? localAi.model_id : "Qwen2.5-1.5B-Instruct Q4_K_M"}</b>
                  {localAi && localAi.model_bytes ? <> · {(localAi.model_bytes / (1024 ** 3)).toFixed(2)} GiB model download</> : null}
                  . The preview uses a pinned, checksum-verified llama.cpp runtime and an explicit CPU-safe execution mode.
                </div>
                <div className="settings-sub">If setup is interrupted or an installed file is corrupt, run Set up Local AI again; Callosum verifies and repairs the managed files before starting.</div>
              </details>
              <div className="settings-actions">
                <button className="btn btn-primary" disabled={busy || (localAi && !["ready", "installed", "not_installed", "error"].includes(localAi.state))}
                  onClick={onSetupLocalAi}>{localSetupActive ? localSetupPhase[0] :
                    localAi && localAi.state === "ready" ? (active ? "Ready" : "Use Local AI") :
                    localAi && localAi.installed ? "Prepare Local AI" : "Set up Local AI"}</button>
              </div>
            </div>
          ) : isLocal ? (
            <div className="settings-field">
              <label className="settings-field-label">Local endpoint (OpenAI-compatible)</label>
              <div className="settings-keyrow">
                <input className="settings-input" placeholder="http://127.0.0.1:11434" value={urlInput} onChange={e => setUrlInput(e.target.value)} />
                <button className="btn btn-ghost" disabled={busy || !urlInput.trim()} onClick={() => onSaveUrl(urlInput)}>{busy ? "Saving…" : "Save"}</button>
              </div>
            </div>
          ) : editing ? (
            <>
              <ProviderFields draft={draft} setDraft={setDraft} disabled={busy} wireFormats={wireFormats} />
              <div className="settings-actions">
                <button className="btn btn-ghost" disabled={busy} onClick={() => setEditing(false)}>Cancel</button>
                <button className="btn btn-primary" disabled={busy || !draft.name.trim() || !draft.base_url.trim()} onClick={saveEdit}>{busy ? "Saving…" : "Save Details"}</button>
              </div>
            </>
          ) : (
            <>
              <div className="settings-field">
                <label className="settings-field-label">API key
                  <span className="settings-sub">
                    {keySet
                      ? (fromEnv ? "Set via an environment variable."
                        : (status && status.key_storage === "keychain" ? "A key is saved in your OS keychain." : "A key is saved locally on this machine."))
                      : "Not set. Stored locally (your OS keychain if available), sent only to this provider."}
                    {keyUrl ? <>{" "}<a href={keyUrl} target="_blank" rel="noopener noreferrer">Get a key →</a></> : null}
                  </span>
                </label>
                <div className="settings-keyrow">
                  <input className="settings-input" type="password" autoComplete="off"
                    placeholder={keySet && !fromEnv ? "•••••••• (saved) — type to replace" : "Paste your key"}
                    value={keyInput} onChange={e => setKeyInput(e.target.value)} />
                  <button className="btn btn-ghost" disabled={busy || !keyInput.trim()} onClick={saveKey}>{busy ? "Saving…" : "Save"}</button>
                  {keySet && !fromEnv && <button className="btn btn-ghost" disabled={busy} onClick={() => onSaveKey(p.id, "")}>Clear</button>}
                </div>
              </div>
              {!p.builtin && <button className="btn-link" disabled={busy} onClick={startEdit}>Edit Name / URL / Models</button>}
            </>
          )}

          {active && !editing && !isManagedLocal &&
            <div className="provider-model-test-row">
              <ProviderModelPicker p={p} activeModel={activeModel} busy={busy} onActivate={onActivate} />
              {(isLocal ? !!(status && status.local_base_url) : keySet) &&
                <button className="btn btn-ghost" disabled={testing} onClick={onTest}>{testing ? "Testing…" : (isLocal ? "Test connection" : "Test key")}</button>}
            </div>}
          {active && !editing && test &&
            <div className={"settings-keytest-result " + (test.ok ? "ok" : "err")}>{test.detail}</div>}
      </div>
    </div>
  );
}

function AiSettings({ agentSettings, onLocalAiSetupState }) {
  const [roster, setRoster] = useState(null);  // GET /settings/providers
  const [status, setStatus] = useState(null);  // GET /settings (egress/help/key_storage/sources)
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [test, setTest] = useState(null);
  const [testing, setTesting] = useState(false);
  const [adding, setAdding] = useState(false);
  const [localAi, setLocalAi] = useState(null);

  // Without the Tauri bridge there is no local_ai_status command to call, but the BACKEND still knows whether
  // it can resolve a managed target -- that is exactly what /settings reports (inc 568). Ask it, instead of
  // asserting a hardware verdict the browser cannot possibly have checked (backlog #72).
  const refreshLocalAi = async (settings) => {
    if (!("__TAURI__" in window)) {
      const reachable = !!(settings && settings.provider === "managed_local" && settings.generation_provider_available);
      acceptLocalAiSetupStatus(reachable
        ? { state: "ready", installed: true, running: true,
            detail: "Reachable from this session (started outside the desktop app)." }
        : { state: "desktop_required", installed: false, running: false,
            detail: (settings && settings.generation_provider_detail)
              || "Managed Local AI setup is available in the installed desktop app.",
            diagnostic: localAiFrontendDiagnostic("LOCAL_AI_DESKTOP_REQUIRED",
              "Managed Local AI setup requires the installed desktop app.", "runtime_detection") });
      return;
    }
    try { acceptLocalAiSetupStatus(await window.__TAURI__.core.invoke("local_ai_status")); }
    catch (_err) { acceptLocalAiSetupStatus({ state: "error", detail: "Local AI status detection failed.", installed: false, running: false,
      diagnostic: localAiFrontendDiagnostic("LOCAL_AI_DETECTION_FAILED", "Callosum could not inspect Local AI status.", "runtime_detection") }); }
  };

  const reload = async () => {
    const [pr, st] = await Promise.all([api("/settings/providers"), api("/settings")]);
    if (pr.ok) setRoster(pr.data);
    if (st.ok) setStatus(st.data);
    return st.ok ? st.data : null;  // the browser branch of refreshLocalAi needs the backend's own verdict
  };
  useEffect(() => {
    const listener = current => setLocalAi(current);
    _localAiSetupListeners.add(listener);
    reload().then(refreshLocalAi);
    return () => _localAiSetupListeners.delete(listener);
  }, []);
  const localSetupActive = localAiSetupActive(localAi);
  useEffect(() => {
    if (onLocalAiSetupState) onLocalAiSetupState(localSetupActive);
    if (localSetupActive) trackLocalAiSetupInStatus();
  }, [localSetupActive]);

  const put = async (body, doneMsg) => {
    setBusy(true); setMsg(""); setTest(null);
    const r = await apiPut("/settings", body);
    setBusy(false);
    if (r.ok) { await reload(); if (doneMsg) setMsg(doneMsg); return true; }
    setMsg("Couldn't save: " + (r.error || "error")); return false;
  };

  // Activating a provider also resets the model override to that provider's default ("") unless a specific model
  // is chosen — so switching providers never carries the previous provider's model name across.
  const activate = async (id, model) => {
    const saved = await put({ provider: id, set_model: true, model: model || "" });
    if (saved && id !== "managed_local" && roster && roster.active_provider === "managed_local" && "__TAURI__" in window) {
      try { await window.__TAURI__.core.invoke("stop_local_ai"); await refreshLocalAi(); } catch (_err) { /* app exit still owns cleanup */ }
    }
    return saved;
  };
  const setupLocalAi = async () => {
    if (!("__TAURI__" in window)) return;
    if (localAi && localAi.state === "ready") {
      await activate("managed_local");
      return;
    }
    setBusy(true); setMsg("");
    acceptLocalAiSetupStatus({ ...(localAi || {}), state: "checking" });
    _startClientStatus({ id: LOCAL_AI_SETUP_STATUS_ID, label: "Setting up Local AI",
      nav: { modal: "local-ai" }, computeKind: "On-device setup", progress: null });
    trackLocalAiSetupInStatus();
    try {
      const result = await window.__TAURI__.core.invoke("setup_local_ai");
      acceptLocalAiSetupStatus(result);
      await apiPut("/settings", { provider: "managed_local", set_model: true, model: "" });
      await reload();
      setMsg("Local AI is ready and active.");
      _finishClientStatus(LOCAL_AI_SETUP_STATUS_ID, true);
    } catch (_err) {
      await refreshLocalAi();
      setMsg("Local AI setup did not finish. Retry setup or open technical details.");
      _finishClientStatus(LOCAL_AI_SETUP_STATUS_ID, false, "Local AI setup did not finish.");
    } finally { setBusy(false); }
  };
  const saveKey = (id, val) => put({ set_api_key: true, api_key: val, api_key_provider: id }, val.trim() ? "Key saved." : "Key cleared.");
  const saveUrl = (url) => put({ set_local_base_url: true, local_base_url: url }, "Endpoint saved.");
  const toggleEgress = () => status && put({ data_egress_enabled: !status.data_egress_enabled });
  const toggleHelp = () => status && put({ help_assistant_enabled: !status.help_assistant_enabled });

  const testActive = async () => {
    setTesting(true); setTest(null);
    const r = await apiPost("/settings/test-key", {});
    setTesting(false);
    setTest(r.ok ? r.data : { ok: false, detail: r.error || "Test failed." });
  };

  const createProvider = async (draft) => {
    setBusy(true); setMsg("");
    const r = await apiPost("/settings/providers", {
      name: draft.name, base_url: draft.base_url, wire_format: draft.wire_format, models: draft.models,
    });
    if (r.ok && draft.api_key && draft.api_key.trim()) {
      await apiPut("/settings", { set_api_key: true, api_key: draft.api_key, api_key_provider: r.data.id });
    }
    if (r.ok) {
      // The user added this provider deliberately — make it active so "add DeepSeek and use it" is one step, not two.
      await apiPut("/settings", { provider: r.data.id, set_model: true, model: (draft.models[0] || "") });
    }
    setBusy(false);
    if (r.ok) { setAdding(false); await reload(); setMsg(`${draft.name} added and set as active.`); return true; }
    setMsg("Couldn't add: " + (r.error || "error")); return false;
  };
  const updateProvider = async (id, patch, doneMsg) => {
    setBusy(true); setMsg("");
    const r = await apiPut(`/settings/providers/${id}`, patch);
    setBusy(false);
    if (r.ok) { await reload(); if (doneMsg) setMsg(doneMsg); return true; }
    setMsg("Couldn't save: " + (r.error || "error")); return false;
  };
  const deleteProvider = async (id) => {
    setBusy(true); setMsg("");
    const r = await apiDelete(`/settings/providers/${id}`);
    setBusy(false);
    if (r.ok) { await reload(); setMsg("Provider removed."); }
    else setMsg("Couldn't remove: " + (r.error || "error"));
  };

  const egressOn = !!(status && status.data_egress_enabled);
  const helpOn = !!(status && status.help_assistant_enabled);
  const providers = roster ? roster.providers : [];
  const activeId = roster ? roster.active_provider : "gemini";
  const activeModel = roster ? roster.active_model : "";
  const wireFormats = roster ? roster.wire_formats : ["messages", "chat_completions", "responses"];

  return (
    <>
      <div className="provider-list">
        {providers.map(p => (
          <ProviderRow key={p.id} p={p} active={p.id === activeId} activeModel={activeModel} status={status}
            busy={busy} testing={testing} test={p.id === activeId ? test : null} wireFormats={wireFormats}
            egressOn={egressOn} localAi={localAi} onSetupLocalAi={setupLocalAi}
            onActivate={activate} onSaveKey={saveKey} onSaveUrl={saveUrl} onTest={testActive}
            onUpdate={updateProvider} onDelete={deleteProvider} />
        ))}
      </div>
      {adding
        ? <AddProviderForm busy={busy} wireFormats={wireFormats} onCancel={() => setAdding(false)} onCreate={createProvider} />
        : <div className="provider-list-footer">
            <div className="settings-ai-note">Whichever provider you choose, every summary sentence is still <b>verified locally</b> against your PDFs — your model choice affects draft quality + coverage, never which citations are accepted.</div>
            <button className="btn provider-add-btn" disabled={busy} onClick={() => setAdding(true)}>+ Add provider</button>
          </div>}

      <div className="settings-ai-controls">
        <div className="settings-row settings-ai-control">
          <span className="eyebrow settings-ai-control-title">Allow AI features (sends text to the active provider)</span>
          <button type="button" className={"settings-switch" + (egressOn ? " on" : "")}
            role="switch" aria-checked={egressOn} aria-label="Allow AI features"
            onClick={toggleEgress}><span className="settings-knob" /></button>
          <span className="settings-sub">
            Off by default. When on, generating a summary sends the relevant library text to your active cloud provider; every sentence is still verified locally against your PDFs. A loopback local provider needs no consent — nothing leaves your machine.
            {status && status.egress_source === "env" ? " Currently set by the CALLOSUM_ALLOW_DATA_EGRESS environment variable." : ""}
          </span>
        </div>
        <div className="settings-row settings-ai-control">
          <span className="eyebrow settings-ai-control-title">AI Help Assistant</span>
          <button type="button" className={"settings-switch" + (helpOn ? " on" : "")}
            role="switch" aria-checked={helpOn} aria-label="AI Help Assistant"
            onClick={toggleHelp}><span className="settings-knob" /></button>
          <span className="settings-sub">
            Answers questions about using Callosum (the “Ask…” box in Help). Its <b>own</b> switch — it sends only your question + the public help docs, never your library, so it works with any provider and is independent of the egress toggle above.
            {status && status.help_source === "env" ? " Currently set by the CALLOSUM_HELP_ASSISTANT_ENABLED environment variable." : ""}
          </span>
        </div>
        {agentSettings}
      </div>
      {testing && <ProgressBar label="Testing the active AI provider…" managedBy="tracked-request" />}
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}
