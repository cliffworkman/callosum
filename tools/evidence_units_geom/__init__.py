"""Proposition-preserving evidence-unit study (post-H1a). Dev-only scratch; no production imports.

Distinct path suffix `_geom` because a second agent is independently running the same study; a
shared directory would let us silently overwrite each other's measurements.

Frozen input state is the commit `614338b` (inc 577, H1a) plus the DB snapshot recorded by
`freeze.py`. Nothing here writes to a production database.
"""
