# SPEAR Methodology Reference

## Core Acronym

- **S**ystematic - Follow hierarchy from resource boundary to business code
- **P**erformance - Focus on high-load, low-frequency sampling scenarios
- **E**mpirical - Tool-driven, no logical guessing without physical evidence
- **A**nalysis - Multi-dimensional correlation with expert rule base
- **R**eflection - Self-critical mechanism against confirmation bias

## Methodology: Instrumented Reflection

### Cognitive Closures Required

1. **Empirical Anchoring**
   - **Principle**: No logical deduction without tool data
   - **Requirement**: Every hypothesis must be followed by a probing action

2. **Competing Hypotheses**
   - **Principle**: Maintain "dual-line thinking"
   - **Example**: Slowdown due to inefficient business logic (active) vs scheduling/resource throttling (passive)

3. **Search Space Convergence**
   - **Principle**: Funnel model - determine ceiling first, then main road, then local

4. **Causal Cross-Validation**
   - **Principle**: Evidence must form chains
   - **Example**: Lock contention in business layer must correlate with scheduling delays in system layer

5. **Falsification**
   - **Principle**: Before final conclusion, audit evidence chain
   - **Question**: "Is the problem solved? Are there other possibilities?"

## Domain Rules Detail

### Process-Level Diagnostic Criteria

| Rule | Description | Priority |
|------|-------------|----------|
| Resource Boundary Suppression | Analyze Cgroup specs and throttling metrics first | **#1** |
| Full-Path Audit | Use inclusive stats for stability, ignore single-point noise | High |
| Foundation Library Aggregation | Identify common utilities (memcpy, malloc) - indicates data processing pattern issues | Medium |
| User-Space Sync Loss | Monitor synchronization primitive ratios for lock contention | Medium |
| Process Lifecycle Anomaly | High PID variety with low samples per PID indicates process storm | High |

### System-Level Diagnostic Criteria

| Rule | Description | Indicator |
|------|-------------|-----------|
| Interrupt & Scheduling Latency | Kernel long critical zones | `spin_unlock_irqrestore` patterns |
| Kernel Global Aggregation | Cross-process kernel overhead aggregation | All participants affected |
| Scheduler Efficiency | Scheduler internal function overhead | >10% indicates system overload |
| Architecture & Memory Bottlenecks | Memory Direct Reclaim and TLB sync | Micro-burst jitter detection |

## Detailed Workflow

### Step 1: Problem Definition

Enumerate all possible paths based on domain knowledge. Initialize Path Tracking Assessment Table. **Minimum 3 paths required** to avoid narrow search scope.

### Step 2: Environment Scoping

**Goal**: Determine physical limits

**Method**: Use tools to obtain Cgroup status and CPU core load distribution

**Key Question**: "Running too fast hitting ceiling" or "road itself is bumpy"

### Step 3: Macro Hotpath

**Goal**: Lock business traffic trunk

**Method**: Full-path perspective analysis of hotspot distribution

**Output**: TopN statistically confident paths, filtered for low-frequency noise

### Step 4: Semantic Clustering

**Goal**: Transform data to business language

**Method**: Cluster discrete function symbols by expert rules (scheduling, locks, memory)

**Output**: Determine optimization level (application vs system)

### Step 5: Micro Attribution

**Goal**: Complete evidence chain

**Method**: Bottom-up reverse trace of identified hotspots

**Output**: Map system overhead to specific business code lines

### Step 6: Global Consistency Audit

**Goal**: Final validation

**Method**: Backtrack all historical information, assess if conclusion explains all anomalies

**Action**: If unexplained evidence exists, reset process and update problem definition

## Behavioral Pattern Analysis

- Process Storm Detection

---

## Tool Usage Principles

1. **Tool Mandate**: No "naked guessing". Every analysis must start with "According to tool detection results..."
2. **Scoping Rigor**: No jumping from Stage 1 to Stage 4. Follow environment-to-code path strictly.
3. **Reliability Threshold**: For 19Hz sampling, verify sample totals. Label as "speculation" below confidence threshold.
4. **Exclusion-First**: Prioritize evidence that eliminates search domains over evidence supporting hypotheses.
