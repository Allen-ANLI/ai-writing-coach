"""Verify the configured real LLM provider (connectivity, model, structured
output, usage reporting). Never prints the API key.

Run from backend/:  .venv\\Scripts\\python.exe scripts\\verify_llm.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.ai import llm  # noqa: E402
from app.ai.schemas import ValidationJudgement  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import ApiError  # noqa: E402


def main() -> int:
    settings = get_settings()
    print(f"provider: {settings.llm_provider}")
    print(f"base_url: {settings.llm_base_url or '(unset)'}")
    print(f"model:    {settings.llm_model or '(unset)'}")
    key_state = "configured" if settings.llm_api_key else "MISSING — set LLM_API_KEY in .env"
    print(f"api_key:  {key_state}")
    if settings.llm_provider == "mock":
        print("NOTE: mock provider active; real connectivity not tested.")
    if not settings.llm_api_key and settings.llm_provider != "mock":
        return 2

    try:
        parsed, usage = llm.call_llm(
            system=(
                "You are a connectivity probe. Judge the sentence and reply with the "
                "required JSON only."
            ),
            user=(
                "Original sentence: He go to school.\nIssue category: grammar\n"
                "Original fragment: go\nExplanation given: subject-verb agreement\n"
                "User's corrected sentence: He goes to school.\nReturn JSON: status, reason."
            ),
            response_model=ValidationJudgement,
        )
    except ApiError as exc:
        print(f"FAILED: {exc.status_code} {exc.code} — {exc.message}")
        return 1

    print("structured output OK:", parsed.model_dump())
    print(
        f"usage: provider={usage.provider} model={usage.model_name} "
        f"input_tokens={usage.input_tokens} output_tokens={usage.output_tokens} "
        f"latency_ms={usage.latency_ms} estimated_cost={usage.estimated_cost}"
    )
    if usage.model_name != settings.llm_model:
        print(
            f"WARNING: configured model {settings.llm_model!r} but provider reported "
            f"{usage.model_name!r} — verify the model name before production use."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
