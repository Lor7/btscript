# BTScript User Guide

Welcome to the **BTScript User Guide**. This document provides a complete walkthrough of the BTScript language, its syntax, behavior tree composition principles, runtime integration with game loops, and the compiler's dry-run verification mode.

---

## Table of Contents
1. [Language Tour: Core Concepts (Arbor I – VII)](#language-tour-core-concepts)
   - [Arbor I: Primitive Trees (Sequences & Actions)](#arbor-i-primitive-trees-sequences--actions)
   - [Arbor II: Decision Flow (Selectors & Conditions)](#arbor-ii-decision-flow-selectors--conditions)
   - [Arbor III: Execution Modifiers (Decorators & Stateful Memory)](#arbor-iii-execution-modifiers-decorators--stateful-memory)
   - [Arbor IV: Dataflow (Blackboard & Parameters)](#arbor-iv-dataflow-blackboard--parameters)
   - [Arbor V: Architecture & Modularity (Subtrees & Imports)](#arbor-v-architecture--modularity-subtrees--imports)
   - [Arbor VI: Expressive Shorthands (Syntactic Sugar)](#arbor-vi-expressive-shorthands-syntactic-sugar)
   - [Arbor VII: Compiler Directives & Analysis Toggles](#arbor-vii-compiler-directives--analysis-toggles)
2. [Runtime Integration Guide](#runtime-integration-guide)
   - [Running in Python](#running-in-python)
   - [Running in Lua](#running-in-lua)
3. [Dry-Run & Semantic Verification Mode (`--check`)](#dry-run--semantic-verification-mode---check)

---

## Language Tour: Core Concepts

### Arbor I: Primitive Trees (Sequences & Actions)

The most basic behavior tree consists of a named `tree` block containing a composite (`sequence`) and leaf tasks (`action`):

```btscript
tree HelloBot {
    sequence {
        action: sayHello()
        action: wanderAround()
    }
}
```

- **`tree Name { ... }`**: Declares a behavior tree root.
- **`sequence { ... }`**: Ticks its children sequentially from top to bottom.
  - If any child returns `FAILURE`, the sequence aborts immediately and returns `FAILURE`.
  - If a child returns `RUNNING`, the sequence pauses and yields `RUNNING`.
  - If all children return `SUCCESS`, the sequence succeeds.
- **`action: name(args...)`**: Executes an action method provided by your game or agent context.

---

### Arbor II: Decision Flow (Selectors & Conditions)

Autonomous agents make decisions using fallbacks (`selector`) gated by checks (`condition`):

```btscript
tree GuardBot {
    selector {
        // High priority: attack if enemy is in range
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

- **`selector { ... }`**: Tries each child in order.
  - If a child succeeds or is running, the selector stops and returns that status.
  - It only falls back to the next child if the current one returns `FAILURE`.
  - If all children fail, the selector returns `FAILURE`.
- **`condition: name(args...)`**: Checks a boolean predicate. Returns `SUCCESS` if true, `FAILURE` if false.

---

### Arbor III: Execution Modifiers (Decorators & Stateful Memory)

Decorators wrap a single child node to modify its execution behavior.

```btscript
tree PatrolBot {
    stateful sequence {
        // Retry locating target up to 3 times before failing
        decorator: retry(3) {
            action: findTarget()
        }

        // Pause for 2.5 seconds before scanning
        decorator: delay(2.5) {
            action: scanArea()
        }

        // Invert condition outcome (SUCCESS <-> FAILURE)
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
- `inverter`: Inverts child status (`SUCCESS` becomes `FAILURE`, `FAILURE` becomes `SUCCESS`, `RUNNING` stays `RUNNING`).
- `force_success`: Always returns `SUCCESS`, regardless of child outcome.
- `force_failure`: Always returns `FAILURE`, regardless of child outcome.
- `repeat(N)`: Ticks child repeatedly until it executes `N` times.
- `retry(N)`: Retries child on `FAILURE` up to `N` times before returning `FAILURE`.
- `timeout(seconds)`: Returns `FAILURE` if the child remains in `RUNNING` longer than the given duration.
- `delay(seconds)`: Pauses execution for a specified duration before ticking the child.
- `cooldown(seconds)`: Enforces a minimum cooldown duration before the child can be re-executed.

#### Stateful vs Stateless Memory:
By default, composites are **stateless** (they re-evaluate starting from their first child on every tick). Adding the `stateful` modifier remembers which child yielded `RUNNING` and resumes directly from that child on subsequent ticks:
```btscript
stateful sequence { ... }
stateful selector { ... }
```

---

### Arbor IV: Dataflow (Blackboard & Parameters)

Blackboards enable nodes to share dynamic state (coordinates, targets, speeds, timestamps). You can declare default blackboard values and pass parameters into trees:

```btscript
tree CombatAI(patrolSpeed = 3.5, maxChaseDistance = 50.0, minRange = -5.0) {
    blackboard {
        $target = none,
        $targetVisible = false,
        $offset = -10
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

- **Tree Parameters**: `tree Name(param1, param2 = default)` enables parameterized, reusable trees. Supports positive and negative literals (`-10`, `-1.5`).
- **Blackboard Block**: `blackboard { $var = default, ... }` initializes blackboard keys. Supports strings, booleans, `none`, positive and negative numbers.
- **Reading Variables**: Pass `$varName` as an argument to any action, condition, or subtree.
- **Writing Variables (`->`)**: Append `-> $varName` to assign an action's return value directly into the blackboard.
- **Static Verification**: The compiler detects if a variable is read before being written or declared, and warns about unused variables.

---

### Arbor V: Architecture & Modularity (Subtrees & Imports)

Scale complex AI architectures into clean, modular files using `subtree:` and `@import:`:

```btscript
// skills.tree
tree CombatSkills(targetEnemy) {
    sequence {
        action: aimAt(targetEnemy)
        action: fireWeapon(targetEnemy)
    }
}
```

```btscript
// main.tree
@import: "skills.tree"

tree MainAgent {
    blackboard {
        $enemy = none
    }

    selector {
        sequence {
            action: detectEnemy() -> $enemy
            // Invoke modular subtree with arguments
            subtree: CombatSkills($enemy)
        }
        action: idle()
    }
}
```

- **`@import: "path/to/file.tree"`**: Injects external tree files. The import resolver prevents duplicate and circular file inclusions.
- **`subtree: SubtreeName(args...)`**: Executes another behavior tree as a sub-routine. Argument counts are verified at compile time, and recursive call cycles are detected before execution.

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
Express alternative fallback actions inline without writing full `selector` blocks:
```btscript
// Tries each action from left to right until one succeeds
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
@lang: python           // Options: python, lua, xml, json, mermaid, ascii

// Include external tree files
@import: "skills.tree"

// Static analysis toggles
@enable: arity          // Overloading rules (default: enabled)
@enable: types          // Argument literal type checks (default: enabled)
@enable: warnings       // Toggle compiler warnings (default: enabled)
@enable: werror         // Treat warnings as fatal errors (default: disabled)
@enable: stub           // Generate ContextStub interface (default: enabled)
```

#### Arity & Signature Rules:
- **Arity Rule**: Under `@enable: arity` (default), leaf actions and conditions allow overloading with varying argument counts. Under `@disable: arity`, all invocations of a leaf must strictly share the exact same parameter count.
- **Type Signature Rule**: Under `@enable: types` (default), calls sharing the same arity must pass matching literal types (`NUMBER`, `STRING`, `BOOLEAN`). Blackboard variables (`$var`) and raw identifiers act as wildcards. Under `@disable: types`, signature checks are skipped.

---

## Runtime Integration Guide

### Running in Python

BTScript transpiles your trees into clean Python class hierarchies and generates a `Context` interface stub:

```python
from guard import GuardBotBehaviorTree, GuardBotContext
from runtime import Status

# 1. Implement context actions and conditions
class GameContext(GuardBotContext):
    def isEnemyVisible(self) -> bool:
        return True

    def isEnemyInRange(self, distance: float) -> bool:
        return distance <= 15.0

    def attackEnemy(self) -> Status:
        print("Attacking enemy!")
        return Status.SUCCESS

    def patrolWaypoints(self) -> Status:
        return Status.SUCCESS

# 2. Instantiate the behavior tree with your context
ctx = GameContext()
tree = GuardBotBehaviorTree(ctx)

# 3. Tick tree in your game loop (with delta time dt)
status = tree.tick(ctx, dt = 0.016)
print(f"Tree tick result: {status}")
```

#### Mock Contexts for Fast Unit Testing:
```python
mock_ctx = GuardBotContext.create_mock(default_status = Status.SUCCESS)
tree = GuardBotBehaviorTree(mock_ctx)
assert tree.tick(mock_ctx) == Status.SUCCESS
```

### Running in Lua

The Lua transpiler produces standalone modules compatible with Lua 5.1+, LuaJIT, Defold, and LÖVE2D:

```lua
local guard = require("guard")
local runtime = require("runtime")

-- 1. Implement context functions
local ctx = {
    isEnemyVisible = function() return true end,
    isEnemyInRange = function(distance) return distance <= 15.0 end,
    attackEnemy = function() return runtime.Status.SUCCESS end,
    patrolWaypoints = function() return runtime.Status.SUCCESS end,
}

-- 2. Create tree instance and tick
local tree = guard.GuardBotBehaviorTree.new(ctx)
local status = tree:tick(ctx, 0.016)
print("Tree status: " .. status)
```

---

## Dry-Run & Semantic Verification Mode (`--check`)

BTScript provides a dedicated **dry-run / check mode** that parses and rigorously validates your behavior trees without emitting any transpiled source code or copying runtime files:

```bash
# Using the bts CLI shortcut
bts path/to/tree.tree -c
# or:
bts path/to/tree.tree --check

# Using the Python module runner
python3 -m btscript path/to/tree.tree -c

# Enabling strict mode (treat warnings as fatal errors)
bts path/to/tree.tree -c -Werror
```

### What Dry-Run Mode Checks:
1. **Subtree Cycles**: Detects circular subtree invocations (e.g. `TreeA -> TreeB -> TreeA`) using depth-first graph traversal.
2. **Arity Consistency**: Verifies that leaves called across files match expected argument counts.
3. **Type Signatures**: Verifies literal argument types (`NUMBER`, `STRING`, `BOOLEAN`) across repeated leaf invocations.
4. **Dataflow & Variable Lifecycle**:
   - Warns if a blackboard variable (`$var`) is read before being written or declared.
   - Warns if a blackboard variable is declared or written but never read anywhere in the tree.
5. **Dead-Code Analysis**:
   - Warns about unreachable sibling nodes following a `force_failure` in a `sequence`.
   - Warns about unreachable sibling nodes following a `force_success` in a `selector`.
6. **Redundant Decorator Analysis**:
   - Warns on double inversion (`! !action()`).
   - Warns on redundant combinations like `inverter` wrapping `force_success`.

### Integration into CI and Git Pre-Commit Hooks
Because dry-run mode returns an exit code of `0` on success and non-zero on error, it is ideal for git hooks:

```bash
#!/bin/sh
# .git/hooks/pre-commit
python3 -m btscript examples/*.tree -c || {
    echo "[ERROR] BTScript validation failed. Commit aborted."
    exit 1
}
```
