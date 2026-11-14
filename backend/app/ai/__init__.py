"""AI service layer: provider abstraction, prompts, structured outputs.

Business modules never bind to a vendor SDK directly (SD §7.1). Every call is
validated with Pydantic and logged to ai_usage_logs (SD §12.4). LLM calls must
happen outside long DB transactions (AGENTS §4).
"""
