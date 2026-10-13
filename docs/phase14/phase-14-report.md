# Phase 14 Report — Automated Experiment Framework

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04.1 LTS, kernel 7.0.0-38-generic

---

## 1. Objective

Wrap the manual experiments from Phases 6, 7, 8, and 11 into a
single reproducible framework. Every experiment must be:

- Declared in a manifest (not hard-coded in shell)
- Executable with one command
- Captured with timestamps, metadata, stdout, stderr, and artifacts
- Filterable by name, category, or tag
- Reproducible from a clean checkout

---

## 2. Design

### 2.1 Manifest Format

Experiments are declared in YAML:

    experiments/manifests/experiments.yaml

Each entry has:

| Field | Purpose |
|-------|---------|
| name | unique identifier |
| description | one-line summary |
| category | grouping (baseline / slicing / resilience) |
| duration_s | expected runtime |
| command | shell command (executed with bash -lc) |
| artifacts | files to preserve after the run |
| depends_on | prerequisite experiments |
| tags | keywords for filtering |

### 2.2 Orchestrator

The runner is a single Python script:

    scripts/phase14/run_experiment.py

Behavior:

- Reads the YAML manifest
- Selects experiments by name, category, or tag
- Creates a timestamped output directory per experiment
- Executes the command with `subprocess.run`
- Writes metadata.yaml, stdout.log, stderr.log
- Copies declared artifacts into the output directory
- Prints a summary at the end

Output layout:

    experiments/results/<name>/<timestamp>/
        metadata.yaml
        stdout.log
        stderr.log
        artifacts/

### 2.3 CLI

| Flag | Purpose |
|------|---------|
| --manifest | path to the YAML manifest (required) |
| --list | print experiments and exit |
| --only NAME | run one experiment |
| --category CAT | run all in a category |
| --tag TAG | run all with a tag |
| --dry-run | print what would run |

---

## 3. Registered Experiments

| Name | Category | Duration | Source Phase |
|------|----------|----------|--------------|
| stack-health | baseline | 5s | new |
| slice-baseline | slicing | 95s | Phase 6 |
| slice-treatment | slicing | 95s | Phase 6 |
| fault-app-failure | resilience | 60s | Phase 11 F01 |
| fault-ue-route-blackhole | resilience | 40s | Phase 11 F05 |
| fault-upf-edge-stop | resilience | 75s | Phase 11 F06 |

The commands call the existing per-phase runner scripts. This
framework does not replace them; it orchestrates and archives them.

---

## 4. Verification

### 4.1 List Mode

    python3 run_experiment.py --manifest experiments.yaml --list

Output: 6 experiments, correctly grouped.

### 4.2 Category Filters

| Filter | Result |
|--------|--------|
| --category baseline | 1 (stack-health) |
| --category slicing | 2 (slice-baseline, slice-treatment) |
| --category resilience | 3 (fault experiments) |
| --tag fault-injection | 3 (fault experiments) |

### 4.3 Live Run

The `stack-health` experiment was executed live:

    python3 run_experiment.py --manifest ... --only stack-health

Result:

    duration_actual_s: 0.2
    status: ok
    artifacts_copied: []

Output directory: `experiments/results/stack-health/20261013-212055/`

Contains:

- metadata.yaml — with name, description, category, command,
  started_at, finished_at, duration, status
- stdout.log — the exact snapshot
- stderr.log — empty

The stdout captured:

    CU:  1
    DU:  1
    UE:  2
    RIC: 1

    oaitun_ue1   UNKNOWN  10.45.0.2/24
    oaitun_ue1p2 UNKNOWN  10.46.0.2/24

    sctp  ESTAB  127.0.0.1:45787 -> 127.0.0.1:36421  users:(("odu"))

    open5gs-upfd        active
    open5gs-upfd-edge   active

This is the same information an operator would capture by hand; the
framework makes it reproducible, timestamped, and archived.

---

## 5. Reproducibility Gains

| Before Phase 14 | After Phase 14 |
|-----------------|----------------|
| Manual shell commands typed per phase | Declared in YAML manifest |
| Results scattered in phase directories | Uniform archive layout per run |
| No consistent metadata | Every run has started_at, duration, status |
| Hard to re-run a specific experiment | One flag: --only NAME |
| Filtering by keyword impossible | Filter by name, category, or tag |

For the thesis, this means the evaluation chapter can state:
"The experiments are declared in a manifest and can be re-executed
with `python3 run_experiment.py --only <name>`."

---

## 6. Limitations

1. **Single-host execution.** The orchestrator runs experiments on
   the local machine. It does not distribute across nodes.

2. **No dependency enforcement.** The `depends_on` field is recorded
   in metadata but not enforced. Running `slice-treatment` without
   `stack-health` first will still proceed.

3. **No scheduling.** Experiments run sequentially in manifest order.
   Parallel execution is not implemented.

4. **No failure retry.** A failed experiment is recorded as failed and
   the loop continues. There is no automatic retry policy.

5. **Only 6 experiments registered.** Phase 6's full matrix (18 trials),
   Phase 8's load sweep, and Phase 11's remaining faults are not in the
   manifest. Adding them would be mechanical but was not necessary for
   this phase.

6. **Artifact globbing is shallow.** Only files directly matched by the
   pattern are copied; nested directories are not recursively gathered.

---

## 7. Files Produced

### 7.1 Framework

    scripts/phase14/run_experiment.py       — orchestrator
    experiments/manifests/experiments.yaml  — manifest

### 7.2 First Run

    experiments/results/stack-health/20261013-212055/
        metadata.yaml
        stdout.log
        stderr.log

---

## 8. Conclusion

Phase 14 converted the project's manual experiment workflows into a
declarative, reproducible framework. Six experiments are registered
across three categories. The framework has been verified end-to-end
with a live stack-health run.

The design keeps phase-specific runners in place and adds a thin
orchestration layer on top. This means existing documentation and
previous phase reports remain valid; the manifest simply adds a
uniform way to execute and archive experiments.

This establishes the infrastructure required by the thesis's
"Reproducibility" chapter (Phase 24).

---

**End of Phase 14 Report**
