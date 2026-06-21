// Settings modal (inc 46) — the app-wide preferences surface. Appearance → Dark mode (theme + onTheme); Axes →
// hide-uncertain-by-default (hideUncertainDefault + onHideUncertainDefault). Controlled by App; toggles persist
// to localStorage. Reuses the .axis-modal overlay pattern.
function SettingsModal({ theme, onTheme, hideUncertainDefault, onHideUncertainDefault, onClose }) {
  const dark = theme === "dark";
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal settings-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Settings</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>

        <p className="eyebrow">Appearance</p>
        <div className="settings-row">
          <span className="settings-label">Dark mode</span>
          <button
            type="button"
            className={"settings-switch" + (dark ? " on" : "")}
            role="switch" aria-checked={dark} aria-label="Dark mode"
            onClick={() => onTheme(dark ? "light" : "dark")}
          ><span className="settings-knob" /></button>
        </div>

        <p className="eyebrow">Axes</p>
        <div className="settings-row">
          <span className="settings-label">Hide uncertain papers by default
            <span className="settings-sub">New axis cards start in the assigned/manual-only view (the 👁 toggle).</span>
          </span>
          <button
            type="button"
            className={"settings-switch" + (hideUncertainDefault ? " on" : "")}
            role="switch" aria-checked={!!hideUncertainDefault} aria-label="Hide uncertain axis papers by default"
            onClick={() => onHideUncertainDefault(!hideUncertainDefault)}
          ><span className="settings-knob" /></button>
        </div>

        <div className="axis-modal-note">More settings will live here — this is just the start.</div>
      </div>
    </div>
  );
}
