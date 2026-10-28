#!/usr/bin/env python3
"""Private personal resource catalog over gh; credentials never appear by default."""
import argparse
import base64
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlsplit

MAX_BYTES = 512 * 1024
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IDENT = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
SENSITIVE = re.compile(r"(^|_)(key|secret|token|password|credential)(_|$)", re.I)


class ResourceError(Exception):
    pass


def api(path, method="GET", payload=None):
    args = [os.environ.get("GITHUB_RESOURCES_GH", "gh"), "api", "--hostname", "github.com", path]
    if method != "GET":
        args += ["--method", method]
    if payload is not None:
        args += ["--input", "-"]
    try:
        result = subprocess.run(args, input=json.dumps(payload) if payload is not None else None,
                                capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        raise ResourceError("GitHub request did not complete; inspect remote state before retrying a write.") from None
    if result.returncode:
        # gh errors can include request content or credentials. Never echo stderr.
        raise ResourceError("GitHub request failed; check gh login, repository permissions, network and conflicts.")
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise ResourceError("GitHub returned an unexpected response.") from None


def config_path():
    if os.environ.get("GITHUB_RESOURCES_CONFIG"):
        return Path(os.environ["GITHUB_RESOURCES_CONFIG"]).expanduser()
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "github-resources/config.json"


def load_binding():
    path = config_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        raise ResourceError("Cannot read the local repository binding.") from None


def private_repo(name):
    if not isinstance(name, str) or not REPO.fullmatch(name):
        raise ResourceError("Repository must be owner/name.")
    info = api("repos/" + name)
    if info.get("private") is not True:
        raise ResourceError("Resource repositories must be private; no catalog was read or written.")
    if not info.get("permissions", {}).get("pull"):
        raise ResourceError("Repository read access is required.")
    return info


def context(repo_arg=None):
    user = api("user")["login"]
    binding = load_binding()
    if binding and binding.get("account", "").lower() != user.lower():
        raise ResourceError("GitHub account changed; explicitly bind the resource repository again.")
    name = repo_arg or os.environ.get("GITHUB_RESOURCES_REPO") or (binding or {}).get("repository")
    name = name or user + "/personal-resources"
    info = private_repo(name)
    return user, info


def read_catalog(info, ref=None):
    branch = ref or info["default_branch"]
    obj = api("repos/" + info["full_name"] + "/contents/catalog.json?ref=" + quote(branch, safe=""))
    try:
        if obj.get("size", MAX_BYTES + 1) > MAX_BYTES:
            raise ValueError()
        raw = base64.b64decode(obj["content"])
        data = json.loads(raw)
        validate_catalog(data)
    except (ValueError, KeyError, TypeError):
        raise ResourceError("Catalog is invalid or exceeds 512 KiB; no contents were printed.") from None
    return data, obj["sha"]


def validate_config(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if SENSITIVE.search(key) or key.lower() in {"authorization", "connection_string", "connection_url"}:
                raise ValueError("Sensitive fields belong in secrets")
            validate_config(item)
    elif isinstance(value, list):
        for item in value:
            validate_config(item)
    elif isinstance(value, str) and "://" in value:
        parsed = urlsplit(value)
        if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
            raise ValueError("Credential-bearing URLs belong in secrets")


def validate_resource(item):
    allowed = {"id", "name", "aliases", "kind", "environment", "scope", "capabilities", "docs", "config", "secrets", "notes", "verification"}
    if not isinstance(item, dict) or set(item) - allowed:
        raise ValueError("Unknown resource fields")
    for key in ("id", "name", "kind", "environment", "scope"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise ValueError("Missing resource identity")
    if not IDENT.fullmatch(item["id"]):
        raise ValueError("Invalid resource ID")
    for key in ("aliases", "capabilities"):
        if not isinstance(item.get(key, []), list) or any(not isinstance(v, str) for v in item.get(key, [])):
            raise ValueError("Invalid list")
    if not isinstance(item.get("config", {}), dict) or not isinstance(item.get("secrets", {}), dict):
        raise ValueError("Invalid configuration")
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in item.get("secrets", {}).items()):
        raise ValueError("Secrets must contain string values")
    validate_config(item.get("config", {}))


def validate_catalog(data):
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("resources"), list):
        raise ValueError("Invalid catalog")
    seen = set()
    for item in data["resources"]:
        validate_resource(item)
        if item["id"] in seen:
            raise ValueError("Duplicate resource ID")
        seen.add(item["id"])
    if len(json.dumps(data).encode()) > MAX_BYTES:
        raise ValueError("Catalog too large")


def summary(item, info):
    fields = ("id", "name", "aliases", "kind", "environment", "scope", "capabilities")
    value = {k: item[k] for k in fields if k in item}
    value["url"] = info["html_url"] + "/blob/" + quote(info["default_branch"], safe="") + "/catalog.json"
    return value


def capability_overview(data, info):
    groups = {}
    for item in data["resources"]:
        metadata = summary(item, info)
        metadata.update({"config": item.get("config", {}), "docs": item.get("docs", []),
                         "verification": item.get("verification", {})})
        for capability in item.get("capabilities", []):
            groups.setdefault(capability, []).append(metadata)
    return groups


def merge_metadata(old, patch):
    """Merge observations without replacing unrelated configuration or credentials."""
    if isinstance(old, dict) and isinstance(patch, dict):
        result = copy.deepcopy(old)
        for key, value in patch.items():
            result[key] = merge_metadata(result[key], value) if key in result else copy.deepcopy(value)
        return result
    if isinstance(old, list) and isinstance(patch, list):
        result = copy.deepcopy(old)
        for value in patch:
            if value not in result:
                result.append(copy.deepcopy(value))
        return result
    return copy.deepcopy(patch)


def record_metadata(data, resource_id, patch):
    if not isinstance(patch, dict) or not patch or set(patch) - {"capabilities", "docs", "verification", "config"}:
        raise ResourceError("record accepts capability, documentation, verification and integration metadata only.")
    if "config" in patch and (not isinstance(patch["config"], dict) or set(patch["config"]) - {
            "models", "model_discovery", "integration", "observed_limits", "recommendations", "preferred_for"}):
        raise ResourceError("record cannot change endpoints, defaults or credentials; maintain them explicitly with put.")
    if "verification" in patch and not isinstance(patch["verification"], dict):
        raise ResourceError("Verification evidence must be an object.")
    if "docs" in patch and (not isinstance(patch["docs"], list) or any(
            not isinstance(v, dict) or set(v) - {"title", "url"} or
            not isinstance(v.get("title"), str) or not isinstance(v.get("url"), str)
            for v in patch["docs"])):
        raise ResourceError("Documentation must contain title and URL records.")
    validate_config(patch)
    # Keep known credentials out of observation text, including values under innocent field names.
    encoded = json.dumps(patch, ensure_ascii=False)
    for resource in data["resources"]:
        for secret in resource.get("secrets", {}).values():
            if len(secret) >= 8 and secret in encoded:
                raise ResourceError("A credential was detected in metadata; it was not saved.")
    item = select(data, resource_id)
    updated = merge_metadata(item, patch)
    validate_resource(updated)
    return updated


def save_catalog(info, data, sha, resource_id):
    validate_catalog(data)
    content = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    private_repo(info["full_name"])
    result = api("repos/" + info["full_name"] + "/contents/catalog.json", "PUT", {
        "message": "chore: maintain personal resource " + resource_id, "branch": info["default_branch"],
        "sha": sha, "content": base64.b64encode(content).decode()})
    commit = result["commit"]["sha"]
    verified, _ = read_catalog(info, commit)
    if verified != data:
        raise ResourceError("Write completed but verification failed; inspect remote state before retrying.")
    return commit


def select(data, resource_id):
    matches = [item for item in data["resources"] if item["id"] == resource_id]
    if len(matches) != 1:
        raise ResourceError("Resource ID not found; search first and select its exact ID.")
    return matches[0]


def get_field(item, path):
    if not isinstance(path, str) or not path.startswith(("config.", "secrets.")):
        raise ResourceError("Mappings must reference config.* or secrets.* fields.")
    value = item
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ResourceError("A mapped configuration field does not exist.")
        value = value[part]
    if not isinstance(value, str) or not value:
        raise ResourceError("Mapped fields must be nonempty strings.")
    return value


def env_bytes(item, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ResourceError("Mapping file must be a nonempty JSON object.")
    lines = []
    for key, path in mapping.items():
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            raise ResourceError("Invalid environment variable name.")
        value = get_field(item, path)
        # This command targets literal dotenv values, never shell source/Compose interpolation.
        # Reject ambiguous characters instead of silently corrupting passwords.
        if any(c in value for c in ("'", "\n", "\r", "\x00")):
            raise ResourceError("This value cannot be exported losslessly as a dotenv literal; use a client-specific adapter.")
        lines.append(key + "='" + value + "'\n")
    return "".join(lines).encode()


def write_private(path, content, overwrite=False):
    path = Path(path).expanduser().absolute()
    if path.is_symlink() or path.exists() and not overwrite:
        raise ResourceError("Output already exists or is a symlink; choose another path or explicitly authorize overwrite.")
    if not path.parent.is_dir():
        raise ResourceError("Output parent directory does not exist.")
    fd, tmp = tempfile.mkstemp(prefix=".github-resources-", dir=str(path.parent))
    try:
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        if overwrite:
            os.replace(tmp, path)
        else:
            # Atomic no-clobber creation, including a concurrent writer.
            os.link(tmp, path)
    except FileExistsError:
        raise ResourceError("Output was created concurrently; it was not overwritten.") from None
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(args):
    if args.command == "bind":
        user = api("user")["login"]
        info = private_repo(args.repository)
        read_catalog(info)
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        write_private(path, (json.dumps({"account": user, "repository": info["full_name"]}) + "\n").encode(), overwrite=True)
        return {"account": user, "repository": info["full_name"], "binding": str(path), "credentials_stored": False}
    user, info = context(args.repo)
    data, sha = read_catalog(info)
    base = {"repository": info["full_name"], "account": user, "private": True, "catalog_sha": sha}
    if args.command == "status":
        return dict(base, count=len(data["resources"]), url=info["html_url"])
    if args.command == "capabilities":
        return dict(base, capabilities=capability_overview(data, info), resource_count=len(data["resources"]),
                    scope="complete catalog metadata; verification is evidence, not a guarantee of current availability")
    if args.command in {"list", "search"}:
        items = [summary(item, info) for item in data["resources"]]
        if args.command == "search":
            query = args.query.casefold()
            items = [item for item in items if query in json.dumps(item, ensure_ascii=False).casefold()]
        return dict(base, resources=items, count=len(items), coverage="complete catalog; metadata only")
    if args.command in {"show", "export"}:
        item = select(data, args.id)
        if args.command == "show":
            # Mask the complete secrets object, regardless of field names.
            safe = {key: value for key, value in item.items() if key != "secrets"}
            safe["secrets"] = {key: "[REDACTED]" for key in item.get("secrets", {})}
            return dict(base, resource=safe, url=summary(item, info)["url"])
        mapping = json.loads(Path(args.map_file).read_text())
        content = env_bytes(item, mapping)
        write_private(args.output, content, overwrite=args.overwrite)
        return dict(base, resource_id=item["id"], output=str(Path(args.output).absolute()), variables=list(mapping), values_printed=False)
    if args.command in {"put", "record"}:
        if not info.get("permissions", {}).get("push"):
            raise ResourceError("Repository write access is required.")
        raw = sys.stdin.read(MAX_BYTES + 1) if args.file == "-" else Path(args.file).read_text()
        if len(raw.encode()) > MAX_BYTES:
            raise ResourceError("Resource input is too large.")
        item = json.loads(raw)
        if args.command == "record":
            if args.expected_sha != sha:
                raise ResourceError("Recording evidence requires the current catalog SHA.")
            old = select(data, args.id)
            item = record_metadata(data, args.id, item)
            if item == old:
                return dict(base, resource_id=args.id, changed=False, verified=True)
        validate_resource(item)
        old = next((i for i in data["resources"] if i["id"] == item["id"]), None)
        if old and args.expected_sha != sha:
            raise ResourceError("Updating an existing resource requires its current catalog SHA.")
        if args.expected_sha and args.expected_sha != sha:
            raise ResourceError("Catalog changed; read it again before saving.")
        if old:
            data["resources"][data["resources"].index(old)] = item
        else:
            data["resources"].append(item)
        commit = save_catalog(info, data, sha, item["id"])
        return dict(base, resource_id=item["id"], commit=commit, verified=True)
    raise ResourceError("Unknown command.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="Private owner/repo; defaults to local binding or ACCOUNT/personal-resources")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("list")
    commands.add_parser("capabilities")
    p = commands.add_parser("bind")
    p.add_argument("repository")
    p = commands.add_parser("search")
    p.add_argument("query")
    p = commands.add_parser("show")
    p.add_argument("id")
    p = commands.add_parser("export")
    p.add_argument("id")
    p.add_argument("--map-file", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--overwrite", action="store_true")
    p = commands.add_parser("put")
    p.add_argument("--file", required=True, help="Resource JSON file, or - for stdin")
    p.add_argument("--expected-sha")
    p = commands.add_parser("record")
    p.add_argument("id")
    p.add_argument("--file", required=True, help="Metadata JSON patch file, or - for stdin")
    p.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=False, indent=2))
    except ResourceError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, TypeError, OSError):
        # Never let JSON validation, IO errors or tracebacks echo a secret input.
        print(json.dumps({"error": "Operation failed safely. Check resource schema, current SHA, gh access, binding and output path; no secret values were printed."}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
