// inc 416: the first-run onboarding wizard. Runs once per machine (gated on GET /health's onboarding_completed,
// the same unconditional launch fetch read_only already rides — see 40_app.jsx), orchestrating existing,
// already-working settings screens rather than reinventing them: My Publications identity, AI/BYOK opt-in,
// the watched library folder, citation/bundle import, and an initial axis. "Skip setup" is always visible and
// reachable — the wizard's job is to surface these once, not to gate the app behind completing them; everything
// it offers stays permanently reachable via Settings regardless. No multi-step convention existed in this
// codebase before this component — kept deliberately simple (one internal step index), not a generic reusable
// Wizard, since nothing else needs one yet.

const ONBOARDING_STEPS = ["identity", "ai", "library", "import", "axis", "done"];

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
        Bring in papers you already have citations for — a BibTeX/RIS/CSL-JSON file (e.g. exported from Zotero,
        Mendeley, or EndNote) or a callosum library bundle. Or skip this and add papers later.
      </div>
      <div className="onboarding-choice-actions">
        <button className="axis-btn" onClick={() => onPick("file")}>Import citations file…</button>
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

function OnboardingWizard({ onDone, onMyPubsRefreshed, onScanned, onImported, onImportedBundle, onAxisSaved }) {
  const [step, setStep] = useState(0);
  const [importMode, setImportMode] = useState(null);  // null | "file" | "bundle"
  const [axisMode, setAxisMode] = useState(null);       // null | "suggest" | "manual"
  const [busy, setBusy] = useState(false);
  const stepId = ONBOARDING_STEPS[step];
  const isLast = step === ONBOARDING_STEPS.length - 1;

  const finish = async () => {
    setBusy(true);
    await apiPut("/settings", { onboarding_completed: true });
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
        <div className="axis-modal-note">Optional and off by default — skip this if you'd rather stay fully local.</div>
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
        <p>You're all set. Everything here is always reachable again from <b>Settings</b> — come back anytime to
          adjust your profile, AI provider, watched folders, or axes.</p>
      </div>
    );
  }

  return (
    <div className="axis-modal-overlay" role="dialog" aria-modal="true" aria-label="Get started with Callosum">
      {/* Deliberately NO onClick={onClose} on this outer div — mirrors AccessLockOverlay's precedent: a
          full-screen intentional overlay isn't backdrop-dismissable. "Skip setup" is the real exit. */}
      <div className="axis-modal onboarding-card" onClick={e => e.stopPropagation()}>
        <div className="onboarding-dots" aria-hidden="true">
          {ONBOARDING_STEPS.map((id, i) => (
            <span key={id} className={"onboarding-dot" + (i === step ? " active" : i < step ? " done" : "")} />
          ))}
        </div>
        <div className="axis-modal-head">
          <span>Welcome to Callosum — {ONBOARDING_STEP_LABELS[stepId]}</span>
          {stepId !== "done" &&
            <button className="axis-link" disabled={busy} onClick={finish}>Skip setup</button>}
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
