# BTScript Technical Specification & Architecture

BTScript is a declarative domain-specific language (DSL) for authoring, verifying, and transpiling **Behavior Trees**.

---

## 1. Compiler Pipeline Architecture

```text
.tree Source Code
       │
       ▼
[ 1. Lexer & Tokens ]        Stream-based scanner tracking exact (file, line, col) spans
       │
       ▼
[ 2. Parser & Desugarer ]    Recursive-descent parser; resolves prefix sugars & fallbacks
       │
       ▼
[ 3. Abstract Syntax Tree ]  Clean dataclass hierarchy (Root, Composites, Leaves, Decorators)
       │
       ▼
[ 4. Semantic Validator ]    Arity checks, type inference, cycle detection, dataflow analysis
       │
       ▼
[ 5. Transpilation Layer ]   Code generation for Python, Lua, XML, JSON, Mermaid, ASCII
       │
       ▼
Target Output & Runtimes     Generates code and bundles runtime engines
```

---

## 2. Core Tree Elements

### Composites (Control Flow)
Composites manage execution order among children and can be configured as **`stateless`** (default) or **`stateful`** (memory):

| Composite | Semantics | Stateful Behavior (`stateful`) |
| :--- | :--- | :--- |
| **`sequence`** | Executes children in order. Succeeds if **all** succeed; fails immediately if **any** child fails. | Remembers running child; resumes directly from running index on next tick. |
| **`selector`** | Fallback priority. Succeeds if **any** child succeeds; fails only if **all** fail. | Remembers running child; does not restart from the first branch on next tick. |
| **`parallel`** | Executes all children concurrently each tick. | Tracks completed children and preserves running states across ticks. |

### Leaves (Execution & Guards)
| Leaf | Return Type | Description |
| :--- | :--- | :--- |
| **`action: Name(...)`** | `Status` or `bool` | Executes domain tasks. Can output results to a blackboard variable via `-> $var`. |
| **`condition: Name(...)`** | `bool` | Evaluates a guard predicate (`SUCCESS` if True, `FAILURE` if False). |
| **`subtree: TreeName(...)`** | `Status` | Invokes another defined behavior tree, passing optional arguments. |

### Decorators
Decorators wrap a single child node to alter its behavior or outcome:
- **`inverter`**: Inverts `SUCCESS` $\leftrightarrow$ `FAILURE` (`RUNNING` passes through).
- **`force_success`**: Converts `FAILURE` to `SUCCESS`.
- **`force_failure`**: Converts `SUCCESS` to `FAILURE`.
- **`repeat(N)`**: Loops execution of the child node $N$ times.
- **`retry(N)`**: Retries the child node up to $N$ times upon failure.
- **`timeout(sec)`**: Fails if the child remains `RUNNING` longer than $N$ seconds.
- **`delay(sec)`**: Returns `RUNNING` until $N$ seconds elapse, then executes child.
- **`cooldown(sec)`**: Prevents execution for $N$ seconds after running.

### Blackboard Memory & Defaults Block
Trees can declare blackboard default variables at the top of the tree body:
```btscript
tree PatrolBot {
    blackboard {
        $speed = 5.5,
        $target = "goblin",
        $aggressive = true,
        $backup = none
    }

    sequence {
        action: findTarget() -> $target
        condition: isAlive($target)
        action: attack($target, $speed)
    }
}
```
- Variables start with `$`.
- Output variables capture action return values: `action: findTarget() -> $target`.
- Context preserves caller-assigned values: defaults only populate if the caller did not already provide values.

---

## 3. Syntactic Sugars

BTScript provides concise shorthand notations that desugar into standard AST nodes during parsing:

### Chained Fallbacks (`|`)
Pipes desugar a sequence of alternatives into a `selector`:
```btscript
// Shorthand:
action: tryPrimary() | action: trySecondary() | action: tryFailsafe()

// Desugars into:
selector {
    action: tryPrimary()
    action: trySecondary()
    action: tryFailsafe()
}
```

### Prefix Decorators
Prefix characters can be placed before actions and conditions:
- `!` or `not` $\rightarrow$ `inverter` (e.g. `!condition: isStunned()`)
- `/` $\rightarrow$ `force_success` (e.g. `/action: playSound()`)
- `\` $\rightarrow$ `force_failure` (e.g. `\action: probe()`)
- `-N` $\rightarrow$ `repeat(N)` (e.g. `-3 action: pulse()`)
- `--N` $\rightarrow$ `retry(N)` (e.g. `--3 action: connect()`)

### Inline Preconditions (`[...]`)
Composites can declare prerequisite conditions inline before the body:
```btscript
sequence [isAlive(), !isStunned()] {
    action: attack()
}
```

---

## 4. Compiler Directives

Directives configure compilation and compiler behavior at file scope:
- **`@lang: <python|lua|json|xml|mermaid|ascii>`**: Sets the default compilation target.
- **`@import: "<path.tree>"`**: Imports external tree definitions with circular-dependency detection.
- **`@enable: <feature>` / `@disable: <feature>`**: Fine-grained compiler toggle:
  - `types`: Enforce consistent argument type inference.
  - `arity`: Enforce consistent parameter arity across identical leaf names.
  - `warnings`: Toggle diagnostic compiler warnings.
  - `werror`: Treat warnings as fatal compilation errors (`-Werror`).
  - `stub`: Enable/disable context stub generation.

---

## 5. Semantic Validation & Diagnostics

The semantic validator ([`Validator`](file:///home/lor7/programming/tree_script/btscript/validator.py)) performs static analysis before transpilation:

1. **Cycle Detection**: Detects circular subtree invocations using depth-first graph traversal.
2. **Arity & Type Signature Checking**:
   - **Arity Rule**: By default (`@enable: arity`), leaf actions and conditions allow overloading with varying argument counts. When `@disable: arity` is specified, overloading is forbidden and all invocations of a leaf must share the exact same parameter count.
   - **Type Rule**: Under `@enable: types` (default), calls sharing the same arity must pass matching literal types (`NUMBER`, `STRING`, `BOOLEAN`). Blackboard variables (`$var`) and raw identifiers act as wildcards to permit dynamic assignments. When `@disable: types` is configured, signature type mismatches are ignored.
3. **Dead-Code Elimination**:
   - Warns about unreachable nodes in sequences following `force_failure`.
   - Warns about unreachable nodes in selectors following `force_success`.
4. **Dataflow & Variable Analysis**:
   - Warns if a blackboard variable is read before being written or declared in defaults.
   - Warns about unused variables (declared or written but never read).
5. **Caret Diagnostics**:
   Prints colorized source-mapped lines with caret pointers:
   ```text
   Semantic Error in patrol.tree:14:12:
     14 |     action: attack($enemy, 50, true)
        |             ^^^^^^
   Action 'attack' called with 3 arguments, but previously called with 2 arguments.
   ```

---

## 6. Transpilation Targets

| Target | Transpiler Class | Output Description |
| :--- | :--- | :--- |
| **Python** | `PyTranspiler` | Pure OOP class implementations, delta-time `dt` tick loop, auto-generated `ContextStub` interfaces with mock factories (`create_mock()`). |
| **Lua** | `LuaTranspiler` | Metatable-based OOP tables, delta-time `dt` simulation, auto-generated `ContextStub` interfaces with `new_mock()`. |
| **XML** | `XMLTranspiler` | Clean XML tree schema with subtrees, stateful memory tags, and blackboard attributes. |
| **JSON** | `JSONTranspiler` | Structured AST serialization for custom tools, editors, and web visualizers. |
| **Mermaid** | `MermaidTranspiler` | Visual Markdown flowcharts with stateful badges and blackboard annotations. |
| **ASCII** | `AsciiTranspiler` | Terminal branch visualization with tree connectors (`├── `, `└── `). |

---

## 7. Simulation Time (Delta Time `dt`)

Both Python and Lua runtimes support decoupled simulation time:
```python
# Realtime execution (relies on monotonic clock)
tree.tick(ctx)

# Simulation / Game Engine loop (relies on explicit delta time)
tree.tick(ctx, dt = 0.016)
```
Time-based decorators (`timeout`, `delay`, `cooldown`) automatically calculate durations using `dt` when passed, making tests fast and deterministic without calling `time.sleep()`.

---

## 8. Editor Support: VS Code Extension

BTScript provides an official TextMate extension for Visual Studio Code, VSCodium, and Cursor (`editors/vscode-btscript`):
- **Full Syntax Highlighting**: Tree keywords, composites, leaf actions/conditions, decorators, directives, blackboard tokens (`$var`), and syntactic sugars.
- **Typo Warnings**: Highlights mistyped directives (`@enabled`, `@disabled`) as syntax errors directly in the editor.
- **Brackets & Formatting**: Auto-closing quotes, matched braces, and automatic indentation rules for Behavior Tree nesting.
- **Automated Installation**: Run `bts --install-vscode` or `python3 scripts/install_vscode.py` to copy into `~/.vscode/extensions/vscode-btscript`.

