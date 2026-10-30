// Active-library identity badge. Renders only when the backend reports `library` on /health, which happens
// only when a launcher sets CALLOSUM_LIBRARY_LABEL (the dev launcher does; the packaged app does not), so the
// installed app's Library header is unchanged. The count is the backend's live (non-trashed) paper count, not
// the filtered "N shown" list size, so a researcher can confirm which database is open before trusting it.
function LibraryIdentityBadge() {
  const [library, setLibrary] = useState(null);
  useEffect(() => {
    let alive = true;
    api("/health").then(r => { if (alive && r.ok && r.data && r.data.library) setLibrary(r.data.library); });
    return () => { alive = false; };
  }, []);
  if (!library) return null;
  const count = library.live_papers == null ? "count unavailable" : `${library.live_papers} live papers`;
  return (
    <span className="library-identity" title={library.db_file ? `Database file: ${library.db_file}` : undefined}>
      {library.label} · {count}
    </span>
  );
}
