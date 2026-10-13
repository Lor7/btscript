"""
btscript.transpilers.xml_tree
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Exports BTScript ASTs to standard XML behavior tree representations with
subtrees, stateful memory tags, and blackboard attributes.
"""

import xml.etree.ElementTree as ET
import xml.dom.minidom


class XMLTranspiler:
    def __init__(self, ast):
        self.trees = ast if isinstance(ast, list) else [ast]

    def transpile(self) -> str:
        main_name = self.trees[-1].name if self.trees else ""
        root_elem = ET.Element("root", {"main_tree_to_execute": main_name})

        for tree in self.trees:
            tree_elem = ET.SubElement(root_elem, "BehaviorTree", {"ID": tree.name})
            if getattr(tree, "blackboard", None):
                bb_elem = ET.SubElement(tree_elem, "Blackboard")
                for k, v in tree.blackboard.items():
                    ET.SubElement(bb_elem, "Variable", {"name": k, "default": str(v)})
            for child in tree.children:
                self.visit(child, tree_elem)

        rough_string = ET.tostring(root_elem, "utf-8")
        reparsed = xml.dom.minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def visit(self, node, parent_elem):
        method = f"visit_{type(node).__name__}"
        getattr(self, method)(node, parent_elem)

    def visit_SequenceNode(self, node, parent):
        if node.is_stateful:
            seq = ET.SubElement(parent, "SequenceWithMemory")
        else:
            seq = ET.SubElement(parent, "Sequence")
        for c in node.children:
            self.visit(c, seq)

    def visit_SelectorNode(self, node, parent):
        if node.is_stateful:
            sel = ET.SubElement(parent, "FallbackWithMemory")
        else:
            sel = ET.SubElement(parent, "Fallback")
        for c in node.children:
            self.visit(c, sel)

    def visit_ParallelNode(self, node, parent):
        attribs = {"memory": "true"} if node.is_stateful else {}
        par = ET.SubElement(parent, "Parallel", attribs)
        for c in node.children:
            self.visit(c, par)

    def visit_DecoratorNode(self, node, parent):
        attribs = {"property": node.property}
        if node.args:
            attribs["count"] = str(node.args[0])
        dec = ET.SubElement(parent, "Decorator", attribs)
        if node.child:
            self.visit(node.child, dec)

    def visit_ActionNode(self, node, parent):
        attribs = {"ID": node.name}
        for idx, arg in enumerate(node.args):
            attribs[f"arg{idx+1}"] = str(arg).strip('"')
        if getattr(node, "output_var", None):
            attribs["output"] = f"${node.output_var}"
        ET.SubElement(parent, "Action", attribs)

    def visit_ConditionNode(self, node, parent):
        attribs = {"ID": node.name}
        for idx, arg in enumerate(node.args):
            attribs[f"arg{idx+1}"] = str(arg).strip('"')
        ET.SubElement(parent, "Condition", attribs)

    def visit_SubtreeNode(self, node, parent):
        attr = {"ID": node.name}
        for idx, arg in enumerate(getattr(node, "args", [])):
            if "=" in arg:
                k, v = arg.split("=", 1)
                attr[k.strip()] = v.strip().strip('"')
            else:
                attr[f"arg{idx+1}"] = str(arg).strip('"')
        ET.SubElement(parent, "SubTree", attr)
