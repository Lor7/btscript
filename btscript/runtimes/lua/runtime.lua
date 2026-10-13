-- runtime.lua: Clean and readable Behavior Tree engine for BTScript
-- Author: Lorenzo (Lor7)
-- License: MIT
local M = {}

M.Status = {
    SUCCESS = "SUCCESS",
    FAILURE = "FAILURE",
    RUNNING = "RUNNING"
}

-- Helper to make a node class with a constructor and tick function
local function create_node(tick_func)
    local Node = {}
    Node.__index = Node
    Node.tick = tick_func

    function Node:reset()
        self.running_idx = 1
        self.completed = nil
        if self.children then
            for _, child in ipairs(self.children) do
                if child.reset then child:reset() end
            end
        end
    end

    -- Makes the class callable directly: Sequence({ ... }, memory) or Action(fn)
    return setmetatable(Node, {
        __call = function(_, data, memory)
            if type(data) == "function" then
                return setmetatable({ fn = data }, Node)
            else
                local node_inst = setmetatable({
                    children = data or {},
                    is_stateful = (memory == "stateful" or memory == true),
                    running_idx = 1
                }, Node)
                return node_inst
            end
        end
    })
end

-- Sequence: fails if any child fails, succeeds if all succeed
M.Sequence = create_node(function(self, ctx, dt)
    local start_idx = self.is_stateful and self.running_idx or 1
    for i = start_idx, #self.children do
        local status = self.children[i]:tick(ctx, dt)
        if status == M.Status.RUNNING then
            if self.is_stateful then
                self.running_idx = i
            end
            return M.Status.RUNNING
        elseif status ~= M.Status.SUCCESS then
            self:reset()
            return status
        end
    end
    self:reset()
    return M.Status.SUCCESS
end)

-- Selector: succeeds if any child succeeds, fails if all fail
M.Selector = create_node(function(self, ctx, dt)
    local start_idx = self.is_stateful and self.running_idx or 1
    for i = start_idx, #self.children do
        local status = self.children[i]:tick(ctx, dt)
        if status == M.Status.RUNNING then
            if self.is_stateful then
                self.running_idx = i
            end
            return M.Status.RUNNING
        elseif status ~= M.Status.FAILURE then
            self:reset()
            return status
        end
    end
    self:reset()
    return M.Status.FAILURE
end)

-- Parallel: runs all children; fails if any fail
M.Parallel = create_node(function(self, ctx, dt)
    if self.is_stateful and not self.completed then
        self.completed = {}
    end
    local any_running = false
    local completed_count = 0
    for i, child in ipairs(self.children) do
        if self.is_stateful and self.completed[i] then
            completed_count = completed_count + 1
        else
            local status = child:tick(ctx, dt)
            if status == M.Status.FAILURE then
                self:reset()
                return M.Status.FAILURE
            elseif status == M.Status.RUNNING then
                any_running = true
            elseif status == M.Status.SUCCESS then
                if self.is_stateful then
                    self.completed[i] = true
                    completed_count = completed_count + 1
                end
            end
        end
    end
    if any_running or (self.is_stateful and completed_count < #self.children) then
        return M.Status.RUNNING
    end
    self:reset()
    return M.Status.SUCCESS
end)

-- Action: wraps a task function
M.Action = create_node(function(self, ctx, dt)
    local res = self.fn(ctx, dt)
    if res == false or res == M.Status.FAILURE then
        return M.Status.FAILURE
    elseif res == M.Status.RUNNING then
        return M.Status.RUNNING
    end
    return M.Status.SUCCESS
end)

-- Condition: wraps a boolean predicate function
M.Condition = create_node(function(self, ctx, dt)
    local res = self.fn(ctx, dt)
    if res then
        return M.Status.SUCCESS
    else
        return M.Status.FAILURE
    end
end)

-- Decorator: wraps a single child node
local Decorator = {}
Decorator.__index = Decorator

function Decorator.new(prop, child, count)
    return setmetatable({
        prop = prop,
        child = child,
        count = tonumber(count) or 1,
        start_time = nil,
        last_run_time = nil,
        elapsed_time = 0.0,
        cooldown_remaining = 0.0
    }, Decorator)
end

function Decorator:tick(ctx, dt)
    if self.prop == "inverter" then
        local status = self.child:tick(ctx, dt)
        if status == M.Status.SUCCESS then return M.Status.FAILURE end
        if status == M.Status.FAILURE then return M.Status.SUCCESS end
        return status

    elseif self.prop == "force_success" then
        local status = self.child:tick(ctx, dt)
        if status ~= M.Status.RUNNING then return M.Status.SUCCESS end
        return status

    elseif self.prop == "force_failure" then
        local status = self.child:tick(ctx, dt)
        if status ~= M.Status.RUNNING then return M.Status.FAILURE end
        return status

    elseif self.prop == "repeat" then
        for _ = 1, self.count do
            local status = self.child:tick(ctx, dt)
            if status == M.Status.RUNNING then return M.Status.RUNNING end
            if status == M.Status.FAILURE then return M.Status.FAILURE end
        end
        return M.Status.SUCCESS

    elseif self.prop == "retry" then
        for _ = 1, self.count do
            local status = self.child:tick(ctx, dt)
            if status == M.Status.SUCCESS then return M.Status.SUCCESS end
            if status == M.Status.RUNNING then return M.Status.RUNNING end
        end
        return M.Status.FAILURE
    
    elseif self.prop == "timeout" then
        if dt then
            self.elapsed_time = self.elapsed_time + dt
            if self.elapsed_time > self.count then
                self.elapsed_time = 0.0
                return M.Status.FAILURE
            end
        else
            local now = os.clock()
            if not self.start_time then self.start_time = now end
            if now - self.start_time > self.count then
                self.start_time = nil
                return M.Status.FAILURE
            end
        end
        local status = self.child:tick(ctx, dt)
        if status ~= M.Status.RUNNING then
            self.start_time = nil
            self.elapsed_time = 0.0
        end
        return status
    
    elseif self.prop == "delay" then
        if dt then
            self.elapsed_time = self.elapsed_time + dt
            if self.elapsed_time < self.count then
                return M.Status.RUNNING
            end
            self.elapsed_time = 0.0
            return self.child:tick(ctx, dt)
        else
            local now = os.clock()
            if not self.start_time then self.start_time = now end
            if now - self.start_time < self.count then
                return M.Status.RUNNING
            end
            self.start_time = nil
            return self.child:tick(ctx, dt)
        end

    elseif self.prop == "cooldown" then
        if dt then
            if self.cooldown_remaining > 0 then
                self.cooldown_remaining = self.cooldown_remaining - dt
                return M.Status.FAILURE
            end
            local status = self.child:tick(ctx, dt)
            if status ~= M.Status.RUNNING then
                self.cooldown_remaining = self.count
            end
            return status
        else
            local now = os.clock()
            if self.last_run_time and (now - self.last_run_time < self.count) then
                return M.Status.FAILURE
            end
            local status = self.child:tick(ctx, dt)
            if status ~= M.Status.RUNNING then
                self.last_run_time = now
            end
            return status
        end
    end

    return self.child:tick(ctx, dt)
end

function Decorator:reset()
    self.start_time = nil
    self.last_run_time = nil
    self.elapsed_time = 0.0
    self.cooldown_remaining = 0.0
    if self.child and self.child.reset then
        self.child:reset()
    end
end

M.Decorator = setmetatable(Decorator, {
    __call = function(_, prop, child, count)
        return Decorator.new(prop, child, count)
    end
})

function M.write_bb(ctx, var_name, val)
    if not ctx.blackboard then ctx.blackboard = {} end
    ctx.blackboard[var_name] = val
    if val == nil or val == false or val == M.Status.FAILURE then
        return M.Status.FAILURE
    elseif val == M.Status.RUNNING then
        return M.Status.RUNNING
    end
    return M.Status.SUCCESS
end

function M.get_bb(ctx, var_name)
    if ctx and ctx.blackboard then
        return ctx.blackboard[var_name]
    end
    return nil
end

return M