# III–V Laser Research Workbench

**A lightweight starting point for linking semiconductor-laser research records across analysis tools.**

Status: **early scaffold**. Python 3.11+, standard library only; no installation,
server or instrument required. 

This project connects the direction of three tools already used in laboratory
work: [PL-Analyzer](https://github.com/SpikeHS/PL-Analyzer),
[laser-beam-qa](https://github.com/SpikeHS/laser-beam-qa) and
[laser-characterization-tools](https://github.com/SpikeHS/laser-characterization-tools).

[中文说明](README.zh-CN.md) · [Roadmap](ROADMAP.md)

## Run the example

```sh
python workbench.py check examples/project.json
python workbench.py report examples/project.json --out runs/demo.html
python -m unittest discover -s tests -v
```

Open `runs/demo.html`. Choose a new output path on subsequent runs; reports never
overwrite existing files. The demo links wafer-level PL and device-level beam,
spectral and LIV records. **All four result files are explicitly hand-authored
synthetic placeholders, not output from the analysis tools or measured data.**

## What works now

- A versioned manifest with explicit wafer/specimen/device relationships.
- Links to local JSON results, labeled as synthetic, simulated or measured.
- Checks for duplicate IDs, missing references, parent cycles and missing files.
- Result-file SHA-256 hashes and an HTML report preserving the original JSON fields.
- Portable relative paths constrained to the project folder; escaped report text.

The manifest is edited manually. Conditions are supplied by the user; missing
values are unknown. The loader checks structure and file references, not source
schema compatibility, units, calibration, scientific validity or comparability.
It does not infer measurement relationships or calculate new scientific metrics.

## Connect your own results

Copy the example project to a local folder. Add entities and explicitly assign
each measurement's `entity_id`. Set `modality` to `pl`, `beam`, `spectrum` or `liv`,
and accurately set `data_kind`. Put each result JSON under that folder and
reference it with `source`; record applicable conditions in `conditions`.
This displays the source payload as supplied, without interpreting its format.
Dedicated, version-aware adapters for the three tools are planned.

PL-Analyzer publishes its full application source; the other two public projects
extract reusable functionality with research-specific presets and experimental
setup removed. Their licenses remain independent. This repository contains its
own integration scaffold and synthetic placeholders, not copies of their code.

MIT © 2026 Sen Hu. Developed with Codex assistance. Scientific interpretation
and validation remain the user's responsibility. See [contributing](CONTRIBUTING.md).
