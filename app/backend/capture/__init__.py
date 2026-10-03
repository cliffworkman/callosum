"""Browser-capture intake (#61 Phase 1): pairing, envelope, admission adapter, idempotency.

The router in ``api/routers/capture.py`` is the HTTP boundary; everything decision-shaped lives here
so the route stays a thin adapter and the logic is testable without a client.
"""
