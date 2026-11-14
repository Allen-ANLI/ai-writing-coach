"""Grammar module: rule-first checking, issue lifecycle, contextual teaching.

Invariants (AGENTS §4): issues anchor to source_server_revision; offsets are
unicode_codepoint; unrevealed suggested_text never leaves the server; LLM
judgement happens outside long DB transactions.
"""
