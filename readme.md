# BTScript

> **A clean, expressive, and verifiable Behavior Tree domain-specific language.**

---

## Project Description

**BTScript** is a domain-specific language (DSL) and compiler toolkit engineered specifically for authoring, verifying, and deploying **Behavior Trees** in games, simulations, and robotics.

Behavior Trees are the de-facto industry standard for modeling autonomous decision-making agents. However, traditional authoring workflows force developers to choose between three flawed compromises:
1. **Imperative Boilerplate**: Building trees directly in code (C++, Python, C#) obscures the tree's logical hierarchy, makes rapid prototyping tedious, and clutters game logic with structural mechanics.
2. **Visual Graph Files**: Node-based graph editors output large binary blobs or noisy XML documents that cause merge conflicts in version control and cannot be reviewed in code pull requests.
3. **Unvalidated Config Files**: Handcrafted JSON or XML configuration formats lack compile-time validation, deferring missing-argument, dead-code, and type-mismatch bugs to runtime crashes.

**BTScript eliminates these compromises:**
- **Human-First Syntax**: Offers a clean, indented DSL with intuitive primitives (`sequence`, `selector`, `action`, `condition`, `decorator`), stateful memory keywords, and expressive syntactic shorthands.
- **Deep Compile-Time Verification**: Runs rigorous static analysis before any code is generated—detecting recursive subtree cycles, dead code, arity mismatches, type conflicts, and uninitialized blackboard variables.
- **Multi-Target Transpilation**: Author once in BTScript, compile directly to clean, idiomatic **Python**, **Lua**, **Rust**, **XML**, **JSON AST**, **Mermaid flowcharts**, or terminal **ASCII** trees.
- **Zero Runtime Dependencies**: The compiler runs entirely on standard Python (>= 3.10) with zero external dependencies.
- **Simulation-Ready**: Built-in Python, Lua, and Rust runtime engines support decoupled simulation time (`dt`) for deterministic game loops and headless unit testing.
- **Editor Tooling**: Official VS Code extension (`vscode-btscript`) with TextMate syntax highlighting, bracket matching, and error checking.

---

## A Quick Look

```btscript
tree GuardBot {
    blackboard { $speed = 4.0, $target = "none" }

    selector {
        // Combat: engage when enemy acquired
        sequence [hasEnemy($target)] {
            action: faceTarget($target)
            action: attackTarget($target)
        }

        // Search: acquire target and alert squad
        sequence {
            action: findEnemy("player") -> $target
            action: alertSquad($target)
        }

        // Patrol: roam perimeter and scan
        sequence {
            action: walkWaypoints($speed)
            decorator: delay(1.5) { action: scanArea() }
        }
    }
}
```

---

## Quickstart & CLI Guide

### 1. Installation

Install directly from GitHub via `pip`:
```bash
pip install git+https://github.com/lor7/btscript.git
```

Or clone and run locally from source:
```bash
git clone https://github.com/lor7/btscript.git
cd btscript
```

### 2. Transpile to Your Engine

```bash
# Transpile to Python (automatically bundles runtime.py)
bts examples/02_selectors.tree -l python -o guard.py

# Transpile to Lua (automatically bundles runtime.lua)
bts examples/02_selectors.tree -l lua -o guard.lua

# Export to clean XML tree schema
bts examples/02_selectors.tree -l xml -o guard.xml

# Export to Mermaid flowchart (.mmd)
bts examples/02_selectors.tree -l mermaid -o guard.mmd

# Export to structured JSON AST
bts examples/02_selectors.tree -l json -o guard.json
```

### 3. Terminal ASCII Visualization

Visualizing your tree in the terminal does **not** create or leave any files on disk:
```bash
bts examples/02_selectors.tree -l ascii
```
*(If you do want to save the ASCII tree to a file, pass `-o filename.txt` or declare `@lang: ascii` in the file directives).*

### 4. Dry-Run & Semantic Verification Mode (`-c` / `--check`)

BTScript includes a dedicated **dry-run mode** that parses and validates your tree without generating output files:

```bash
# Verify syntax, subtree cycles, arity, and dataflow
bts examples/02_selectors.tree -c
# or:
python3 -m btscript examples/02_selectors.tree --check

# Strict mode: treat compiler warnings as fatal errors
bts examples/02_selectors.tree -c -Werror
```
Dry-run mode exits with code `0` on success and non-zero on error, making it ideal for Git pre-commit hooks and CI/CD pipelines.

---

## BTScript Language Support (VS Code Extension)

BTScript includes a dedicated **VS Code Extension** (`vscode-btscript`) providing full editor language support for `.tree` files:

- **Syntax Highlighting**: Distinct coloration for composites (`sequence`, `selector`, `parallel`), leaves (`action`, `condition`), decorator properties (`repeat`, `retry`, `timeout`, `delay`, `cooldown`, etc.), blackboard variables (`$target`), compiler directives (`@lang`, `@import`, `@enable`, etc.), and literals.
- **Syntactic Sugar Tokenization**: Full color support for prefix sugars (`!`, `/`, `\`), chained fallbacks (`|`), and repeat counts (`-4`, `--2`).
- **Typo & Error Detection**: Highlights invalid directives like `@enabled` or `@disabled` in red as syntax errors.
- **Editor Ergonomics**: Automatic bracket matching (`{}`, `[]`, `()`), quote closing (`""`), comment toggling (`Ctrl+/` for `//`), and smart indentation rules.

### Installing the VS Code Extension

You can install the extension directly into your editor with a single command:

```bash
# Using the CLI entrypoint
bts --install-vscode

# Or using the standalone script directly
python3 scripts/install_vscode.py
```

The script automatically detects and copies the extension into your editor's extensions directory (`~/.vscode/extensions/vscode-btscript`, as well as VSCodium or Cursor if detected). Once installed, run **Developer: Reload Window** (`Ctrl+Shift+P`) or restart your editor.

---

## Python API

You can embed BTScript directly into your Python build scripts and asset pipelines:

```python
from btscript import Parser, Validator, Transpiler, Status

# 1. Parse .tree file into AST
ast, directives = Parser("examples/02_selectors.tree").parse_file()

# 2. Run semantic and dataflow validation
validator = Validator(ast, directives)
validator.validate()

# 3. Transpile to desired output format
transpiler = Transpiler(ast, lang = "python", directive = directives)
code = transpiler.transpile()
```

---

## Documentation & References

- **[User Guide (`user_guide.md`)](user_guide.md)**: A complete walkthrough of language features (Arbor I – VII), stateful vs stateless memory, blackboard dataflow, syntactic sugars, Python/Lua/Rust runtime integration, and dry-run verification.
- **[Technical Specification (`features.md`)](features.md)**: In-depth technical architecture, AST node definitions, desugaring transformation rules, cycle detection algorithms, and validator diagnostics.

---

## Author & License

- **Author**: Developed by Lorenzo (Lor7).
- **License**: [MIT License](LICENSE). Free for personal and commercial use with attribution.
