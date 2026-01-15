# Codebase Intelligence & Change Impact Analysis

> Understand what breaks before you change code.

A developer-focused **static analysis tool** for understanding **dependencies and change impact** in large codebases.

It helps engineers see **what is affected by a change and why**, before modifying code — without executing anything and without relying on guesses.

---

## What This Tool Does

This tool analyzes a repository and builds a structural model of the codebase.  
From that model, it can:

- Show which files and functions depend on each other
- Trace the downstream impact of changing a function or file
- Reveal hidden coupling and risky areas in the code
- Explain *why* a change affects specific parts of the system

All results are **deterministic and explainable**.

---

## How It Works (High Level)

- Parses source code using static analysis (AST)
- Builds a dependency graph between files and functions
- Traverses dependencies to compute change impact
- Presents impact paths clearly in the UI

No code is executed. No AI is required for correctness.

---

## User Experience

- IDE-style file explorer
- Read-only code viewer with line numbers
- Impact view listing affected files and functions

Designed for engineers working with real, non-trivial codebases.

---

## Core Principles

- Static analysis over heuristics  
- Explainability over black-box results  
- Safety and read-only access by default  

Not included:
- Code execution
- Code generation
- Prompt-based logic

---

## Tech Stack (Brief)

- Frontend: React, Tailwind, Monaco Editor
- Backend: Python, AST parsing, FastAPI
- Data: Dependency graphs

---

## Project Status

Actively in development.

