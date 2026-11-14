"""Writing sessions: mode-derived feature flags and session lifecycle.

Mode restrictions are enforced here on the backend (SD §10, AGENTS): the
enabled_features map is always server-derived from the session mode, never
trusted from the client. Grammar/AI slices must check it before assisting.
"""
