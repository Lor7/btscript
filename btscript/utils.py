"""
btscript.utils
~~~~~~~~~~~~~~

Utility functions for AST inspection, structural statistics, and diagnostics.
"""

from .nodes import TreeRoot
from .transpilers.ascii_tree import render_ascii_tree


def inspect_tree(tree: TreeRoot) -> str:
    """Computes and formats structural statistics for a given behavior tree."""
    stats = {
        "total_nodes": 0,
        "max_depth": 0,
        "composites": 0,
        "actions": set(),
        "conditions": set(),
        "decorators": 0,
        "subtrees": set()
    }

    def walk(node, depth = 1):
        stats['total_nodes'] += 1
        stats['max_depth'] = max(stats['max_depth'], depth)
        name = type(node).__name__

        if name in ("SequenceNode", "SelectorNode", "ParallelNode"):
            stats['composites'] += 1
            for child in node.children:
                walk(child, depth + 1)

        elif name == "ActionNode":
            stats['actions'].add(node.name)

        elif name == "ConditionNode":
            stats['conditions'].add(node.name)

        elif name == "DecoratorNode":
            stats['decorators'] += 1
            if node.child:
                walk(node.child, depth + 1)

        elif name == "SubtreeNode":
            stats['subtrees'].add(node.name)

    for child in tree.children:
        walk(child, depth = 1)

    return (
        f"Tree '{tree.name}': {stats['total_nodes']} nodes, depth {stats['max_depth']} | "
        f"Composites: {stats['composites']} | "
        f"Actions ({len(stats['actions'])}): {', '.join(sorted(stats['actions'])) or 'none'} | "
        f"Conditions ({len(stats['conditions'])}): {', '.join(sorted(stats['conditions'])) or 'none'} | "
        f"Decorators: {stats['decorators']} | "
        f"Subtrees: {', '.join(sorted(stats['subtrees'])) or 'none'}"
    )