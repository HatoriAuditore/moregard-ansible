#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path


SECTION_HEADER = "[linux_hosts]"


def _load_vm_names() -> list[str]:
    raw = os.getenv("VM_NAMES_JSON") or ""
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"VM_NAMES_JSON is not valid JSON: {exc}") from exc
        if isinstance(data, list):
            return [str(item) for item in data if str(item).strip()]

    fallback = os.getenv("VM_NAMES", "")
    return [item.strip() for item in fallback.split(",") if item.strip()]


def _load_tfvars_vms() -> dict[str, dict]:
    raw = os.getenv("TF_VARS_CONTENT_B64") or ""
    if not raw:
        return {}

    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Could not decode TF_VARS_CONTENT_B64: {exc}") from exc

    vms = payload.get("vms", {})
    if not isinstance(vms, dict):
        return {}
    return {str(name): value for name, value in vms.items() if isinstance(value, dict)}


def _load_inventory_sync_vms() -> dict[str, dict]:
    raw = os.getenv("INVENTORY_SYNC_VM_JSON") or ""
    if not raw:
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"INVENTORY_SYNC_VM_JSON is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        return {}

    name = str(payload.get("name") or "").strip()
    if not name:
        return {}
    return {name: payload}


def _render_host_line(name: str, vm: dict) -> str:
    ansible_host = vm.get("ipv4_address") or name
    ansible_user = os.getenv("ANSIBLE_REMOTE_USER", "ansible")
    fqdn = _build_fqdn(name, vm)
    return f"{name} ansible_host={ansible_host} ansible_user={ansible_user} vm_fqdn={fqdn}"


def _build_fqdn(name: str, vm: dict) -> str:
    computer_name = vm.get("computer_name") or name
    domain = vm.get("domain")
    if domain:
        return f"{computer_name}.{domain}"
    suffixes = vm.get("dns_suffix_list") or []
    if suffixes:
        return f"{computer_name}.{suffixes[0]}"
    return computer_name


def _split_inventory(lines: list[str]) -> tuple[list[str], list[str]]:
    header_index = None
    for index, line in enumerate(lines):
        if line.strip() == SECTION_HEADER:
            header_index = index
            break

    if header_index is None:
        return lines, []

    prefix = lines[:header_index]
    section = lines[header_index:]
    return prefix, section


def _parse_section(section_lines: list[str]) -> tuple[list[str], dict[str, str], list[str]]:
    if not section_lines:
        return [], {}, []

    header_and_prelude: list[str] = []
    host_lines: dict[str, str] = {}
    tail: list[str] = []

    mode = "header"
    for line in section_lines:
        stripped = line.strip()
        if mode == "header":
            header_and_prelude.append(line)
            if stripped == SECTION_HEADER:
                mode = "hosts"
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            tail.append(line)
            mode = "tail"
            continue

        if mode == "tail":
            tail.append(line)
            continue

        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            header_and_prelude.append(line)
            continue

        host_name = stripped.split()[0]
        host_lines[host_name] = line

    return header_and_prelude, host_lines, tail


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: sync_inventory.py <inventory-file>", file=sys.stderr)
        return 2

    inventory_path = Path(sys.argv[1])
    vm_names = _load_vm_names()
    if not vm_names:
        print("No VM_NAMES provided, inventory sync skipped.")
        return 0

    operation = (os.getenv("VM_OPERATION") or "").strip().lower()
    tfvars_vms = _load_tfvars_vms()
    inventory_sync_vms = _load_inventory_sync_vms()

    original_lines = inventory_path.read_text(encoding="utf-8").splitlines() if inventory_path.exists() else []
    prefix, section = _split_inventory(original_lines)
    header_lines, host_lines, tail = _parse_section(section)

    if not header_lines:
        header_lines = [SECTION_HEADER]

    if operation in {"delete", "destroy"}:
        for name in vm_names:
            host_lines.pop(name, None)
        action = "removed"
    else:
        for name in vm_names:
            vm = tfvars_vms.get(name) or inventory_sync_vms.get(name)
            if vm is None:
                raise SystemExit(f"No inventory sync payload contains VM '{name}', cannot update inventory.")
            host_lines[name] = _render_host_line(name, vm)
        action = "updated"

    rendered_lines: list[str] = []
    rendered_lines.extend(prefix)
    if rendered_lines and rendered_lines[-1].strip():
        rendered_lines.append("")

    rendered_lines.extend(header_lines[:1])
    comment_lines = [line for line in header_lines[1:] if line.strip()]
    rendered_lines.extend(comment_lines)
    rendered_lines.extend(host_lines[name] for name in sorted(host_lines))

    if tail:
        if rendered_lines and rendered_lines[-1].strip():
            rendered_lines.append("")
        rendered_lines.extend(tail)

    inventory_path.write_text("\n".join(rendered_lines).rstrip() + "\n", encoding="utf-8")
    print(f"Inventory {action} for VM(s): {', '.join(vm_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
