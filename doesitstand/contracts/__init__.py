import json
from pathlib import Path

import jsonschema

_SCHEMAS_DIR = Path(__file__).parent


def validate_artifact(data: dict, schema_id: str) -> None:
    """Validate *data* against the JSON schema identified by *schema_id*.

    schema_id examples: "evidence.v1", "dossier.v1", "reference_check_report.v1"
    Raises jsonschema.ValidationError on failure.
    """
    schema_path = _SCHEMAS_DIR / f"{schema_id}.schema.json"
    schema = json.loads(schema_path.read_text())
    jsonschema.validate(instance=data, schema=schema)
