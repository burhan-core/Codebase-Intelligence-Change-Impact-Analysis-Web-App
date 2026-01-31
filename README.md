# Codebase Intelligence & Change Impact Analysis

> **Understand what breaks before you change code.**

A developer-focused **static analysis tool** designed to map dependencies and visualize change impact in large codebases. Stop guessing—see exactly what is affected by a change and why, without executing a single line of code.

---

## Interface

<table>
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="https://github.com/user-attachments/assets/30619e81-e7ef-41f4-88d0-f9177b715068" alt="Initial View" width="100%">
      <br>
      <em>Figure 1: Initial Codebase Exploration</em>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="https://github.com/user-attachments/assets/f59d4f33-12d6-465d-a13e-b1c64af8d462" alt="Impact View" width="100%">
      <br>
      <em>Figure 2: Visualizing Change Impact Paths</em>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
        <br>
        <img src="https://github.com/user-attachments/assets/56b09a91-d149-4fca-876c-fbc1d059c1a3" alt="Sidebar Detail" width="350">
        <br>
        <em>Detail View: List of Impacted Files</em>
    </td>
  </tr>
</table>

---

## Key Features

* **Deep Dependency Mapping:** Visualize how files and functions depend on each other across the entire repository.
* **Downstream Impact Tracing:** Instantly see the "blast radius" of changing a specific function or file.
* **Risk Detection:** Reveal hidden coupling and high-risk areas before they cause regressions.
* **Explainable Insights:** Get deterministic explanations for *why* a change affects specific parts of the system.

---

## How It Works

This tool prioritizes **static analysis over heuristics** and **safety over guesswork**.

1. **Parses:** Source code is analyzed using Abstract Syntax Trees (AST).
2. **Models:** A comprehensive dependency graph is built connecting every file and function.
3. **Traverses:** The engine traverses these links to compute the exact impact path of any change.
4. **Visualizes:** Results are presented in a clean, read-only UI.

> **Note:** No code is executed. No AI is required for correctness.

---

## The User Experience

Designed for engineers working with real, non-trivial codebases.

* **IDE-Style Explorer:** Familiar file navigation.
* **Code Viewer:** Read-only interface with line numbers for context.
* **Impact Dashboard:** A clear list of all affected files and functions.

---

## Tech Stack

* **Frontend:** React, Tailwind CSS, Monaco Editor
* **Backend:** Python, FastAPI, Custom AST Parsing
* **Core:** Graph-based dependency algorithms

---

## Project Status

**Actively in development.**
