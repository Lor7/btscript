import pytest
from btscript.validator import Validator, SemanticError

def test_empty_composite(parse_src):
    code = """
    tree Bad {
        sequence {
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError):
        v.validate()

def test_arity_disallowed(parse_src):
    code = """
    @disable: arity
    tree Test {
        sequence {
            action: run(1)
            action: run(1, 2)
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError):
        v.validate()

def test_type_mismatch(parse_src):
    code = """
    @enable: types
    tree Test {
        sequence {
            action: run(10)
            action: run("str")
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError):
        v.validate()

def test_cycle_detection(parse_src):
    code = """
    tree A {
        sequence {
            subtree: B
        }
    }
    tree B {
        sequence {
            subtree: A
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError) as exc:
        v.validate()
    assert "Circular subtree invocation detected" in str(exc.value)

def test_warnings_and_werror(parse_src):
    code = """
    @enable: werror
    tree Test {
        sequence {
            action: !!noop()
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError) as exc:
        v.validate()
    assert "Double inversion is redundant" in str(exc.value)

def test_dead_code_warning(parse_src):
    code = """
    tree Test {
        sequence {
            condition: isReady()
            decorator: force_failure {
                action: step()
            }
            action: unreachableAction()
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    v.validate()
    assert len(v.warnings) == 1
    assert "Unreachable nodes in Sequence" in v.warnings[0]

def test_duplicate_tree_error(parse_src):
    code = """
    tree Dup { sequence { action: a() } }
    tree Dup { sequence { action: b() } }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError) as exc:
        v.validate()
    assert "Duplicate tree declaration 'Dup'" in str(exc.value)

def test_unknown_subtree_error(parse_src):
    code = """
    tree Main {
        sequence {
            subtree: GhostTree
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError) as exc:
        v.validate()
    assert "Unknown subtree 'GhostTree'" in str(exc.value)

def test_subtree_param_mismatch(parse_src):
    code = """
    tree Sub(a, b) {
        sequence {
            action: run(a, b)
        }
    }
    tree Main {
        sequence {
            subtree: Sub(1)
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError) as exc:
        v.validate()
    assert "Subtree 'Sub' expects 2 argument(s), but got 1" in str(exc.value)

def test_blackboard_read_before_write_warning(parse_src):
    code = """
    tree Patrol {
        sequence {
            action: attack($target)
            action: findTarget() -> $target
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    v.validate()
    assert len(v.warnings) == 1
    assert "Blackboard variable '$target' is read before being written" in v.warnings[0]

def test_blackboard_read_before_write_werror(parse_src):
    code = """
    @enable: werror
    tree Patrol {
        sequence {
            action: attack($target)
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    with pytest.raises(SemanticError) as exc:
        v.validate()
    assert "Blackboard variable '$target' is read before being written" in str(exc.value)

def test_blackboard_valid_dataflow(parse_src):
    code = """
    tree Patrol {
        sequence {
            action: findTarget() -> $target
            condition: isAlive($target)
            action: attack($target)
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    v.validate()
    assert len(v.warnings) == 0
    assert len(v.errors) == 0

def test_unused_variable_warning(parse_src):
    code = """
    tree Patrol {
        sequence {
            action: findTarget() -> $target
            action: finish()
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    v.validate()
    assert len(v.warnings) == 1
    assert "Variable 'target' is declared/written but never read (unused)" in v.warnings[0]

def test_blackboard_defaults_validation_used(parse_src):
    code = """
    tree Patrol {
        blackboard {
            $speed = 10
        }
        sequence {
            action: run($speed)
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    v.validate()
    assert len(v.errors) == 0
    assert len(v.warnings) == 0

def test_blackboard_defaults_validation_unused(parse_src):
    code = """
    tree Patrol {
        blackboard {
            $speed = 10,
            $unused_var = "test"
        }
        sequence {
            action: run($speed)
        }
    }
    """
    ast, dirs = parse_src(code)
    v = Validator(ast, dirs)
    v.validate()
    assert len(v.errors) == 0
    assert len(v.warnings) == 1
    assert "Variable 'unused_var' is declared/written but never read (unused)" in v.warnings[0]


