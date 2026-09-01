// inc 416/553: first-run onboarding plus a one-time Local AI refresh for existing desktop installs. Both are gated
// by GET /health's completed/version state; the refresh reuses the real AI settings step rather than duplicating it.
// the same unconditional launch fetch read_only already rides — see 40_app.jsx), orchestrating existing,
// already-working settings screens rather than reinventing them: My Publications identity, AI provider choice,
// the watched library folder, citation/bundle import, and an initial axis. "Skip setup" is always visible and
// reachable — the wizard's job is to surface these once, not to gate the app behind completing them; everything
// it offers stays permanently reachable via Settings regardless. No multi-step convention existed in this
// codebase before this component — kept deliberately simple (one internal step index), not a generic reusable
// Wizard, since nothing else needs one yet.

const ONBOARDING_STEPS = ["identity", "ai", "library", "import", "axis", "done"];
const ONBOARDING_REFRESH_STEPS = ["ai", "done"];

const ONBOARDING_STEP_LABELS = {
  identity: "Your publications",
  ai: "AI features",
  library: "Where your PDFs live",
  import: "Import",
  axis: "Your first axis",
  done: "All set",
};

function OnboardingImportChoice({ onPick, onSkip }) {
  return (
    <div className="onboarding-choice">
      <div className="axis-modal-note">
        Bring in papers you already have. <b>Zotero:</b> read the library directly for PDFs, notes, tags, and
        collections. <b>Mendeley:</b> first use Zotero's <b>Mendeley Reference Manager (online import)</b>, then
        read that Zotero library here. <b>EndNote:</b> export with <b>RefMan (RIS) Export</b>, then import the
        citations file. A Callosum bundle restores portable library data without PDFs. Or skip this and add
        papers later.
      </div>
      <div className="onboarding-choice-actions">
        <button className="axis-btn" onClick={() => onPick("zotero")}>Read Zotero / migrated Mendeley library…</button>
        <button className="btn btn-ghost" onClick={() => onPick("file")}>Import EndNote RIS / citations file…</button>
        <button className="btn btn-ghost" onClick={() => onPick("bundle")}>Import a callosum bundle…</button>
        <button className="axis-link" onClick={onSkip}>Skip this step →</button>
      </div>
    </div>
  );
}

function OnboardingAxisChoice({ onPick, onSkip }) {
  return (
    <div className="onboarding-choice">
      <div className="axis-modal-note">
        An axis is a lens for organizing your library along a theme you define — Callosum can suggest some from
        your library's own content, or you can name your first one by hand. Either way, you can add more anytime.
      </div>
      <div className="onboarding-choice-actions">
        <button className="axis-btn" onClick={() => onPick("suggest")}>Suggest axes from my library…</button>
        <button className="btn btn-ghost" onClick={() => onPick("manual")}>Create one manually…</button>
        <button className="axis-link" onClick={onSkip}>Skip this step →</button>
      </div>
    </div>
  );
}

function onboardingLaunchState(health, isDesktop) {
  const completed = !!(health && health.onboarding_completed);
  const storedVersion = Number.isInteger(health && health.onboarding_version) ? health.onboarding_version : 0;
  const currentVersion = Number.isInteger(health && health.onboarding_current_version) ? health.onboarding_current_version : 0;
  const refresh = !!(isDesktop && !(health && health.read_only) && completed && storedVersion < currentVersion);
  return { done: completed && !refresh, refresh, version: currentVersion };
}

function OnboardingWizard({ onDone, refreshMode = false, currentVersion = 0, onMyPubsRefreshed, onScanned, onImported, onImportedZotero, onImportedBundle, onAxisSaved }) {
  const steps = refreshMode ? ONBOARDING_REFRESH_STEPS : ONBOARDING_STEPS;
  const [step, setStep] = useState(0);
  const [importMode, setImportMode] = useState(null);  // null | "file" | "bundle" | "zotero"
  const [axisMode, setAxisMode] = useState(null);       // null | "suggest" | "manual"
  const [busy, setBusy] = useState(false);
  const stepId = steps[step];
  const isLast = step === steps.length - 1;

  const finish = async () => {
    setBusy(true);
    await apiPut("/settings", { onboarding_completed: true, onboarding_version: currentVersion });
    setBusy(false);
    if (onDone) onDone();
  };
  const goNext = () => { if (isLast) finish(); else setStep(s => s + 1); };
  const goBack = () => setStep(s => Math.max(0, s - 1));

  let body = null;
  if (stepId === "identity") {
    body = (
      <>
        <div className="axis-modal-note">Optional — helps Callosum find and organize your own papers.</div>
        <MyPubsSettings onRefreshed={onMyPubsRefreshed} />
      </>
    );
  } else if (stepId === "ai") {
    body = (
      <>
        <div className="axis-modal-note">{refreshMode
          ? <>Local AI is now built in. Set it up once to run compatible AI features on this device — no API key,
              provider account, endpoint, Ollama, or terminal required.</>
          : <>Choose <b>Local AI</b> to run compatible AI features on this device, or configure a cloud provider.
              Callosum never switches providers silently.</>}</div>
        <AiSettings />
      </>
    );
  } else if (stepId === "library") {
    body = <ScanModalBody onClose={goNext} onScanned={onScanned} />;
  } else if (stepId === "import") {
    body = importMode == null
      ? <OnboardingImportChoice onPick={setImportMode} onSkip={goNext} />
      : importMode === "bundle"
        ? <BundleImportModalBody onClose={goNext} onImported={onImportedBundle} />
        : importMode === "zotero"
          ? <ZoteroImportModalBody onClose={goNext} onImported={onImportedZotero} />
          : <ImportModalBody onClose={goNext} onImported={onImported} />;
  } else if (stepId === "axis") {
    body = axisMode == null
      ? <OnboardingAxisChoice onPick={setAxisMode} onSkip={goNext} />
      : axisMode === "suggest"
        ? <SuggestAxesModalBody onClose={goNext} />
        : <AxisEditModalBody mode="create" axisId={null} initialTitle="" initialDescription="" initialTerms={[]}
            onClose={goNext} onSaved={() => { if (onAxisSaved) onAxisSaved(); goNext(); }} />;
  } else if (stepId === "done") {
    body = (
      <div className="onboarding-done">
        <div className="onboarding-done-icon" aria-hidden="true">🎉</div>
        <p>{refreshMode
          ? <>Your AI provider and Local AI setup remain available in <b>Settings</b> whenever you need them.</>
          : <>You're all set. Everything here is always reachable again from <b>Settings</b> — come back anytime to
              adjust your profile, AI provider, watched folders, or axes.</>}</p>
      </div>
    );
  }

  return (
    <div className="axis-modal-overlay" role="dialog" aria-modal="true" aria-label="Get started with Callosum">
      {/* Deliberately NO onClick={onClose} on this outer div — mirrors AccessLockOverlay's precedent: a
          full-screen intentional overlay isn't backdrop-dismissable. "Skip setup" is the real exit. */}
      <div className="axis-modal onboarding-card" onClick={e => e.stopPropagation()}>
        <div className="onboarding-dots" aria-hidden="true">
          {steps.map((id, i) => (
            <span key={id} className={"onboarding-dot" + (i === step ? " active" : i < step ? " done" : "")} />
          ))}
        </div>
        <div className="axis-modal-head">
          <span>{refreshMode ? "What's new in Callosum" : "Welcome to Callosum"} — {ONBOARDING_STEP_LABELS[stepId]}</span>
          {stepId !== "done" &&
            <button className="axis-link" disabled={busy} onClick={finish}>{refreshMode ? "Not now" : "Skip Setup"}</button>}
        </div>
        <div className="onboarding-body">{body}</div>
        <div className="onboarding-nav axis-form-actions">
          <button className="axis-link" disabled={step === 0 || busy} onClick={goBack}>← Back</button>
          <button className="axis-btn" disabled={busy} onClick={goNext}>
            {busy ? "Finishing…" : isLast ? "Finish" : "Next →"}
          </button>
        </div>
      </div>
    </div>
  );
}
