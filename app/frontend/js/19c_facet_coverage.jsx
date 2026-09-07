// inc 581: per-facet coverage strip for a broad (faceted) Ask synthesis. Extracted from
// 20_synthesis.jsx to keep it under the 600-line cap (shared-IIFE hoist — FacetCoverageStrip is a
// function declaration, callable from 20_synthesis.jsx). Supported = verified evidence found (green
// cite-status pill); everything else is amber "unresolved" and NEVER claims the library lacks the
// topic — the honesty rule: retrieval failure is not evidence absence.
const FACET_COVERAGE_LABEL = {
  supported: "supported",
  partial: "partial",
  retrieved_unverified: "no verified evidence",
  no_evidence_retrieved: "no evidence retrieved",
};

function FacetCoverageStrip({ coverage }) {
  if (!coverage || !coverage.length) return null;
  // A facet "has verified evidence" if any of its claims verified — whether or not it also produced
  // unverified candidates. Counting only status=="supported" (zero-flagged) would undersell a facet
  // that verified real evidence AND generated some unverified candidates (status "partial").
  const withVerified = coverage.filter(c => c.verified_claim_count > 0).length;
  return (
    <div className="synth-coverage" role="status" style={{ marginTop: 10 }}>
      <div><b>Facet coverage</b> — {withVerified} of {coverage.length} facet{coverage.length === 1 ? "" : "s"} have verified evidence.</div>
      <ul style={{ listStyle: "none", margin: "6px 0 0", padding: 0 }}>
        {coverage.map((c, i) => (
          <li key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", margin: "3px 0" }}>
            <span className={"cite-status " + (c.status === "supported" ? "verified" : "flagged")}>
              {FACET_COVERAGE_LABEL[c.status] || c.status}
            </span>
            <span>{c.label}</span>
            <span style={{ opacity: 0.7 }}>
              {c.verified_claim_count} verified{c.flagged_claim_count ? " · " + c.flagged_claim_count + " unverified" : ""}
              {" · "}{c.retrieved_chunk_count} passage{c.retrieved_chunk_count === 1 ? "" : "s"}
            </span>
          </li>
        ))}
      </ul>
      <div style={{ marginTop: 4 }}>
        “No verified evidence” / “no evidence retrieved” means none was found in the retrieved passages — not that your library lacks the topic.
      </div>
    </div>
  );
}
