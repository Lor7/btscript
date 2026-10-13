# BTScript

> **A clean, expressive, and verifiable Behavior Tree domain-specific language.**

BTScript brings modern programming language ergonomics to **Behavior Trees**. Designed for game developers, roboticists, and AI designers who want to write, review, and version-control behavior trees with clear syntax and compile-time verification instead of dealing with clumsy XML, bulky visual node files, or sprawling imperative boilerplate.

---

## Why BTScript?

Behavior Trees are the industry standard for modeling autonomous decision-making in games, simulation, and robotics. However, common authoring workflows present recurring challenges:
- **Imperative Code**: Verbose to construct by hand, hard to visualize at a glance, and clutters game logic with structural boilerplate.
- **Visual Node Graphs**: Save as huge binary files or unstructured XML, leading to painful Git merge conflicts.
- **Handwritten XML**: Lack compile-time checks, resulting in subtle runtime bugs when arguments, types, or variable names change.

**BTScript bridges this gap:**
- **Human-Readable DSL**: Express sequences, fallbacks, decorators, and dataflow in clean, indented code.
- **Compile-Time Static Analysis**: Catches recursion cycles, dead code, arity mismatches, and uninitialized blackboard variables before code runs.
- **Multi-Target Transpilation**: Compile once to **Python**, **Lua**, **XML**, **JSON AST**, **Mermaid flowcharts**, or terminal **ASCII** trees.
- **Zero Runtime Dependencies**: The compiler runs entirely on standard Python (>= 3.10) without third-party dependencies.
- **Decoupled Simulation Time**: Built-in runtime support for fixed delta-time (`dt`) simulation and tick loops.

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

### 2. Verify Trees (`-c` / `--check`)

Run semantic static analysis and structural checks without generating files:
```bash
bts examples/02_selectors.tree -c
# or:
python3 -m btscript examples/02_selectors.tree -c
```

### 3. Transpile to Your Engine

```bash
# Transpile to Python (bundles runtime.py automatically)
bts examples/02_selectors.tree -l python -o guard.py

# Transpile to Lua (bundles runtime.lua automatically)
bts examples/02_selectors.tree -l lua -o guard.lua

# Export to XML schema
bts examples/02_selectors.tree -l xml -o guard.xml

# Visualize directly in terminal (ASCII branch tree)
bts examples/02_selectors.tree -l ascii

# Export to Mermaid flowchart (.mmd)
bts examples/02_selectors.tree -l mermaid -o guard.mmd

# Export to structured JSON AST
bts examples/02_selectors.tree -l json -o guard.json
```

### 4. Install VS Code Extension

BTScript provides an official **VS Code extension** (`vscode-btscript`) with full syntax highlighting, bracket matching, and error checking for `.tree` files:
```bash
bts --install-vscode
# or:
python3 scripts/install_vscode.py
```
After running the command, reload your editor window (**Developer: Reload Window**) or restart VS Code!

---

## Language Tour: Core Concepts

A structured walkthrough of BTScript syntax and behavior tree composition, progressing from fundamental primitives to modular multi-file architectures.

### Arbor I: Primitive Trees (Sequences & Actions)

The most basic tree consists of a named `tree` block containing a composite (`sequence`) and leaf tasks (`action`):

```btscript
tree HelloBot {
    sequence {
        action: sayHello()
        action: wanderAround()
    }
}
```

- **`tree Name { ... }`**: Defines a behavior tree.
- **`sequence { ... }`**: Executes its children from top to bottom. If any child returns `FAILURE`, the sequence aborts immediately and returns `FAILURE`. If all children return `SUCCESS`, the sequence succeeds.
- **`action: name(args...)`**: Executes an action method provided by your game or agent context.

---

### Arbor II: Decision Flow (Selectors & Conditions)

Autonomous agents make decisions using fallbacks (`selector`) gated by checks (`condition`):

```btscript
tree GuardBot {
    selector {
        // High priority: if enemy is in range, attack!
        sequence {
            condition: isEnemyVisible()
            condition: isEnemyInRange(10.0)
            action: attackEnemy()
        }

        // Fallback: patrol the perimeter
        action: patrolWaypoints()
    }
}
```

- **`selector { ... }`**: Tries each child in order. If a child succeeds or is running, the selector stops and returns that status. It only falls back to the next child if the current one fails.
- **`condition: name(args...)`**: Checks a boolean predicate. Returns `SUCCESS` if true, `FAILURE` if false.

---

### Arbor III: Execution Modifiers (Decorators & Stateful Memory)

Decorators wrap a single child node to modify its execution behavior.

```btscript
tree PatrolBot {
    stateful sequence {
        // Retry locating target up to 3 times
        decorator: retry(3) {
            action: findTarget()
        }

        // Pause for 2.5 seconds before moving
        decorator: delay(2.5) {
            action: scanArea()
        }

        // Invert condition outcome (SUCCESS becomes FAILURE and vice-versa)
        decorator: inverter {
            condition: isLowHealth()
        }

        // Loop patrol steps 5 times
        decorator: repeat(5) {
            action: walkNextWaypoint()
        }
    }
}
```

#### Available Built-in Decorators:
- `inverter`: Inverts child status (`SUCCESS` <-> `FAILURE`, `RUNNING` stays `RUNNING`).
- `force_success`: Always returns `SUCCESS`, regardless of child outcome.
- `force_failure`: Always returns `FAILURE`, regardless of child outcome.
- `repeat(N)`: Ticks child repeatedly until it runs `N` times (or succeeds/fails depending on semantics).
- `retry(N)`: Retries child on `FAILURE` up to `N` times before failing.
- `timeout(seconds)`: Fails if the child stays in `RUNNING` longer than the given duration.
- `delay(seconds)`: Delays child execution by a given duration.
- `cooldown(seconds)`: Enforces a minimum cooldown period before the child can be re-executed.

#### Stateful vs Stateless Memory:
By default, composites are **stateless** (they re-evaluate from the first child on every tick). Adding `stateful` remembers which child was `RUNNING` and resumes execution from that child on the subsequent tick:
```btscript
stateful sequence { ... }
stateful selector { ... }
```

---

### Arbor IV: Dataflow (Blackboard & Parameters)

Blackboards allow nodes to share dynamic state (e.g. coordinates, targets, speeds). You can declare default blackboard values and pass parameters into trees:

```btscript
tree CombatAI(patrolSpeed = 3.5, maxChaseDistance = 50.0) {
    blackboard {
        $target = none,
        $targetVisible = false
    }

    sequence {
        // Output arrow (->) writes the action's return value to the blackboard
        action: scanForPlayer(maxChaseDistance) -> $target

        // Reading blackboard variables using $ prefix
        condition: hasTarget($target)
        condition: isTargetVisible($targetVisible)
        action: chaseTarget($target, patrolSpeed)
    }
}
```

- **Tree Parameters**: `tree Name(param1, param2 = default)` allows parameterized tree instances.
- **Blackboard Block**: `blackboard { $varName = defaultValue, ... }` initializes shared keys.
- **Reading Variables**: Pass `$varName` as an argument to any action or condition.
- **Writing Variables (`->`)**: Append `-> $varName` to assign an action's return value directly into the blackboard.
- **Static Verification**: BTScript's compiler detects if a variable is read before being written or declared, and flags unused variables.

---

### Arbor V: Architecture & Modularity (Subtrees & Imports)

Break large AI systems into clean, reusable modules using `subtree:` and `@import:`:

```btscript
// combat.tree
tree CombatSubtree(targetEnemy) {
    sequence {
        action: aimAt(targetEnemy)
        action: fireWeapon(targetEnemy)
    }
}
```

```btscript
// main.tree
@import: "combat.tree"

tree MainAgent {
    blackboard {
        $enemy = none
    }

    selector {
        sequence {
            action: detectEnemy() -> $enemy
            // Invoke modular subtree with arguments
            subtree: CombatSubtree($enemy)
        }
        action: idle()
    }
}
```

- **`@import: "path/to/file.tree"`**: Pulls in external trees. Imports are tracked to prevent circular inclusion.
- **`subtree: SubtreeName(args...)`**: Instantiates and executes a child tree. The compiler validates argument counts and checks the call graph for circular invocation cycles.

---

### Arbor VI: Expressive Shorthands (Syntactic Sugar)

BTScript includes expressive syntactic sugars that eliminate nesting boilerplate:

#### 1. Inline Preconditions (`[...]`)
Gate a sequence or selector with condition checks on the same line:
```btscript
// Desugars into a sequence containing condition checks followed by actions
sequence [isArmed(), hasAmmo(10)] {
    action: fireWeapon()
    action: reload()
}
```

#### 2. Chained Fallbacks (`|`)
Quickly try alternative actions without declaring an explicit `selector` block:
```btscript
// Try to sprint, or fall back to walking, or fall back to crawling
action: sprintToCover() | walkToCover() | crawlToCover()
```

#### 3. Prefix Decorator Shorthands
Prefix symbols provide instant, readable decorator applications:

| Shorthand | Sugar Syntax | Desugared Equivalent |
| :--- | :--- | :--- |
| **Inversion** | `!isEnemyVisible()` | `decorator: inverter { condition: isEnemyVisible() }` |
| **Force Success** | `/tryLootChest()` | `decorator: force_success { action: tryLootChest() }` |
| **Force Failure** | `\warnNearbyGuards()` | `decorator: force_failure { action: warnNearbyGuards() }` |
| **Repeat N Times**| `-3 walkForward()` | `decorator: repeat(3) { action: walkForward() }` |
| **Retry N Times** | `--2 connectServer()` | `decorator: retry(2) { action: connectServer() }` |

Example combining sugars:
```btscript
sequence {
    condition: !isAlarmTriggered()
    action: --3 hackTerminal()
    action: /grabIntel()
}
```

---

### Arbor VII: Compiler Directives & Analysis Toggles

Directives appear at the top of a `.tree` file to configure compiler behavior and static analysis:

```btscript
// Set default target transpilation language
@lang: python

// Include external tree files
@import: "skills.tree"

// Static analysis toggles
@enable: arity          // Enable/disable leaf overloading rules
@enable: types          // Enable/disable argument literal type checking
@enable: warnings       // Toggle compiler warnings
@enable: werror         // Treat warnings as fatal errors (strict mode)
@enable: stub           // Toggle ContextStub interface generation
```

#### Arity & Signature Rules:
- **Arity Rule**: By default (`@enable: arity`), leaf tasks allow overloading with different argument counts. Under `@disable: arity`, all calls to the same action/condition must use the exact same argument count.
- **Type Signature Rule**: Under `@enable: types` (default), calls sharing the same argument count must pass matching literal types (`NUMBER`, `STRING`, `BOOLEAN`). Blackboard variables (`$var`) and raw identifiers act as wildcards. Under `@disable: types`, signature checks are skipped.

---

## Runtime Integration Guide

### Running in Python

BTScript generates pure Python classes alongside an auto-generated context interface:

```python
from guard import GuardBotBehaviorTree, GuardBotContext
from runtime import Status

# 1. Provide task implementations via context subclass or binding
class GameContext(GuardBotContext):
    def isEnemyVisible(self) -> bool:
        return True

    def attackEnemy(self) -> Status:
        print("Attacking enemy!")
        return Status.SUCCESS

    def patrolWaypoints(self) -> Status:
        return Status.SUCCESS

# 2. Instantiate behavior tree with your context
ctx = GameContext()
tree = GuardBotBehaviorTree(ctx)

# 3. Tick tree in your game loop (with delta time dt)
status = tree.tick(ctx, dt = 0.016)
print(f"Tree tick result: {status}")
```

For unit tests, use the built-in mock factory:
```python
mock_ctx = GuardBotContext.create_mock(default_status = Status.SUCCESS)
tree = GuardBotBehaviorTree(mock_ctx)
assert tree.tick(mock_ctx) == Status.SUCCESS
```

### Running in Lua

The Lua transpiler produces clean tables compatible with Lua 5.1+, LuaJIT, Defold, and LÖVE2D:

```lua
local guard = require("guard")
local runtime = require("runtime")

-- 1. Implement context functions
local ctx = {
    isEnemyVisible = function() return true end,
    attackEnemy = function() return runtime.Status.SUCCESS end,
    patrolWaypoints = function() return runtime.Status.SUCCESS end,
}

-- 2. Create tree instance and tick
local tree = guard.GuardBotBehaviorTree.new(ctx)
local status = tree:tick(ctx, 0.016)
print("Tree status: " .. status)
```

---

## Python API

You can also embed BTScript directly in your Python build tools:

```python
from btscript import Parser, Validator, Transpiler, Status

# 1. Parse .tree file into AST
ast, directives = Parser("examples/02_selectors.tree").parse_file()

# 2. Validate semantics and dataflow
validator = Validator(ast, directives)
validator.validate()

# 3. Transpile to desired output format
transpiler = Transpiler(ast, lang = "python", directive = directives)
code = transpiler.transpile()
```

---

## Technical Specification

For advanced technical details on AST nodes, desugaring transformation rules, cycle detection algorithms, and memory management, see **[features.md](features.md)**.

---

## Author & License

- **Author**: Developed by Lorenzo (Lor7).
- **License**: [MIT License](LICENSE). Free for personal and commercial use with attribution.
