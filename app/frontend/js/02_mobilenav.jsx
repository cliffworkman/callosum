// B5 (inc 237): the mobile bottom-nav bar. On a phone-width viewport the 3-pane layout collapses to one region at
// a time; this switches between them. Presentational leaf (props only) — hoists in the shared IIFE, so 40_app.jsx
// renders <MobileNav/> regardless of chunk order.

const MOBILE_TABS = [
  { id: "library", label: "Library", icon: "📚" },
  { id: "theory", label: "Panels", icon: "🧭" },
  { id: "methods", label: "Details", icon: "📄" },
];

function MobileNav({ active, onSelect }) {
  return (
    <nav className="mobile-nav" aria-label="Sections">
      {MOBILE_TABS.map(t => (
        <button
          key={t.id}
          className={"mobile-nav-btn" + (active === t.id ? " active" : "")}
          aria-current={active === t.id ? "page" : undefined}
          onClick={() => onSelect(t.id)}
        >
          <span className="mobile-nav-icon" aria-hidden="true">{t.icon}</span>
          <span className="mobile-nav-label">{t.label}</span>
        </button>
      ))}
    </nav>
  );
}
