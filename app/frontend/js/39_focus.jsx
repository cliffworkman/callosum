// useFocusMode — the axis "focus-mode" subsystem (inc-50 C), extracted from App (inc 167) to keep 40_app.jsx
// under the 600-line cap. Add/remove papers to an axis from the library list: changes are STAGED
// (focusPending: paperId → "add"|"remove", relative to focusMembers) and committed on Save.
//
// Interface: the caller passes `setActiveTab` (entering focus brings the library list into view) and
// `onEnterClearFilters` (entering focus replaces any view filter). It returns the focus state + the actions +
// `axisRefresh`/`setAxisRefresh` (bumped after Save so the AxesPanel reloads; also bumped by the caller after a merge).
function useFocusMode({ setActiveTab, onEnterClearFilters }) {
  const [focusAxis, setFocusAxis] = useState(null); // {id, label} | null
  const [focusMembers, setFocusMembers] = useState(() => new Set()); // paper ids already on the axis
  const [focusPending, setFocusPending] = useState({}); // staged changes
  const [axisRefresh, setAxisRefresh] = useState(0); // bumped after Save → AxesPanel reloads

  const enterFocus = useCallback((axis) => {
    setFocusAxis(axis);
    if (onEnterClearFilters) onEnterClearFilters(); // the add-papers focus replaces any view filter
    setFocusPending({});
    setFocusMembers(new Set());
    setActiveTab("library"); // bring the library list (where the add buttons live) into view
    api(`/axes/${axis.id}/clusters`).then(r => {
      if (r.ok) setFocusMembers(new Set((r.data || []).flatMap(n => n.papers || []).map(p => p.id)));
    });
  }, [setActiveTab, onEnterClearFilters]);

  const cancelFocus = useCallback(() => { setFocusAxis(null); setFocusPending({}); setFocusMembers(new Set()); }, []);

  // Toggle a paper's staged membership. effective = staged ? (staged==="add") : isMember; click flips it,
  // collapsing back to "no change" when the flip matches the persisted state.
  const toggleFocusPaper = useCallback((paperId) => {
    setFocusPending(prev => {
      const next = { ...prev };
      const isMember = focusMembers.has(paperId);
      const staged = prev[paperId];
      const effective = staged ? staged === "add" : isMember;
      if (effective) {
        if (isMember) next[paperId] = "remove"; else delete next[paperId];
      } else {
        if (isMember) delete next[paperId]; else next[paperId] = "add";
      }
      return next;
    });
  }, [focusMembers]);

  const saveFocus = useCallback(async () => {
    if (!focusAxis) return;
    const entries = Object.entries(focusPending);
    const adds = entries.filter(([, op]) => op === "add").map(([id]) => Number(id));
    const removes = entries.filter(([, op]) => op === "remove").map(([id]) => Number(id));
    await Promise.all([
      ...adds.map(pid => apiPost(`/axes/${focusAxis.id}/papers`, { paper_id: pid })),
      ...removes.map(pid => apiDelete(`/axes/${focusAxis.id}/papers/${pid}`)),
    ]);
    setAxisRefresh(n => n + 1); // AxesPanel reloads counts + the open axis's papers
    cancelFocus();
  }, [focusAxis, focusPending, cancelFocus]);

  return { focusAxis, focusMembers, focusPending, axisRefresh, setAxisRefresh,
    enterFocus, cancelFocus, toggleFocusPaper, saveFocus };
}
