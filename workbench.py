"""Minimal local manifest validator and report builder. Python 3.11+, standard library."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def invalid(value):
        raise ValueError(f"Nonfinite JSON number: {value}")
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=invalid)


def unique_records(records, label):
    require(isinstance(records, list) and records, f"{label} must be a nonempty list")
    result = {}
    for record in records:
        require(isinstance(record, dict), f"Invalid {label} record")
        key = record.get("id")
        require(isinstance(key, str) and key.strip(), f"Missing {label} id")
        require(key not in result, f"Duplicate {label} id: {key}")
        result[key] = record
    return result


def load_project(path):
    path = Path(path).resolve()
    project = read_json(path)
    require(isinstance(project, dict), "Project must be an object")
    require(type(project.get("schema_version")) is int and project["schema_version"] == 1,
            "Supported project schema_version: 1")
    require(isinstance(project.get("title"), str) and project["title"].strip(), "Missing title")
    entities = unique_records(project.get("entities"), "entity")
    for key, entity in entities.items():
        require(entity.get("kind") in {"growth_run", "wafer", "specimen", "device"},
                f"Unknown entity kind: {key}")
        visited = set()
        current = key
        while current is not None:
            require(isinstance(current, str) and current in entities, f"Unknown parent of {key}")
            require(current not in visited, f"Parent cycle: {key}")
            visited.add(current)
            current = entities[current].get("parent_id")
    measurements = unique_records(project.get("measurements"), "measurement")
    snapshots = []
    for key, record in measurements.items():
        entity_id = record.get("entity_id")
        require(isinstance(entity_id, str) and entity_id in entities, f"Unknown entity: {key}")
        require(record.get("modality") in {"pl", "beam", "spectrum", "liv"}, f"Unknown modality: {key}")
        require(record.get("data_kind") in {"synthetic", "simulated", "measured"}, f"Missing data kind: {key}")
        require(isinstance(record.get("conditions"), dict), f"conditions must be an object: {key}")
        relative = record.get("source")
        require(isinstance(relative, str) and relative, f"Missing source: {key}")
        require(not Path(relative).is_absolute(), f"Source must be relative: {key}")
        source = (path.parent / relative).resolve()
        require(source.is_relative_to(path.parent), f"Source escapes project folder: {key}")
        require(source.is_file() and source.suffix.lower() == ".json", f"Missing JSON source: {key}")
        payload = read_json(source)
        snapshots.append((record, payload, hashlib.sha256(source.read_bytes()).hexdigest()))
    return project, snapshots


def render_report(project, snapshots):
    escape = html.escape
    rows = "".join(
        f"<tr><td>{escape(e['id'])}</td><td>{escape(e['kind'])}</td>"
        f"<td>{escape(e.get('parent_id') or '—')}</td></tr>" for e in project["entities"]
    )
    cards = []
    for record, payload, digest in snapshots:
        conditions = json.dumps(record["conditions"], ensure_ascii=False, indent=2)
        cards.append(
            f"<section><h2>{escape(record['id'])} · {escape(record['modality'])}</h2>"
            f"<p>Entity: <b>{escape(record['entity_id'])}</b> · Data: <b>{escape(record['data_kind'])}</b></p>"
            f"<p>Source: {escape(record['source'])}</p><p class='hash'>Result-file SHA-256: {digest}</p>"
            f"<h3>Declared conditions</h3><pre>{escape(conditions)}</pre>"
            f"<details open><summary>Source result (original field meanings)</summary>"
            f"<pre>{escape(json.dumps(payload, ensure_ascii=False, indent=2))}</pre></details></section>"
        )
    title = escape(project["title"])
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#183349;background:#f5f8fa}}
section,table{{background:white;padding:20px;border:1px solid #dce4ea;margin:20px 0;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #dce4ea}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f6;padding:14px}}.hash{{font-size:12px;overflow-wrap:anywhere}}</style>
<h1>{title}</h1><p>III–V Laser Research Workbench · manifest prototype</p>
<p>Relationships and conditions are supplied by the user. Missing conditions are unknown.
This report preserves source results; it does not validate scientific methods or infer comparable measurements.</p>
<table><tr><th>Entity</th><th>Type</th><th>Parent</th></tr>{rows}</table>{''.join(cards)}</html>"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "report"])
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        project, snapshots = load_project(args.project)
        if args.command == "report":
            require(args.out is not None, "report requires --out")
            report = render_report(project, snapshots)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(report)
            print(f"Created {args.out}")
        else:
            print(f"OK: {len(project['entities'])} entities, {len(snapshots)} linked result files")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
