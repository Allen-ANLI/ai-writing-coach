"""Contract checks against contracts/openapi.yaml (the source of truth).

1. The full contract validates as OpenAPI 3.1.
2. The implemented health route matches the contracted path, method and auth.
3. Pydantic envelopes semantically match the contracted HealthResponse/ErrorResponse
   schemas (refs inlined; titles/defaults/nullability normalized away).
"""

import pathlib

import yaml
from openapi_spec_validator import OpenAPIV31SpecValidator

from app.main import create_app
from app.schemas.health import ErrorResponse, HealthResponse

CONTRACT_PATH = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"

_DROP_KEYS = {"title", "description", "default", "examples", "$defs", "definitions"}


def _load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def _resolve_ref(schema: object, root: dict) -> object:
    depth = 0
    while isinstance(schema, dict) and "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/"), f"only local refs are supported: {ref}"
        node: object = root
        for part in ref[2:].split("/"):
            node = node[part]
        schema = node
        depth += 1
        assert depth < 20, "ref cycle"
    return schema


def _canonical(schema: object, root: dict) -> object:
    schema = _resolve_ref(schema, root)
    if not isinstance(schema, dict):
        return schema
    if "anyOf" in schema:
        branches = [
            _canonical(branch, root) for branch in schema["anyOf"] if branch != {"type": "null"}
        ]
        if len(branches) == 1:
            return branches[0]
        return {"anyOf": sorted(branches, key=repr)}
    result: dict = {}
    for key, value in schema.items():
        if key in _DROP_KEYS:
            continue
        if key == "properties":
            result[key] = {name: _canonical(sub, root) for name, sub in value.items()}
        elif key == "required":
            result[key] = sorted(value)
        elif key == "enum" and len(value) == 1:
            result["const"] = value[0]
        elif key == "items":
            result[key] = _canonical(value, root)
        else:
            result[key] = value
    return result


def test_contract_validates_as_openapi_31():
    spec = _load_contract()
    errors = list(OpenAPIV31SpecValidator(spec).iter_errors())
    assert errors == []


def test_health_route_matches_contract():
    spec = _load_contract()
    operation = spec["paths"]["/health"]["get"]
    assert operation["security"] == []
    assert set(operation["responses"]) == {"200", "503"}

    # Contract paths are relative to the /api/v1 server prefix; the app serves
    # the full path. Compare against the OpenAPI document the app generates.
    generated = create_app().openapi()
    assert "/api/v1/health" in generated["paths"]
    generated_get = generated["paths"]["/api/v1/health"]["get"]
    assert set(generated_get["responses"]) == {"200", "503"}
    ok_schema = generated_get["responses"]["200"]["content"]["application/json"]["schema"]
    assert ok_schema["$ref"].endswith("/HealthResponse")
    err_schema = generated_get["responses"]["503"]["content"]["application/json"]["schema"]
    assert err_schema["$ref"].endswith("/ErrorResponse")


def test_register_documents_duplicate_email_conflict():
    spec = _load_contract()
    responses = spec["paths"]["/auth/register"]["post"]["responses"]
    assert "409" in responses
    schema = responses["409"]["content"]["application/json"]["schema"]
    assert schema["$ref"] == "#/components/schemas/ErrorResponse"


def test_health_response_schema_matches_contract():
    spec = _load_contract()
    expected = _canonical(spec["components"]["schemas"]["HealthResponse"], spec)
    schema = HealthResponse.model_json_schema()
    assert _canonical(schema, schema) == expected


def test_error_response_schema_matches_contract():
    spec = _load_contract()
    expected = _canonical(spec["components"]["schemas"]["ErrorResponse"], spec)
    schema = ErrorResponse.model_json_schema()
    assert _canonical(schema, schema) == expected


def test_no_out_of_contract_routes():
    """Every implemented operation must exist in the contract (shape authority)."""
    spec = _load_contract()
    contract_ops = {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    generated = create_app().openapi()
    implemented = {
        (method.upper(), path.removeprefix("/api/v1"))
        for path, item in generated["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert implemented - contract_ops == set()


def test_document_lifecycle_operations_implemented():
    generated = create_app().openapi()["paths"]
    for path, method in [
        ("/api/v1/essays/{essay_id}/working-document", "get"),
        ("/api/v1/essays/{essay_id}/working-document", "put"),
        ("/api/v1/essays/{essay_id}/snapshots", "post"),
        ("/api/v1/essays/{essay_id}/versions", "get"),
        ("/api/v1/essays/{essay_id}/versions/{version_id}", "get"),
        ("/api/v1/essays/{essay_id}/restore", "post"),
    ]:
        assert method in generated[path], f"{method.upper()} {path} missing"


def test_ielts_operations_implemented():
    generated = create_app().openapi()["paths"]
    for path, method in [
        ("/api/v1/ielts/questions", "get"),
        ("/api/v1/ielts/questions/{question_id}", "get"),
        ("/api/v1/ielts/tags", "get"),
        ("/api/v1/ielts/questions/random", "get"),
        ("/api/v1/ielts/questions/{question_id}/favorite", "post"),
        ("/api/v1/ielts/questions/{question_id}/favorite", "delete"),
    ]:
        assert method in generated[path], f"{method.upper()} {path} missing"


def test_evaluation_operations_implemented():
    generated = create_app().openapi()["paths"]
    for path, method in [
        ("/api/v1/essays/{essay_id}/evaluations", "post"),
        ("/api/v1/essays/{essay_id}/evaluations", "get"),
        ("/api/v1/evaluations/{evaluation_id}", "get"),
        ("/api/v1/evaluations/{evaluation_id}", "delete"),
        ("/api/v1/evaluations/{evaluation_id}/rewrite", "post"),
        ("/api/v1/rewrites/{rewrite_id}", "get"),
        ("/api/v1/rewrites/{rewrite_id}/accept", "post"),
    ]:
        assert method in generated[path], f"{method.upper()} {path} missing"


def test_outline_and_workflow_operations_implemented():
    generated = create_app().openapi()["paths"]
    for path, method in [
        ("/api/v1/essays/{essay_id}/outlines/generate", "post"),
        ("/api/v1/essays/{essay_id}/outlines", "get"),
        ("/api/v1/outlines/{outline_id}", "get"),
        ("/api/v1/outlines/{outline_id}", "patch"),
        ("/api/v1/outlines/{outline_id}/confirm", "post"),
        ("/api/v1/outlines/{outline_id}/nodes", "post"),
        ("/api/v1/outlines/{outline_id}/nodes/{node_id}", "patch"),
        ("/api/v1/outlines/{outline_id}/nodes/{node_id}", "delete"),
        ("/api/v1/workflows", "post"),
        ("/api/v1/workflows/{workflow_id}", "get"),
        ("/api/v1/workflows/{workflow_id}/resume", "post"),
        ("/api/v1/workflows/{workflow_id}/cancel", "post"),
        ("/api/v1/workflows/{workflow_id}/events", "get"),
    ]:
        assert method in generated[path], f"{method.upper()} {path} missing"
