#!/usr/bin/env python3
"""Check the Cursor plugin: the manifest, mcp.json, the stdio alternative, the skill and the copy.

Standard library only. Cursor's published manifest schema (cursor/plugins, schemas/plugin.schema.json) is
fetched when the network allows. Its required fields, allowed keys, value types and name pattern are
checked. Without the network the local copies of those lists are used. This is not a full JSON Schema
validator.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_URL = "https://raw.githubusercontent.com/cursor/plugins/main/schemas/plugin.schema.json"

# Local copy of the schema's lists (cursor/plugins e58dd04, 2026-11-19), used when the fetch fails.
LOCAL_TYPES = {
    "name": "string", "displayName": "string", "description": "string", "version": "string",
    "minClientVersions": "object", "author": "object", "publisher": "string", "homepage": "string",
    "repository": "string", "license": "string", "logo": "string", "keywords": "array", "category": "string",
    "tags": "array", "commands": None, "agents": None, "skills": None, "rules": None, "hooks": None,
    "variables": "object", "mcpServers": None,
}
LOCAL_AUTHOR_KEYS = {"name", "email"}
LOCAL_NAME_PATTERN = r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$"

# The JSON Schema keywords Cursor accepts in `variables` (docs/reference/plugins.md, Variables).
VARIABLE_KEYWORDS = {
    "type", "title", "description", "default", "enum", "const", "properties", "required", "items",
    "minLength", "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minItems", "maxItems",
}

HOSTED_URL = "https://mcp.faxforagents.com/mcp/"
KEY_VAR = "FAXFORAGENTS_API_KEY"
STDIO_ARGS = ["-y", "faxforagents-mcp@0.3.1"]
SKILL = "fax-for-agents"
EXPECTED = {
    "homepage": "https://faxforagents.com",
    "repository": "https://github.com/faxforagents/cursor-plugin",
    "license": "MIT",
    "logo": "https://faxforagents.com/brand/logo-512.png",
}
# These fields replace Cursor's default discovery. The checks below read mcp.json and skills/, so the
# manifest must leave discovery alone.
DISCOVERY_FIELDS = ("rules", "agents", "skills", "commands", "hooks", "mcpServers")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?$")
PY_TYPES = {"string": str, "array": list, "object": dict, "boolean": bool}

# The owner's copy rules for text we write (README.md and the manifest). The vendored skill is exempt.
# scripts/truthcheck.sh already refuses competitor names and claims it lists in every tracked file.
COPY_RULES = (
    (r"\bdelivered\b", "never say delivered"),
    (r"\bfree\b", "never call the service free"),
    (r"\bsecure\b|\bcomplian(t|ce)\b", "no compliance or security claims"),
    (r"\$\s?\d", "no prices"),
)


def reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not valid JSON")


def load(path: str, problems: list[str]) -> dict:
    try:
        data = json.loads((ROOT / path).read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, ValueError) as err:
        problems.append(f"{path}: cannot be read as JSON ({err})")
        return {}
    if not isinstance(data, dict):
        problems.append(f"{path}: the top level must be an object")
        return {}
    return data


def obj(value: object, where: str, problems: list[str]) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        problems.append(f"{where} must be an object")
        return {}
    return value


def fetch_schema() -> dict | None:
    try:
        with urllib.request.urlopen(SCHEMA_URL, timeout=10) as resp:  # noqa: S310
            return json.load(resp)
    except Exception as err:  # noqa: BLE001
        print(f"check_plugin: schema {SCHEMA_URL} not fetched ({err}), checking the local lists only")
        return None


def schema_types(schema: dict) -> dict[str, str | None]:
    return {key: spec.get("type") for key, spec in schema.get("properties", {}).items()}


def placeholders(value: object) -> set[str]:
    return set(re.findall(r"\$\{([^}]+)\}", json.dumps(value)))


def check_manifest(plugin: dict, problems: list[str]) -> None:
    schema = fetch_schema()
    types, author_keys, name_pattern, required = LOCAL_TYPES, LOCAL_AUTHOR_KEYS, LOCAL_NAME_PATTERN, ["name"]
    if schema:
        types = schema_types(schema) or LOCAL_TYPES
        author = schema.get("$defs", {}).get("author", {})
        author_keys = set(author.get("properties", {})) or LOCAL_AUTHOR_KEYS
        name_pattern = schema.get("properties", {}).get("name", {}).get("pattern", LOCAL_NAME_PATTERN)
        required = list(schema.get("required", ["name"]))
    for field in required:
        if field not in plugin:
            problems.append(f"plugin.json: {field} is required by the schema")
    for field, value in plugin.items():
        if field not in types:
            problems.append(f"plugin.json: {field} is not a field of the Cursor manifest schema")
            continue
        expected = types[field]
        if expected and not isinstance(value, PY_TYPES[expected]):
            problems.append(f"plugin.json: {field} must be of type {expected}")
    for field in ("keywords", "tags"):
        if isinstance(plugin.get(field), list) and not all(isinstance(item, str) for item in plugin[field]):
            problems.append(f"plugin.json: every item of {field} must be a string")
    if not isinstance(plugin.get("name"), str) or not re.match(name_pattern, plugin["name"]):
        problems.append("plugin.json: name must be lowercase kebab-case")
    for field in ("name", "displayName", "version", "description", "author", "keywords", *EXPECTED):
        if field not in plugin:
            problems.append(f"plugin.json: {field} is missing")
    for field, value in EXPECTED.items():
        if plugin.get(field) != value:
            problems.append(f"plugin.json: {field} must be {value}")
    if not isinstance(plugin.get("version"), str) or not SEMVER.match(plugin["version"]):
        problems.append("plugin.json: version must be a semantic version")
    author = obj(plugin.get("author"), "plugin.json: author", problems)
    if not isinstance(author.get("name"), str) or not author["name"]:
        problems.append("plugin.json: author.name is missing")
    if "email" in author and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(author["email"])):
        problems.append("plugin.json: author.email must be an email address")
    for field in sorted(set(author) - author_keys):
        problems.append(f"plugin.json: author.{field} is not allowed by the schema")
    if not plugin.get("keywords"):
        problems.append("plugin.json: keywords must not be empty")
    for field in DISCOVERY_FIELDS:
        if field in plugin:
            problems.append(f"plugin.json: {field} replaces Cursor's default discovery, leave it out")


def check_variables(plugin: dict, configs: dict[str, dict], problems: list[str]) -> None:
    variables = obj(plugin.get("variables"), "plugin.json: variables", problems)
    declared = variables.get("properties")
    if variables.get("type") != "object" or not isinstance(declared, dict):
        problems.append("plugin.json: variables must be {type: object, properties: {...}}")
        return
    for name, spec in declared.items():
        spec = obj(spec, f"plugin.json: variables.{name}", problems)
        for keyword in sorted(set(spec) - VARIABLE_KEYWORDS):
            problems.append(f"plugin.json: variables.{name} uses {keyword}, which Cursor does not accept")
    required = variables.get("required", [])
    if not isinstance(required, list):
        problems.append("plugin.json: variables.required must be a list")
        required = []
    for name in required:
        if name not in declared:
            problems.append(f"plugin.json: variables.required names {name}, which is not declared")
    if KEY_VAR not in required:
        problems.append(f"plugin.json: {KEY_VAR} must be a required variable")
    for path, config in configs.items():
        for name in sorted(placeholders(config)):
            if name not in declared:
                problems.append(f"{path}: ${{{name}}} is not declared under variables in plugin.json")


def only_server(config: dict, path: str, problems: list[str]) -> dict:
    servers = obj(config.get("mcpServers"), f"{path}: mcpServers", problems)
    if set(servers) != {"faxforagents"}:
        problems.append(f"{path}: mcpServers must hold exactly one server, faxforagents")
    return obj(servers.get("faxforagents"), f"{path}: mcpServers.faxforagents", problems)


def check_mcp(problems: list[str]) -> dict[str, dict]:
    mcp = load("mcp.json", problems)
    hosted = only_server(mcp, "mcp.json", problems)
    if set(hosted) - {"type", "url", "headers"} or hosted.get("type") != "http":
        problems.append("mcp.json: the server takes type http, url and headers only")
    if hosted.get("url") != HOSTED_URL:
        problems.append(f"mcp.json: the hosted server url must be {HOSTED_URL}")
    headers = obj(hosted.get("headers"), "mcp.json: headers", problems)
    if headers != {"Authorization": f"Bearer ${{{KEY_VAR}}}"}:
        problems.append(f"mcp.json: headers must be only Authorization: Bearer ${{{KEY_VAR}}}")
    stdio_cfg = load("alternatives/stdio.mcp.json", problems)
    stdio = only_server(stdio_cfg, "alternatives/stdio.mcp.json", problems)
    if set(stdio) - {"command", "args", "env"}:
        problems.append("alternatives/stdio.mcp.json: the server takes command, args and env only")
    if stdio.get("command") != "npx" or stdio.get("args") != STDIO_ARGS:
        problems.append(f"alternatives/stdio.mcp.json: the server must run npx {' '.join(STDIO_ARGS)}")
    if obj(stdio.get("env"), "alternatives/stdio.mcp.json: env", problems) != {KEY_VAR: f"${{{KEY_VAR}}}"}:
        problems.append(f"alternatives/stdio.mcp.json: env must be only {KEY_VAR} from ${{{KEY_VAR}}}")
    for path, config in (("mcp.json", mcp), ("alternatives/stdio.mcp.json", stdio_cfg)):
        if re.search(r"ffa_(live|test)_[A-Za-z0-9_-]{8,}", json.dumps(config)):
            problems.append(f"{path}: holds what looks like a real key, use the placeholder")
    return {"mcp.json": mcp, "alternatives/stdio.mcp.json": stdio_cfg}


def check_skills(problems: list[str]) -> None:
    # CI compares skills/fax-for-agents with faxforagents/skills byte for byte. Any other skill would
    # skip that comparison, so it is refused here.
    folders = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()) if (ROOT / "skills").is_dir() else []
    if folders != [SKILL]:
        problems.append(f"skills/: must hold only {SKILL}, found {folders}")
    if (ROOT / "SKILL.md").exists():
        problems.append("SKILL.md at the root would be read as a second skill")
    skill = ROOT / "skills" / SKILL / "SKILL.md"
    text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        problems.append(f"skills/{SKILL}/SKILL.md: missing, or its frontmatter is missing")
        return
    front = match.group(1)
    if not re.search(rf"^name: {re.escape(SKILL)}$", front, re.M):
        problems.append(f"skills/{SKILL}/SKILL.md: frontmatter name must be {SKILL}")
    if not re.search(r"^description: \S", front, re.M):
        problems.append(f"skills/{SKILL}/SKILL.md: frontmatter description is missing")


def check_copy(plugin: dict, readme: str, problems: list[str]) -> None:
    texts = {"README.md": readme, "plugin.json": json.dumps(plugin, ensure_ascii=False)}
    for path, text in texts.items():
        for pattern, rule in COPY_RULES:
            found = re.search(pattern, text, re.I)
            if found:
                problems.append(f"{path}: {rule} (found {found.group(0)!r})")


def main() -> int:
    problems: list[str] = []
    plugin = load(".cursor-plugin/plugin.json", problems)
    check_manifest(plugin, problems)
    configs = check_mcp(problems)
    check_variables(plugin, configs, problems)
    check_skills(problems)
    if (ROOT / "plugin.json").exists():
        problems.append("plugin.json at the root would make this an Agent Plugin too, keep one manifest")
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    for needle in ("https://faxforagents.com/privacy", "hello@faxforagents.com", KEY_VAR):
        if needle not in readme:
            problems.append(f"README.md must carry {needle} (usage, configuration, privacy and support)")
    check_copy(plugin, readme, problems)
    for problem in problems:
        print(f"check_plugin: FAIL: {problem}", file=sys.stderr)
    if not problems:
        print("check_plugin: OK")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
