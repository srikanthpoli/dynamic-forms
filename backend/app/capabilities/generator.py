"""Generate the scoped Angular Material capability registry from official docs."""

import json
import logging
import re
import tempfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from app.config import get_settings
from app.llm.provider import get_chat_model
from app.vectorstore.store import build_or_refresh_index

logger = logging.getLogger(__name__)

OFFICIAL_DOCS = {
    "text": "https://material.angular.dev/components/input/overview",
    "autocomplete": "https://material.angular.dev/components/autocomplete/overview",
    "select": "https://material.angular.dev/components/select/overview",
    "checkbox": "https://material.angular.dev/components/checkbox/overview",
}

COMPONENT_DEFAULTS = {
    "text": {
        "angular_tag": "mat-form-field",
        "inner_element": "input matInput",
        "module": "MatInputModule",
    },
    "autocomplete": {
        "angular_tag": "mat-form-field",
        "inner_element": "input matInput [matAutocomplete]",
        "module": "MatAutocompleteModule",
    },
    "select": {
        "angular_tag": "mat-form-field",
        "inner_element": "mat-select",
        "module": "MatSelectModule",
    },
    "checkbox": {
        "angular_tag": "mat-checkbox",
        "inner_element": "mat-checkbox",
        "module": "MatCheckboxModule",
    },
}


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "dynamic-forms-capability-generator/1.0"})
    with urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="replace")

    class TextParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts: list[str] = []
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in {"script", "style", "noscript", "svg"}:
                self.skip += 1

        def handle_endtag(self, tag):
            if tag in {"script", "style", "noscript", "svg"} and self.skip:
                self.skip -= 1

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)

    parser = TextParser()
    parser.feed(raw)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:30000]


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    return json.loads(content)


def _validate_registry(registry: dict, components: list[str]) -> dict:
    framework_value = registry.get("framework")
    if isinstance(framework_value, dict):
        framework = str(framework_value.get("name", "")).strip()
    else:
        framework = str(framework_value or "").strip()
    if framework and "angular material" not in framework.lower():
        raise ValueError("Generated registry has an invalid framework")
    registry["framework"] = "Angular Material"

    fields = registry.get("supported_fields")
    if not isinstance(fields, list):
        raise ValueError("Generated registry must contain supported_fields")

    by_type = {field.get("type"): field for field in fields if isinstance(field, dict)}
    missing = set(components) - set(by_type)
    if missing:
        raise ValueError(f"Generated registry is missing components: {sorted(missing)}")

    for component in components:
        field = by_type[component]
        defaults = COMPONENT_DEFAULTS[component]
        for key, value in defaults.items():
            if not field.get(key):
                field[key] = value
        if not field.get("angular_tag") or not field.get("inner_element"):
            raise ValueError(f"Generated component is incomplete: {component}")
        field["documentation_url"] = OFFICIAL_DOCS[component]

    registry["supported_fields"] = [by_type[component] for component in components]

    registry["generated_at"] = datetime.now(UTC).isoformat()
    registry["documentation_source"] = "official Angular Material documentation"
    return registry


def generate_capabilities(components: list[str] | None = None) -> dict:
    settings = get_settings()
    selected = components or list(OFFICIAL_DOCS)
    unknown = set(selected) - set(OFFICIAL_DOCS)
    if unknown:
        raise ValueError(f"Unsupported capability components: {sorted(unknown)}")

    docs = {component: _fetch_text(OFFICIAL_DOCS[component]) for component in selected}
    prompt = (
        "Create a strict JSON Angular Material capability registry from the official "
        "documentation excerpts below. Preserve only the requested field types. "
        "Do not invent API names. The framework is always Angular Material; do not "
        "need to return a framework field. Include type, angular_tag, inner_element, module, "
        "allowed_inputs, allowed_outputs, allowed_validations, and any required "
        "options/api configuration. Return keys framework, angular_material_version, "
        "supported_fields.\n\n"
        f"Requested types: {json.dumps(selected)}\n"
        f"Documentation excerpts: {json.dumps(docs)}"
    )
    response = get_chat_model(temperature=0, json_mode=True).invoke(prompt)
    registry = _validate_registry(_parse_json(response.content), selected)

    target = Path(settings.material_spec_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as temporary:
        json.dump(registry, temporary, indent=2)
        temporary.write("\n")
        temp_path = Path(temporary.name)
    temp_path.replace(target)
    build_or_refresh_index()
    logger.info("Generated capability registry components=%s path=%s", selected, target)
    return registry
