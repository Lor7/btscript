from btscript.nodes import ActionNode, ConditionNode, SequenceNode, SelectorNode, ParallelNode, DecoratorNode, SubtreeNode

def test_composite_nodes(parse_src):
    code = """
    tree Simple {
        sequence {
            action: run()
        }
        selector {
            condition: check()
        }
        parallel {
            action: tick()
        }
    }
    """
    ast, _ = parse_src(code)
    tree = ast[0]
    assert tree.name == "Simple"
    assert len(tree.children) == 3
    assert isinstance(tree.children[0], SequenceNode)
    assert isinstance(tree.children[1], SelectorNode)
    assert isinstance(tree.children[2], ParallelNode)

def test_sugars_and_chain(parse_src):
    code = r"""
    tree Sugars {
        sequence {
            action: step1() | action: step2() | action: step3()
            /action: succ()
            \action: fail()
            !action: inv()
            -3 action: rep()
            --2 action: ret()
        }
    }
    """
    ast, _ = parse_src(code)
    seq = ast[0].children[0]
    
    # | chain
    chain = seq.children[0]
    assert isinstance(chain, SelectorNode)
    assert len(chain.children) == 3
    assert [c.name for c in chain.children] == ["step1", "step2", "step3"]

    # / force_success
    assert isinstance(seq.children[1], DecoratorNode)
    assert seq.children[1].property == "force_success"

    # \ force_failure
    assert isinstance(seq.children[2], DecoratorNode)
    assert seq.children[2].property == "force_failure"

    # ! inverter
    assert isinstance(seq.children[3], DecoratorNode)
    assert seq.children[3].property == "inverter"

    # -3 repeat
    assert isinstance(seq.children[4], DecoratorNode)
    assert seq.children[4].property == "repeat"
    assert seq.children[4].args == ["3"]

    # --2 retry
    assert isinstance(seq.children[5], DecoratorNode)
    assert seq.children[5].property == "retry"
    assert seq.children[5].args == ["2"]

def test_directives(parse_src):
    code = """
    @disable: arity
    @disable: types
    @disable: stub
    @enable: werror
    @lang: lua

    tree Test {
        sequence {
            action: noop()
        }
    }
    """
    _, dirs = parse_src(code)
    assert dirs["check_arity"] is False
    assert dirs["check_types"] is False
    assert dirs["stub"] is False
    assert dirs["werror"] is True
    assert dirs["lang"] == "lua"

def test_comments_and_args(parse_src):
    code = """
    # Full line comment
    tree ArgsTest {
        sequence {
            action: call(1, 2.5, "hello", true, false, none) # trailing comment
        }
    }
    """
    ast, _ = parse_src(code)
    act = ast[0].children[0].children[0]
    assert act.name == "call"
    assert act.args == ["1", "2.5", '"hello"', "true", "false", "none"]

def test_unknown_directive_error(parse_src):
    import pytest
    code = """
    @enabled: types
    tree Test {
        sequence { action: run() }
    }
    """
    with pytest.raises(Exception) as exc:
        parse_src(code)
    assert "Unknown directive '@enabled'" in str(exc.value)

def test_inline_preconditions(parse_src):
    code = """
    tree Guard {
        sequence [isReady(), !hasAmmo(10)] {
            action: attack()
        }
        selector [condition: checkHealth()] {
            action: retreat()
        }
    }
    """
    ast, _ = parse_src(code)
    seq = ast[0].children[0]
    assert len(seq.children) == 3
    assert isinstance(seq.children[0], ConditionNode)
    assert seq.children[0].name == "isReady"
    assert seq.children[0].args == []

    assert isinstance(seq.children[1], DecoratorNode)
    assert seq.children[1].property == "inverter"
    assert isinstance(seq.children[1].child, ConditionNode)
    assert seq.children[1].child.name == "hasAmmo"
    assert seq.children[1].child.args == ["10"]

    assert isinstance(seq.children[2], ActionNode)
    assert seq.children[2].name == "attack"

    sel = ast[0].children[1]
    assert len(sel.children) == 2
    assert isinstance(sel.children[0], ConditionNode)
    assert sel.children[0].name == "checkHealth"
    assert isinstance(sel.children[1], ActionNode)

def test_blackboard_variables_parsing(parse_src):
    code = """
    tree Patrol {
        sequence {
            action: findTarget("orc") -> $target
            condition: isAlive($target)
            action: attack($target, 50)
            subtree: Sub($target)
        }
    }
    """
    ast, _ = parse_src(code)
    seq = ast[0].children[0]
    act1 = seq.children[0]
    assert act1.name == "findTarget"
    assert act1.args == ['"orc"']
    assert act1.output_var == "target"

    cond = seq.children[1]
    assert cond.name == "isAlive"
    assert cond.args == ["$target"]

    act2 = seq.children[2]
    assert act2.name == "attack"
    assert act2.args == ["$target", "50"]

    sub = seq.children[3]
    assert sub.name == "Sub"
    assert sub.args == ["$target"]

def test_blackboard_defaults_parsing(parse_src):
    code = """
    tree Patrol {
        blackboard {
            $speed = 5.5,
            $target = "goblin",
            $aggressive = true,
            $backup = none,
            $offset = -10
        }
        sequence {
            action: attack($target, $speed)
        }
    }
    """
    ast, _ = parse_src(code)
    tree = ast[0]
    assert tree.blackboard == {
        "speed": "5.5",
        "target": '"goblin"',
        "aggressive": "true",
        "backup": "none",
        "offset": "-10",
    }


def test_negative_numbers_in_arguments_and_ascii_lang(parse_src):
    code = """
    @lang: ascii

    tree Child(val = -5) {
        sequence {
            action: work(val)
        }
    }

    tree Main(speed = -1.5, count = -42) {
        blackboard {
            $delta = -0.016,
            $min_x = -100
        }
        sequence {
            condition: isBelow(-50)
            action: applyForce(-10, -3.14)
            subtree: Child(-20)
        }
    }
    """
    ast, dirs = parse_src(code)
    assert dirs["lang"] == "ascii"

    child_tree = ast[0]
    assert child_tree.params == ["val=-5"]

    main_tree = ast[1]
    assert main_tree.params == ["speed=-1.5", "count=-42"]
    assert main_tree.blackboard["delta"] == "-0.016"
    assert main_tree.blackboard["min_x"] == "-100"

    seq = main_tree.children[0]
    cond = seq.children[0]
    assert cond.args == ["-50"]

    act = seq.children[1]
    assert act.args == ["-10", "-3.14"]

    sub = seq.children[2]
    assert sub.args == ["-20"]


def test_lex_error_and_parse_error(parse_src):
    import pytest
    from btscript.lexer import Lexer, LexError
    from btscript.parser import ParseError

    # LexError on unknown character
    lexer_bad_char = Lexer("tree T { ~ }", file_path = "test.tree")
    with pytest.raises(LexError) as exc_char:
        lexer_bad_char.tokenize()
    assert "Unknown character '~'" in str(exc_char.value)
    assert "test.tree" in str(exc_char.value)
    assert "^" in str(exc_char.value)

    # LexError on unterminated string
    lexer_bad_str = Lexer('tree T { action: a("unterminated) }', file_path = "test.tree")
    with pytest.raises(LexError) as exc_str:
        lexer_bad_str.tokenize()
    assert "Unterminated string literal" in str(exc_str.value)

    # ParseError on unexpected token
    with pytest.raises(ParseError) as exc_parse:
        parse_src("tree T { invalid_token }")
    assert "Unexpected token 'invalid_token'" in str(exc_parse.value)



