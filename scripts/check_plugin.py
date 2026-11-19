#!/usr/bin/env python3
"""Check the Cursor plugin: the manifest, mcp.json, the stdio alternative and the vendored skill.

Standard library only. Cursor's published manifest schema (cursor/plugins, schemas/plugin.schema.json) is
fetched when the network allows. Its required fields, its allowed keys and the name pattern are checked
too. Without the network the local copies of those lists are used.
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
LOCAL_KEYS = {
    "name", "displayName", "description", "version", "minClientVersions", "author", "publisher",
    "homepage", "repository", "license", "logo", "keywords", "category", "tags", "commands", "agents",
    "skills", "rules", "hooks", "variables", "mcpServers",
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
EXPECTED = {
    "homepage": "https://faxforagents.com",
    "repository": "https://github.com/faxforagents/cursor-plugin",
    "license": "MIT",
    "logo": "https://faxforagents.com/brand/logo-512.png",
}
PATH_FIELDS = ("rules", "agents", "skills", "commands", "hooks", "mcpServers")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?$")


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def fetch_schema() -> dict | None:
    try:
        with urllib.request.urlopen(SCHEMA_URL, timeout=10) as resp:  # noqa: S310
            return json.load(resp)
    except Exception as err:  # noqa: BLE001
        print(f"check_plugin: schema {SCHEMA_URL} not fetched ({err}), checking the local lists only")
        return None


def placeholders(value: object) -> set[str]:
    return set(re.findall(r"\$\{([^}]+)\}", json.dumps(value)))


def check_manifest(plugin: dict, problems: list[str]) -> None:
    schema = fetch_schema()
    keys, author_keys, name_pattern, required = LOCAL_KEYS, LOCAL_AUTHOR_KEYS, LOCAL_NAME_PATTERN, ["name"]
    if schema:
        keys = set(schema.get("properties", {}))
        author = schema.get("$defs", {}).get("author", {})
        author_keys = set(author.get("properties", {})) or LOCAL_AUTHOR_KEYS
        name_pattern = schema.get("properties", {}).get("name", {}).get("pattern", LOCAL_NAME_PATTERN)
        required = list(schema.get("required", ["name"]))
    for field in required:
        if field not in plugin:
            problems.append(f"plugin.json: {field} is required by the schema")
    for field in sorted(set(plugin) - keys):
        problems.append(f"plugin.json: {field} is not a field of the Cursor manifest schema")
    if not re.match(name_pattern, plugin.get("name", "")):
        problems.append("plugin.json: name must be lowercase kebab-case")
    for field in ("name", "displayName", "version", "description", "author", "keywords", *EXPECTED):
        if field not in plugin:
            problems.append(f"plugin.json: {field} is missing")
    for field, value in EXPECTED.items():
        if plugin.get(field) != value:
            problems.append(f"plugin.json: {field} must be {value}")
    if not SEMVER.match(plugin.get("version", "")):
        problems.append("plugin.json: version must be a semantic version")
    author = plugin.get("author", {})
    if not author.get("name"):
        problems.append("plugin.json: author.name is missing")
    for field in sorted(set(author) - author_keys):
        problems.append(f"plugin.json: author.{field} is not allowed by the schema")
    if not plugin.get("keywords"):
        problems.append("plugin.json: keywords must not be empty")
    for field in PATH_FIELDS:
        values = plugin.get(field)
        for value in values if isinstance(values, list) else [values]:
            if isinstance(value, str) and (value.startswith("/") or ".." in Path(value).parts):
                problems.append(f"plugin.json: {field} path {value} must be relative and stay inside the plugin")


def check_variables(plugin: dict, configs: dict[str, dict], problems: list[str]) -> None:
    variables = plugin.get("variables", {})
    if variables.get("type") != "object" or not isinstance(variables.get("properties"), dict):
        problems.append("plugin.json: variables must be {type: object, properties: {...}}")
        return
    declared = variables["properties"]
    for name, spec in declared.items():
        for keyword in sorted(set(spec) - VARIABLE_KEYWORDS):
            problems.append(f"plugin.json: variables.{name} uses {keyword}, which Cursor does not accept")
    for name in variables.get("required", []):
        if name not in declared:
            problems.append(f"plugin.json: variables.required names {name}, which is not declared")
    if KEY_VAR not in variables.get("required", []):
        problems.append(f"plugin.json: {KEY_VAR} must be a required variable")
    for path, config in configs.items():
        for name in sorted(placeholders(config)):
            if name not in declared:
                problems.append(f"{path}: ${{{name}}} is not declared under variables in plugin.json")


def check_mcp(problems: list[str]) -> dict[str, dict]:
    mcp = load("mcp.json")
    hosted = mcp.get("mcpServers", {}).get("faxforagents", {})
    if hosted.get("url") != HOSTED_URL:
        problems.append(f"mcp.json: the hosted server url must be {HOSTED_URL}")
    if hosted.get("headers", {}).get("Authorization") != f"Bearer ${{{KEY_VAR}}}":
        problems.append(f"mcp.json: Authorization must be Bearer ${{{KEY_VAR}}}")
    stdio_cfg = load("alternatives/stdio.mcp.json")
    stdio = stdio_cfg.get("mcpServers", {}).get("faxforagents", {})
    if stdio.get("command") != "npx" or stdio.get("args") != STDIO_ARGS:
        problems.append(f"alternatives/stdio.mcp.json: the server must run npx {' '.join(STDIO_ARGS)}")
    if stdio.get("env", {}).get(KEY_VAR) != f"${{{KEY_VAR}}}":
        problems.append(f"alternatives/stdio.mcp.json: the key must come from ${{{KEY_VAR}}}")
    for path, config in (("mcp.json", mcp), ("alternatives/stdio.mcp.json", stdio_cfg)):
        if re.search(r"ffa_(live|test)_[A-Za-z0-9_-]{8,}", json.dumps(config)):
            problems.append(f"{path}: holds what looks like a real key, use the placeholder")
    return {"mcp.json": mcp, "alternatives/stdio.mcp.json": stdio_cfg}


def check_skills(problems: list[str]) -> None:
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if not skills:
        problems.append("skills/: no SKILL.md found")
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not match:
            problems.append(f"{skill.relative_to(ROOT)}: frontmatter is missing")
            continue
        front = match.group(1)
        if not re.search(rf"^name: {re.escape(skill.parent.name)}$", front, re.M):
            problems.append(f"{skill.relative_to(ROOT)}: frontmatter name must equal the folder name")
        if not re.search(r"^description: \S", front, re.M):
            problems.append(f"{skill.relative_to(ROOT)}: frontmatter description is missing")


def main() -> int:
    problems: list[str] = []
    plugin = load(".cursor-plugin/plugin.json")
    check_manifest(plugin, problems)
    configs = check_mcp(problems)
    check_variables(plugin, configs, problems)
    check_skills(problems)
    if (ROOT / "plugin.json").exists():
        problems.append("plugin.json at the root would make this an Agent Plugin too, keep one manifest")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in ("https://faxforagents.com/privacy", "hello@faxforagents.com", KEY_VAR):
        if needle not in readme:
            problems.append(f"README.md must carry {needle} (usage, configuration, privacy and support)")
    for problem in problems:
        print(f"check_plugin: FAIL: {problem}", file=sys.stderr)
    if not problems:
        print("check_plugin: OK")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
