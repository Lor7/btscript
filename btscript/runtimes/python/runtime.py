"""
runtime.py: Clean and readable Behavior Tree engine for BTScript.
Provides core status codes, composites, leaf wrappers, decorators,
blackboard accessors, and simulation time (dt) support.

Author: Lorenzo (Lor7)
License: MIT
"""

import enum
import time


# ======================================================================
# Status Enumeration
# ======================================================================

class Status(enum.Enum):
    """Execution status returned by behavior tree node ticks."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


# ======================================================================
# Base Node Interface
# ======================================================================

class Node:
    """Base interface for all executable behavior tree nodes."""
    def tick(self, ctx, dt = None) -> Status:
        raise NotImplementedError


# ======================================================================
# Composites: Sequence
# ======================================================================

class Sequence(Node):
    """
    Executes children in order.
    Succeeds only if ALL children succeed; fails immediately if ANY child fails.
    If memory='stateful', resumes from the currently RUNNING child on the next tick.
    """
    def __init__(self, children, memory="stateless"):
        self.children = children
        self.is_stateful = (memory == "stateful" or memory is True)
        self.running_idx = 0
    
    def tick(self, ctx, dt = None) -> Status:
        # Resume from running child if stateful, otherwise start from first child
        start_idx = self.running_idx if self.is_stateful else 0

        for i in range(start_idx, len(self.children)):
            status = self.children[i].tick(ctx, dt)

            if status == Status.RUNNING:
                if self.is_stateful:
                    self.running_idx = i
                return Status.RUNNING

            elif status != Status.SUCCESS:
                self.reset()
                return status

        self.reset()
        return Status.SUCCESS

    def reset(self):
        """Resets running state and propagates to child nodes."""
        self.running_idx = 0
        for child in self.children:
            if hasattr(child, "reset"):
                child.reset()


# ======================================================================
# Composites: Selector (Fallback)
# ======================================================================

class Selector(Node):
    """
    Executes children as fallback options.
    Succeeds if ANY child succeeds; fails only if ALL children fail.
    If memory='stateful', resumes from the currently RUNNING child on the next tick.
    """
    def __init__(self, children, memory="stateless"):
        self.children = children
        self.is_stateful = (memory == "stateful" or memory is True)
        self.running_idx = 0
    
    def tick(self, ctx, dt = None) -> Status:
        start_idx = self.running_idx if self.is_stateful else 0

        for i in range(start_idx, len(self.children)):
            status = self.children[i].tick(ctx, dt)

            if status == Status.RUNNING:
                if self.is_stateful:
                    self.running_idx = i
                return Status.RUNNING

            elif status != Status.FAILURE:
                self.reset()
                return status

        self.reset()
        return Status.FAILURE

    def reset(self):
        self.running_idx = 0
        for child in self.children:
            if hasattr(child, "reset"):
                child.reset()


# ======================================================================
# Composites: Parallel
# ======================================================================

class Parallel(Node):
    """
    Executes all children concurrently each tick.
    Fails if any child fails. Returns RUNNING if any child is running.
    """
    def __init__(self, children, memory="stateless"):
        self.children = children
        self.is_stateful = (memory == "stateful" or memory is True)
        self.completed = set()

    def tick(self, ctx, dt = None) -> Status:
        statuses = []
        for i, child in enumerate(self.children):
            if self.is_stateful and i in self.completed:
                continue

            st = child.tick(ctx, dt)
            statuses.append(st)

            if self.is_stateful and st == Status.SUCCESS:
                self.completed.add(i)

        if any(r == Status.FAILURE for r in statuses):
            self.reset()
            return Status.FAILURE

        if any(r == Status.RUNNING for r in statuses) or (self.is_stateful and len(self.completed) < len(self.children)):
            return Status.RUNNING

        self.reset()
        return Status.SUCCESS

    def reset(self):
        self.completed.clear()
        for child in self.children:
            if hasattr(child, "reset"):
                child.reset()


# ======================================================================
# Leaves: Action & Condition
# ======================================================================

class Action(Node):
    """Wraps an executable task function. Adapts return values to Status codes."""
    def __init__(self, fn):
        self.fn = fn

    def tick(self, ctx, dt = None) -> Status:
        try:
            res = self.fn(ctx, dt)
        except TypeError:
            res = self.fn(ctx)

        if res is False or res == Status.FAILURE:
            return Status.FAILURE
        elif res == Status.RUNNING:
            return Status.RUNNING
        return Status.SUCCESS


class Condition(Node):
    """Wraps a boolean guard function. Returns SUCCESS if truthy, FAILURE if falsy."""
    def __init__(self, fn):
        self.fn = fn

    def tick(self, ctx, dt = None) -> Status:
        try:
            res = self.fn(ctx, dt)
        except TypeError:
            res = self.fn(ctx)

        return Status.SUCCESS if res else Status.FAILURE


# ======================================================================
# Decorator: Inverter, Modifiers & Time Triggers
# ======================================================================

class Decorator(Node):
    """
    Wraps a single child node to modify its execution policy.
    Supports inverters, forced outcomes, repeats, retries, and time triggers.
    Supports both decoupled simulation time (dt) and realtime clock (time.monotonic).
    """
    def __init__(self, prop, child, count = 1):
        self.prop = prop
        self.child = child
        self.count = float(count)
        self.start_time = None
        self.last_run_time = None
        self.elapsed_time = 0.0
        self.cooldown_remaining = 0.0

    def reset(self):
        self.start_time = None
        self.last_run_time = None
        self.elapsed_time = 0.0
        self.cooldown_remaining = 0.0
        if hasattr(self.child, "reset"):
            self.child.reset()

    def tick(self, ctx, dt = None) -> Status:
        now = time.monotonic()

        # Invert success and failure (leave RUNNING untouched)
        if self.prop == "inverter":
            status = self.child.tick(ctx, dt)
            if status == Status.FAILURE: return Status.SUCCESS
            elif status == Status.SUCCESS: return Status.FAILURE
            return status

        # Force outcome to SUCCESS unless RUNNING
        elif self.prop == "force_success":
            status = self.child.tick(ctx, dt)
            if status != Status.RUNNING: return Status.SUCCESS
            return status

        # Force outcome to FAILURE unless RUNNING
        elif self.prop == "force_failure":
            status = self.child.tick(ctx, dt)
            if status != Status.RUNNING: return Status.FAILURE
            return status

        # Repeat execution N times per tick
        elif self.prop == "repeat":
            for _ in range(int(self.count)):
                status = self.child.tick(ctx, dt)
                if status == Status.RUNNING: return Status.RUNNING
                if status == Status.FAILURE: return Status.FAILURE
            return Status.SUCCESS

        # Retry execution up to N times upon failure
        elif self.prop == "retry":
            for _ in range(int(self.count)):
                status = self.child.tick(ctx, dt)
                if status == Status.SUCCESS: return Status.SUCCESS
                if status == Status.RUNNING: return Status.RUNNING
            return Status.FAILURE

        # Timeout: fails if child remains RUNNING longer than count seconds
        elif self.prop == "timeout":
            if dt is not None:
                self.elapsed_time += dt
                if self.elapsed_time > self.count:
                    self.elapsed_time = 0.0
                    return Status.FAILURE
            else:
                if self.start_time is None:
                    self.start_time = now
                if (now - self.start_time) > self.count:
                    self.start_time = None
                    return Status.FAILURE

            status = self.child.tick(ctx, dt)
            if status != Status.RUNNING:
                self.start_time = None
                self.elapsed_time = 0.0
            return status

        # Delay: stays RUNNING until count seconds elapse, then executes child
        elif self.prop == "delay":
            if dt is not None:
                self.elapsed_time += dt
                if self.elapsed_time < self.count:
                    return Status.RUNNING
                self.elapsed_time = 0.0
                return self.child.tick(ctx, dt)
            else:
                if self.start_time is None:
                    self.start_time = now
                if (now - self.start_time) < self.count:
                    return Status.RUNNING
                self.start_time = None
                return self.child.tick(ctx, dt)

        # Cooldown: prevents re-execution for count seconds after running
        elif self.prop == "cooldown":
            if dt is not None:
                if self.cooldown_remaining > 0:
                    self.cooldown_remaining -= dt
                    return Status.FAILURE
                status = self.child.tick(ctx, dt)
                if status != Status.RUNNING:
                    self.cooldown_remaining = self.count
                return status
            else:
                if self.last_run_time is not None and (now - self.last_run_time) < self.count:
                    return Status.FAILURE
                status = self.child.tick(ctx, dt)
                if status != Status.RUNNING:
                    self.last_run_time = now
                return status
        
        return self.child.tick(ctx, dt)


# ======================================================================
# Blackboard Memory Helpers
# ======================================================================

def write_bb(ctx, var_name: str, val) -> Status:
    """
    Writes a value to the context blackboard dict.
    Returns appropriate Status based on the written value.
    """
    if not hasattr(ctx, "blackboard") or ctx.blackboard is None:
        ctx.blackboard = {}

    ctx.blackboard[var_name] = val

    if val in (False, None) or val == Status.FAILURE:
        return Status.FAILURE
    elif val == Status.RUNNING:
        return Status.RUNNING
    return Status.SUCCESS


def get_bb(ctx, var_name: str, default = None):
    """Safely retrieves a value from the context blackboard."""
    if hasattr(ctx, "blackboard") and ctx.blackboard is not None:
        return ctx.blackboard.get(var_name, default)
    return default


# ======================================================================
# Subtree Wrapper
# ======================================================================

class Subtree(Node):
    """Wraps an instantiated subtree to tick it within another tree."""
    def __init__(self, tree_instance):
        self.tree = tree_instance

    def tick(self, ctx, dt = None) -> Status:
        return self.tree.tick(ctx, dt)