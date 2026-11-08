from btscript.transpilers import PyTranspiler, LuaTranspiler, MermaidTranspiler
from runtime import Status

def test_python_e2e_execution(parse_src):
    code = r"""
    tree Test {
        sequence {
            condition: isReady()
            action: step1() | action: step2()
            /action: finish()
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()
    
    ns = {}
    exec(py_code, ns)
    TestTree = ns["TestBehaviorTree"]
    TestStub = ns["TestContextStub"]

    ctx = TestStub()
    ctx.isReady = lambda: True
    ctx.step1 = lambda: False  # fails
    ctx.step2 = lambda: True   # fallback succeeds
    ctx.finish = lambda: Status.SUCCESS

    tree = TestTree(ctx)
    assert tree.tick() == Status.SUCCESS

def test_python_mock_factory(parse_src):
    code = """
    tree Test {
        sequence {
            condition: check()
            action: run()
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()
    
    ns = {}
    exec(py_code, ns)
    mock = ns["TestContextStub"].create_mock()
    tree = ns["TestBehaviorTree"](mock)
    assert tree.tick() == Status.SUCCESS

def test_lua_output_format(parse_src):
    code = """
    tree Test {
        sequence {
            action: run()
        }
    }
    """
    ast, dirs = parse_src(code)
    lua_code = LuaTranspiler(ast, directive=dirs).transpile()
    assert "TestBehaviorTree = TestBehaviorTree" in lua_code
    assert "TestContextStub = TestContextStub" in lua_code

def test_mermaid_subgraph_output(parse_src):
    code = """
    tree Sub {
        sequence {
            action: childRun()
        }
    }
    tree Main {
        sequence {
            subtree: Sub
        }
    }
    """
    ast, dirs = parse_src(code)
    mmd_code = MermaidTranspiler(ast).transpile()
    assert "graph TD" in mmd_code
    assert "Tree: Main" in mmd_code
    assert 'subgraph subgraph_Sub' in mmd_code

def test_python_subtree_execution(parse_src):
    code = """
    tree Child {
        sequence {
            action: childAction()
        }
    }
    tree Parent {
        sequence {
            subtree: Child
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()

    ns = {}
    exec(py_code, ns)
    ParentTree = ns["ParentBehaviorTree"]
    ParentStub = ns["ParentContextStub"]

    ctx = ParentStub()
    ctx.childAction = lambda: Status.SUCCESS

    tree = ParentTree(ctx)
    assert tree.tick() == Status.SUCCESS

def test_json_transpiler(parse_src):
    import json
    code = """
    tree Test {
        sequence {
            action: doWork(1, "ok")
        }
    }
    """
    ast, _ = parse_src(code)
    from btscript.transpilers import JSONTranspiler
    out = JSONTranspiler(ast).transpile()
    data = json.loads(out)
    assert "trees" in data
    assert data["trees"][0]["name"] == "Test"
    assert data["trees"][0]["children"][0]["type"] == "Stateless Sequence"
    assert data["trees"][0]["children"][0]["children"][0]["name"] == "doWork"

def test_xml_transpiler(parse_src):
    code = """
    tree Test {
        sequence {
            action: doWork()
        }
    }
    """
    ast, _ = parse_src(code)
    from btscript.transpilers import XMLTranspiler
    out = XMLTranspiler(ast).transpile()
    assert '<root main_tree_to_execute="Test">' in out
    assert '<BehaviorTree ID="Test">' in out
    assert '<Action ID="doWork"/>' in out

def test_ascii_transpiler(parse_src):
    code = """
    tree Test {
        sequence {
            condition: isOk()
            action: doWork(1, 2)
        }
    }
    """
    ast, _ = parse_src(code)
    from btscript.transpilers import AsciiTranspiler
    out = AsciiTranspiler(ast).transpile()
    assert "Tree 'Test'" in out
    assert "└── Sequence [→]" in out
    assert "├── Condition: isOk()" in out
    assert "└── Action: doWork(1, 2)" in out

def test_parameterized_subtree_execution(parse_src):
    code = """
    tree Worker(speed, tag="def") {
        sequence {
            action: applySpeed(speed)
            action: applyTag(tag)
        }
    }
    tree Main {
        sequence {
            subtree: Worker(42, "fast")
        }
    }
    """
    ast, dirs = parse_src(code)
    from btscript.transpilers import PyTranspiler
    py_code = PyTranspiler(ast, directive=dirs).transpile()

    ns = {}
    exec(py_code, ns)
    MainTree = ns["MainBehaviorTree"]
    WorkerStub = ns["WorkerContextStub"]

    recorded = {}
    ctx = WorkerStub()
    ctx.applySpeed = lambda s: recorded.update({"speed": s}) or Status.SUCCESS
    ctx.applyTag = lambda t: recorded.update({"tag": t}) or Status.SUCCESS

    tree = MainTree(ctx)
    res = tree.tick()
    assert res == Status.SUCCESS
    assert recorded["speed"] == 42
    assert recorded["tag"] == "fast"

def test_stateful_vs_stateless_sequence_execution(parse_src):
    stateless_code = """
    tree StatelessTree {
        stateless sequence {
            action: step1()
            action: step2()
        }
    }
    """
    stateful_code = """
    tree StatefulTree {
        stateful sequence {
            action: step1()
            action: step2()
        }
    }
    """
    from btscript.transpilers import PyTranspiler
    
    # 1. Test Stateless: step1 runs again on second tick
    ast1, _ = parse_src(stateless_code)
    ns1 = {}
    exec(PyTranspiler(ast1).transpile(), ns1)
    
    counts1 = {"step1": 0, "step2": 0}
    ctx1 = ns1["StatelessTreeContextStub"]()
    ctx1.step1 = lambda: counts1.update({"step1": counts1["step1"] + 1}) or Status.SUCCESS
    ctx1.step2 = lambda: counts1.update({"step2": counts1["step2"] + 1}) or Status.RUNNING
    
    tree1 = ns1["StatelessTreeBehaviorTree"](ctx1)
    assert tree1.tick() == Status.RUNNING
    assert counts1["step1"] == 1 and counts1["step2"] == 1
    assert tree1.tick() == Status.RUNNING
    assert counts1["step1"] == 2 and counts1["step2"] == 2  # step1 re-evaluated!

    # 2. Test Stateful: step1 is skipped on second tick!
    ast2, _ = parse_src(stateful_code)
    ns2 = {}
    exec(PyTranspiler(ast2).transpile(), ns2)
    
    counts2 = {"step1": 0, "step2": 0}
    ctx2 = ns2["StatefulTreeContextStub"]()
    ctx2.step1 = lambda: counts2.update({"step1": counts2["step1"] + 1}) or Status.SUCCESS
    ctx2.step2 = lambda: counts2.update({"step2": counts2["step2"] + 1}) or Status.RUNNING
    
    tree2 = ns2["StatefulTreeBehaviorTree"](ctx2)
    assert tree2.tick() == Status.RUNNING
    assert counts2["step1"] == 1 and counts2["step2"] == 1
    assert tree2.tick() == Status.RUNNING
    assert counts2["step1"] == 1 and counts2["step2"] == 2  # step1 NOT re-evaluated, resumed at step2!

def test_stateful_vs_stateless_selector_execution(parse_src):
    stateless_code = """
    tree StatelessSel {
        stateless selector {
            action: tryFallback()
            action: longTask()
        }
    }
    """
    stateful_code = """
    tree StatefulSel {
        stateful selector {
            action: tryFallback()
            action: longTask()
        }
    }
    """
    from btscript.transpilers import PyTranspiler

    # 1. Stateless Selector: tryFallback re-evaluated on subsequent tick
    ast1, _ = parse_src(stateless_code)
    ns1 = {}
    exec(PyTranspiler(ast1).transpile(), ns1)
    counts1 = {"fallback": 0, "task": 0}
    ctx1 = ns1["StatelessSelContextStub"]()
    ctx1.tryFallback = lambda: counts1.update({"fallback": counts1["fallback"] + 1}) or Status.FAILURE
    ctx1.longTask = lambda: counts1.update({"task": counts1["task"] + 1}) or Status.RUNNING

    t1 = ns1["StatelessSelBehaviorTree"](ctx1)
    assert t1.tick() == Status.RUNNING
    assert counts1["fallback"] == 1 and counts1["task"] == 1
    assert t1.tick() == Status.RUNNING
    assert counts1["fallback"] == 2 and counts1["task"] == 2

    # 2. Stateful Selector: tryFallback is skipped on subsequent tick
    ast2, _ = parse_src(stateful_code)
    ns2 = {}
    exec(PyTranspiler(ast2).transpile(), ns2)
    counts2 = {"fallback": 0, "task": 0}
    ctx2 = ns2["StatefulSelContextStub"]()
    ctx2.tryFallback = lambda: counts2.update({"fallback": counts2["fallback"] + 1}) or Status.FAILURE
    ctx2.longTask = lambda: counts2.update({"task": counts2["task"] + 1}) or Status.RUNNING

    t2 = ns2["StatefulSelBehaviorTree"](ctx2)
    assert t2.tick() == Status.RUNNING
    assert counts2["fallback"] == 1 and counts2["task"] == 1
    assert t2.tick() == Status.RUNNING
    assert counts2["fallback"] == 1 and counts2["task"] == 2  # fallback skipped, resumed directly at running task!

def test_xml_stateful_and_params(parse_src):
    code = """
    tree Sub(speed) {
        stateful sequence {
            action: run(speed)
        }
    }
    tree Main {
        stateful selector {
            subtree: Sub(10)
        }
    }
    """
    ast, _ = parse_src(code)
    from btscript.transpilers import XMLTranspiler
    out = XMLTranspiler(ast).transpile()
    assert "<SequenceWithMemory>" in out
    assert "<FallbackWithMemory>" in out
    assert '<SubTree ID="Sub" arg1="10"/>' in out

def test_json_stateful_and_params(parse_src):
    import json
    code = """
    tree Worker(speed, tag="def") {
        stateful sequence {
            action: run(speed)
        }
    }
    """
    ast, _ = parse_src(code)
    from btscript.transpilers import JSONTranspiler
    data = json.loads(JSONTranspiler(ast).transpile())
    tree_entry = data["trees"][0]
    assert tree_entry["params"] == ["speed", 'tag="def"']
    assert tree_entry["children"][0]["type"] == "Stateful Sequence"

def test_mermaid_stateful_and_params(parse_src):
    code = """
    tree Worker(speed) {
        stateful sequence {
            action: run(speed)
        }
    }
    tree Main {
        sequence {
            subtree: Worker(5)
        }
    }
    """
    ast, _ = parse_src(code)
    from btscript.transpilers import MermaidTranspiler
    out = MermaidTranspiler(ast).transpile()
    assert '-> Sequence (stateful)' in out
    assert 'Subtree: Worker(5)' in out

def test_lua_stateful_and_params_execution(parse_src):
    import subprocess, tempfile, os, shutil
    if not shutil.which("lua"):
        return
    code = """
    tree Sub(speed) {
        sequence {
            action: run(speed)
        }
    }
    tree Main {
        stateful sequence {
            action: prep()
            subtree: Sub(42)
        }
    }
    """
    ast, dirs = parse_src(code)
    from btscript.transpilers import LuaTranspiler
    lua_code = LuaTranspiler(ast, directive=dirs).transpile()

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
        f.write(lua_code)
        lua_path = f.name

    runner = f"""
    package.path = 'btscript/runtimes/lua/?.lua;runtimes/lua/?.lua;' .. package.path
    local mod = dofile('{lua_path}')
    local recorded = {{ prep = 0, speed = nil }}
    local ctx = {{
        prep = function(self) recorded.prep = recorded.prep + 1; return 'SUCCESS' end,
        run = function(self, sp) recorded.speed = sp; return 'SUCCESS' end,
    }}
    local tree = mod.MainBehaviorTree.new(ctx)
    local st = tree:tick()
    assert(st == 'SUCCESS')
    assert(recorded.prep == 1)
    assert(recorded.speed == 42)
    """
    res = subprocess.run(["lua", "-e", runner], capture_output=True, text=True)
    os.remove(lua_path)
    assert res.returncode == 0

def test_python_inline_preconditions_execution(parse_src):
    code = """
    tree Combat {
        sequence [isReady(), !isStunned()] {
            action: attack()
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()

    ns = {}
    exec(py_code, ns)
    CombatTree = ns["CombatBehaviorTree"]
    CombatStub = ns["CombatContextStub"]

    ctx = CombatStub()
    ctx.isReady = lambda: True
    ctx.isStunned = lambda: False
    ctx.attack = lambda: Status.SUCCESS

    tree = CombatTree(ctx)
    assert tree.tick() == Status.SUCCESS

    ctx.isReady = lambda: False
    tree2 = CombatTree(ctx)
    assert tree2.tick() == Status.FAILURE

    ctx.isReady = lambda: True
    ctx.isStunned = lambda: True
    tree3 = CombatTree(ctx)
    assert tree3.tick() == Status.FAILURE

def test_time_decorators_execution(parse_src):
    import time
    code = """
    tree TimedTest {
        sequence {
            decorator: timeout(0.05) {
                action: waitForever()
            }
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()

    ns = {}
    exec(py_code, ns)
    tree_cls = ns["TimedTestBehaviorTree"]
    stub_cls = ns["TimedTestContextStub"]

    ctx = stub_cls()
    ctx.waitForever = lambda: Status.RUNNING

    tree = tree_cls(ctx)
    assert tree.tick() == Status.RUNNING
    time.sleep(0.06)
    assert tree.tick() == Status.FAILURE

def test_blackboard_execution_python(parse_src):
    code = """
    tree Patrol {
        sequence {
            action: findTarget("orc") -> $target
            condition: isAlive($target)
            action: attack($target, 50)
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()

    ns = {}
    exec(py_code, ns)
    PatrolTree = ns["PatrolBehaviorTree"]
    PatrolStub = ns["PatrolContextStub"]

    ctx = PatrolStub()
    ctx.findTarget = lambda race: {"id": 1, "race": race}
    ctx.isAlive = lambda enemy: enemy["id"] == 1
    ctx.attack = lambda enemy, dmg: Status.SUCCESS

    tree = PatrolTree(ctx)
    assert tree.tick() == Status.SUCCESS
    assert ctx.blackboard["target"] == {"id": 1, "race": "orc"}

def test_blackboard_transpilers_export(parse_src):
    from btscript.transpilers import JSONTranspiler, XMLTranspiler, MermaidTranspiler, AsciiTranspiler
    import json
    code = """
    tree Patrol {
        sequence {
            action: findTarget("orc") -> $target
            condition: isAlive($target)
            action: attack($target, 50)
        }
    }
    """
    ast, _ = parse_src(code)

    # JSON
    js = json.loads(JSONTranspiler(ast).transpile())
    act1 = js["trees"][0]["children"][0]["children"][0]
    assert act1["output_var"] == "target"

    # XML
    xml = XMLTranspiler(ast).transpile()
    assert 'output="$target"' in xml

    # Mermaid
    mermaid = MermaidTranspiler(ast).transpile()
    assert "➔ $target" in mermaid

    # ASCII
    ascii_out = AsciiTranspiler(ast).transpile()
    assert "-> $target" in ascii_out

def test_blackboard_execution_lua(parse_src):
    import subprocess, tempfile, os, shutil
    if not shutil.which("lua"):
        return
    code = """
    tree Patrol {
        sequence {
            action: findTarget("orc") -> $target
            condition: isAlive($target)
            action: attack($target, 50)
        }
    }
    """
    ast, dirs = parse_src(code)
    lua_code = LuaTranspiler(ast, directive=dirs).transpile()

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
        f.write(lua_code)
        lua_path = f.name

    runner = f"""
    package.path = 'btscript/runtimes/lua/?.lua;runtimes/lua/?.lua;' .. package.path
    local mod = dofile('{lua_path}')
    local ctx = {{
        findTarget = function(self, race) return {{ id = 42, race = race }} end,
        isAlive = function(self, enemy) return enemy.id == 42 end,
        attack = function(self, enemy, dmg)
            assert(enemy.id == 42)
            assert(dmg == 50)
            return 'SUCCESS'
        end,
    }}
    local tree = mod.PatrolBehaviorTree.new(ctx)
    local st = tree:tick()
    assert(st == 'SUCCESS')
    assert(ctx.blackboard.target.id == 42)
    assert(ctx.blackboard.target.race == 'orc')
    """
    res = subprocess.run(["lua", "-e", runner], capture_output=True, text=True)
    os.remove(lua_path)
    assert res.returncode == 0

def test_python_dt_simulation(parse_src):
    code = """
    tree TimedTest {
        sequence {
            decorator: timeout(0.05) {
                action: waitForever()
            }
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()

    ns = {}
    exec(py_code, ns)
    tree_cls = ns["TimedTestBehaviorTree"]
    stub_cls = ns["TimedTestContextStub"]

    ctx = stub_cls()
    ctx.waitForever = lambda *args: Status.RUNNING

    tree = tree_cls(ctx)
    # Simulation ticks with dt=0.02
    assert tree.tick(ctx, dt=0.02) == Status.RUNNING
    assert tree.tick(ctx, dt=0.02) == Status.RUNNING
    assert tree.tick(ctx, dt=0.02) == Status.FAILURE  # 0.06 > 0.05

def test_lua_dt_simulation(parse_src):
    import subprocess, tempfile, os, shutil
    if not shutil.which("lua"):
        return
    code = """
    tree TimedTest {
        sequence {
            decorator: timeout(0.05) {
                action: waitForever()
            }
        }
    }
    """
    ast, dirs = parse_src(code)
    lua_code = LuaTranspiler(ast, directive=dirs).transpile()

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
        f.write(lua_code)
        lua_path = f.name

    runner = f"""
    package.path = 'btscript/runtimes/lua/?.lua;runtimes/lua/?.lua;' .. package.path
    local mod = dofile('{lua_path}')
    local ctx = {{
        waitForever = function(self) return 'RUNNING' end,
    }}
    local tree = mod.TimedTestBehaviorTree.new(ctx)
    assert(tree:tick(ctx, 0.02) == 'RUNNING')
    assert(tree:tick(ctx, 0.02) == 'RUNNING')
    assert(tree:tick(ctx, 0.02) == 'FAILURE')
    """
    res = subprocess.run(["lua", "-e", runner], capture_output=True, text=True)
    os.remove(lua_path)
    assert res.returncode == 0

def test_blackboard_defaults_execution_python(parse_src):
    code = """
    tree Patrol {
        blackboard {
            $speed = 5.0,
            $target = "goblin"
        }
        sequence {
            action: attack($target, $speed)
        }
    }
    """
    ast, dirs = parse_src(code)
    py_code = PyTranspiler(ast, directive=dirs).transpile()

    ns = {}
    exec(py_code, ns)
    PatrolTree = ns["PatrolBehaviorTree"]
    PatrolStub = ns["PatrolContextStub"]

    # 1. Defaults applied when blackboard is empty
    ctx = PatrolStub()
    ctx.attack = lambda enemy, spd: Status.SUCCESS
    tree = PatrolTree(ctx)
    assert ctx.blackboard["speed"] == 5.0
    assert ctx.blackboard["target"] == "goblin"
    assert tree.tick() == Status.SUCCESS

    # 2. Existing caller blackboard values are preserved (not overwritten by defaults)
    ctx2 = PatrolStub()
    ctx2.blackboard = {"speed": 20.0}
    ctx2.attack = lambda enemy, spd: Status.SUCCESS
    tree2 = PatrolTree(ctx2)
    assert ctx2.blackboard["speed"] == 20.0
    assert ctx2.blackboard["target"] == "goblin"

def test_blackboard_defaults_execution_lua(parse_src):
    import subprocess, tempfile, os, shutil
    if not shutil.which("lua"):
        return
    code = """
    tree Patrol {
        blackboard {
            $speed = 5.0,
            $target = "goblin"
        }
        sequence {
            action: attack($target, $speed)
        }
    }
    """
    ast, dirs = parse_src(code)
    lua_code = LuaTranspiler(ast, directive=dirs).transpile()

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
        f.write(lua_code)
        lua_path = f.name

    runner = f"""
    package.path = 'btscript/runtimes/lua/?.lua;runtimes/lua/?.lua;' .. package.path
    local mod = dofile('{lua_path}')
    local ctx = {{
        attack = function(self, enemy, spd)
            assert(enemy == 'goblin')
            assert(spd == 5.0)
            return 'SUCCESS'
        end
    }}
    local tree = mod.PatrolBehaviorTree.new(ctx)
    assert(ctx.blackboard.speed == 5.0)
    assert(ctx.blackboard.target == 'goblin')
    assert(tree:tick() == 'SUCCESS')

    -- Existing blackboard preserved
    local ctx2 = {{
        blackboard = {{ speed = 25.0 }},
        attack = function(self, enemy, spd) return 'SUCCESS' end
    }}
    local tree2 = mod.PatrolBehaviorTree.new(ctx2)
    assert(ctx2.blackboard.speed == 25.0)
    assert(ctx2.blackboard.target == 'goblin')
    """
    res = subprocess.run(["lua", "-e", runner], capture_output=True, text=True)
    os.remove(lua_path)
    assert res.returncode == 0

def test_blackboard_defaults_export_targets(parse_src):
    from btscript.transpilers import JSONTranspiler, XMLTranspiler, AsciiTranspiler
    import json
    code = """
    tree Patrol {
        blackboard {
            $speed = 5.0,
            $target = "goblin"
        }
        sequence {
            action: attack($target, $speed)
        }
    }
    """
    ast, _ = parse_src(code)

    # JSON
    js = json.loads(JSONTranspiler(ast).transpile())
    assert js["trees"][0]["blackboard"]["speed"] == "5.0"
    assert js["trees"][0]["blackboard"]["target"] == '"goblin"'

    # XML
    xml = XMLTranspiler(ast).transpile()
    assert "<Blackboard>" in xml
    assert 'name="speed"' in xml

    # ASCII
    ascii_out = AsciiTranspiler(ast).transpile()
    assert "[bb: " in ascii_out
    assert "$speed=5.0" in ascii_out

    # Mermaid
    from btscript.transpilers import MermaidTranspiler
    mermaid = MermaidTranspiler(ast).transpile()
    assert "[bb: " in mermaid
    assert "$speed=5.0" in mermaid


def test_rust_transpiler_basic(parse_src):
    from btscript.transpilers import RustTranspiler
    code = """
    tree PatrolBot {
        stateful sequence {
            condition: isAlert()
            action: moveTo(10.5, 20.0)
        }
    }
    """
    ast, dirs = parse_src(code)
    rust_code = RustTranspiler(ast, directive=dirs).transpile()

    assert "pub fn build_patrol_bot() -> Box<dyn BehaviourNode>" in rust_code
    assert "Box::new(Sequence::new(" in rust_code
    assert "true," in rust_code  # stateful
    assert "pub trait PatrolBotContext" in rust_code
    assert "fn is_alert(&mut self) -> bool;" in rust_code
    assert "fn move_to(&mut self, arg1: f64, arg2: f64) -> Status;" in rust_code
    assert "pub struct MockPatrolBotContext;" in rust_code






