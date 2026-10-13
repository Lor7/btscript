from ..nodes import TreeRoot, DecoratorNode, ActionNode, ConditionNode, SubtreeNode

def render_ascii_tree(node, prefix: str = "", is_last: bool = True, is_root: bool = True) -> str:
    lines = []
    ntype = type(node).__name__
    if ntype == "TreeRoot":
        params_str = f"({', '.join(node.params)})" if getattr(node, "params", None) else ""
        bb_str = f" [bb: {', '.join(f'${k}={v}' for k, v in node.blackboard.items())}]" if getattr(node, "blackboard", None) else ""
        label = f"Tree '{node.name}{params_str}'{bb_str}"
    elif ntype == "SequenceNode":
        tag = "Stateful " if getattr(node, "memory_type", "") == "stateful" else ""
        label = f"{tag}Sequence [→]"
    elif ntype == "SelectorNode":
        tag = "Stateful " if getattr(node, "memory_type", "") == "stateful" else ""
        label = f"{tag}Selector [?]"
    elif ntype == "ParallelNode":
        tag = "Stateful " if getattr(node, "memory_type", "") == "stateful" else ""
        label = f"{tag}Parallel [⇉]"
    elif ntype == "DecoratorNode":
        args_str = f"({', '.join(map(str, node.args))})" if node.args else ""
        label = f"Decorator: {node.property}{args_str} [δ]"
    elif ntype == "ActionNode":
        args = ", ".join(map(str, node.args))
        out_str = f" -> ${node.output_var}" if getattr(node, "output_var", None) else ""
        label = f"Action: {node.name}({args}){out_str}"
    elif ntype == "ConditionNode":
        args = ", ".join(map(str, node.args))
        label = f"Condition: {node.name}({args})"
    elif ntype == "SubtreeNode":
        args_str = f"({', '.join(map(str, node.args))})" if getattr(node, "args", None) else ""
        label = f"Subtree: {node.name}{args_str} [↳]"
    else:
        label = str(node)

    if is_root:
        lines.append(label)
        child_prefix = ""
    else:
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{label}")
        child_prefix = prefix + ("    " if is_last else "│   ")

    children = []
    if hasattr(node, "children"):
        children = node.children
    elif isinstance(node, DecoratorNode) and node.child:
        children = [node.child]

    for idx, child in enumerate(children):
        last = (idx == len(children) - 1)
        lines.append(render_ascii_tree(child, prefix=child_prefix, is_last=last, is_root=False))

    return "\n".join(lines)


class AsciiTranspiler:
    def __init__(self, ast, directive = None):
        self.trees = ast if isinstance(ast, list) else [ast]
        self.directive = directive or {}

    def transpile(self) -> str:
        return "\n\n".join(render_ascii_tree(t) for t in self.trees)
