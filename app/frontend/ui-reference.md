# Frontend UI Reference

`callosum-reference-manager.jsx` is a synthetic interactive mockup for the planned Callosum workbench. It should inform frontend requirements, but it should not be treated as production source until the implementation stack is selected.

## Screens And Regions Implied

- Top bar with product identity and import actions.
- Local-first status note explaining which steps are local and which call a model.
- Semantic-axis sidebar with expandable parent and child axes.
- Paper results list filtered by the selected axis.
- Open-science badges and score bar on each paper.
- Missing-literature suggestion panel.
- Grounded synthesis panel.
- Floating provenance card for cited summary sentences.

## Component Candidates

- `AppShell`
- `ImportActions`
- `SemanticAxisTree`
- `AxisCreator`
- `PaperList`
- `PaperListItem`
- `OpenScienceBadges`
- `MissingLiteratureSuggestions`
- `SynthesisPanel`
- `ConfidenceFloorControl`
- `SentenceWithEvidence`
- `ProvenancePopover`
- `PdfEvidenceLink`

## Data Needed By The UI

Paper list item:

- `id`
- `citationKey`
- `title`
- `venue`
- `year`
- `axisIds`
- `oaStatus`
- `openScienceSignals`
- `openScienceScore`

Axis tree node:

- `id`
- `parentId`
- `label`
- `paperCount`
- `children`

Synthesis sentence:

- `id`
- `text`
- `evidenceMappings`
- `minimumConfidence`
- `status`

Evidence mapping:

- `paperId`
- `paperKey`
- `page`
- `quote`
- `confidence`
- `status`
- `boundingBoxes`
- `chunkId`

Missing-literature suggestion:

- `externalId`
- `title`
- `authors`
- `year`
- `reason`
- `sourceProvider`
- `addableState`

## Accessibility Requirements To Plan

- Provenance must be available by keyboard, not hover alone.
- Confidence and verification status cannot rely only on color.
- Import and synthesis actions need disabled and busy states.
- The axis tree should expose expanded and selected states.
- The PDF jump action should have a clear focus target after navigation.

## Styling Notes

The mockup uses a restrained research-workbench visual style: serif titles, compact metadata, low-saturation panels, and confidence/status colors. Future CSS should preserve the dense, inspection-focused character while adapting it to the selected design system.

