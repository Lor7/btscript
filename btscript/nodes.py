"""
btscript.nodes
~~~~~~~~~~~~~~

Abstract Syntax Tree (AST) node definitions for BTScript.

Hierarchy:
    ASTNode
    ├── TreeRoot              (Container for tree definitions and blackboard defaults)
    ├── Composites
    │   ├── SequenceNode      (Executes children in order until one fails)
    │   ├── SelectorNode      (Executes children in order until one succeeds)
    │   └── ParallelNode      (Concurrently executes all children)
    ├── Leaves
    │   ├── ActionNode        (Executes a behavior task, optional blackboard output)
    │   ├── ConditionNode     (Boolean guard condition)
    │   └── SubtreeNode       (Reusable invocation of another behavior tree)
    └── DecoratorNode         (Modifies child execution: retry, repeat, timeout, etc.)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ASTNode:
    """Base class for all Abstract Syntax Tree nodes with source location metadata."""
    token: Optional[object] = field(default = None, repr = False)
    source_file: Optional[str] = field(default = None, repr = False)


# ======================================================================
# Root Tree Node
# ======================================================================

@dataclass
class TreeRoot(ASTNode):
    """Represents a top-level behavior tree definition."""
    name: str = ""
    children: List[ASTNode] = field(default_factory = list)
    params: List[str] = field(default_factory = list)
    blackboard: dict = field(default_factory = dict)


# ======================================================================
# Composite Nodes (Control Flow)
# ======================================================================

@dataclass
class SequenceNode(ASTNode):
    """Executes child nodes in sequence. Fails if any child fails."""
    children: List[ASTNode] = field(default_factory = list)
    memory_type: str = "stateless"

    @property
    def is_stateful(self) -> bool:
        """Returns True if the composite resumes from running children on next tick."""
        return self.memory_type == "stateful"


@dataclass
class SelectorNode(ASTNode):
    """Executes child nodes as fallbacks. Succeeds if any child succeeds."""
    children: List[ASTNode] = field(default_factory = list)
    memory_type: str = "stateless"

    @property
    def is_stateful(self) -> bool:
        """Returns True if the composite resumes from running children on next tick."""
        return self.memory_type == "stateful"


@dataclass
class ParallelNode(ASTNode):
    """Executes all child nodes concurrently."""
    children: List[ASTNode] = field(default_factory = list)
    memory_type: str = "stateless"

    @property
    def is_stateful(self) -> bool:
        return self.memory_type == "stateful"


# ======================================================================
# Leaf Nodes (Execution & Guards)
# ======================================================================

@dataclass
class ActionNode(ASTNode):
    """Leaf action executing domain logic. Can write its result to a blackboard variable."""
    name: str = ""
    args: List[str] = field(default_factory = list)
    output_var: Optional[str] = None


@dataclass
class ConditionNode(ASTNode):
    """Leaf guard predicate that evaluates to SUCCESS (true) or FAILURE (false)."""
    name: str = ""
    args: List[str] = field(default_factory = list)
    output_var: Optional[str] = None


@dataclass
class SubtreeNode(ASTNode):
    """Invokes another behavior tree as a reusable composite node."""
    name: str = ""
    args: List[str] = field(default_factory = list)


# ======================================================================
# Decorator Nodes
# ======================================================================

@dataclass
class DecoratorNode(ASTNode):
    """Wraps a single child node to alter its behavior or outcome."""
    property: str = ""
    child: Optional[ASTNode] = None
    args: List[str] = field(default_factory = list)