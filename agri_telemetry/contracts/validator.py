"""
JSON Schema Validator for Agri Telemetry Contracts.
Validates payloads directly against Draft 2020-12 schemas under Event & Telemetry Contract/schemas/.
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple, List
import jsonschema
from jsonschema.validators import validator_for


# Base path to canonical JSON schemas
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "Event & Telemetry Contract" / "schemas"

# Schema file mappings
SCHEMA_FILES = {
    "telemetry": "telemetry-event.schema.json",
    "forecast": "forecast-event.schema.json",
    "alert": "alert-event.schema.json",
}

_LOADED_SCHEMAS: Dict[str, Any] = {}
_VALIDATORS: Dict[str, Any] = {}


def load_schema(schema_key: str) -> Dict[str, Any]:
    """Loads and caches the specified JSON Schema."""
    if schema_key in _LOADED_SCHEMAS:
        return _LOADED_SCHEMAS[schema_key]
    
    filename = SCHEMA_FILES.get(schema_key)
    if not filename:
        raise ValueError(f"Unknown schema key: '{schema_key}'. Available: {list(SCHEMA_FILES.keys())}")
    
    schema_path = SCHEMAS_DIR / filename
    if not schema_path.exists():
        raise FileNotFoundError(f"Canonical schema file not found: {schema_path.resolve()}")
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_dict = json.load(f)
    
    _LOADED_SCHEMAS[schema_key] = schema_dict
    
    validator_cls = validator_for(schema_dict)
    validator_cls.check_schema(schema_dict)
    _VALIDATORS[schema_key] = validator_cls(schema_dict)
    
    return schema_dict


def validate_payload(schema_key: str, payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a python dictionary against the designated Draft 2020-12 JSON Schema.
    Returns: (is_valid: bool, error_messages: List[str])
    """
    if schema_key not in _VALIDATORS:
        load_schema(schema_key)
    
    validator = _VALIDATORS[schema_key]
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    
    if not errors:
        return True, []
    
    error_msgs = []
    for err in errors:
        field_path = ".".join(str(p) for p in err.path) if err.path else "root"
        error_msgs.append(f"[{field_path}] {err.message}")
    
    return False, error_msgs


def assert_valid_payload(schema_key: str, payload: Dict[str, Any]) -> None:
    """Raises jsonschema.ValidationError if payload is invalid."""
    is_valid, errors = validate_payload(schema_key, payload)
    if not is_valid:
        raise jsonschema.ValidationError(
            f"Schema validation failed for '{schema_key}':\n" + "\n".join(f" - {e}" for e in errors)
        )
