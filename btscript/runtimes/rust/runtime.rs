#![allow(dead_code)]
#![allow(unused_imports)]

use std::any::Any;
use std::collections::{HashMap, HashSet};
use std::time::Instant;

// ======================================================================
// Blackboard & Execution Context
// ======================================================================

#[derive(Default)]
pub struct Blackboard {
    storage: HashMap<String, Box<dyn Any>>,
}

impl Blackboard {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set<T: 'static>(&mut self, key: &str, value: T) {
        self.storage.insert(key.to_string(), Box::new(value));
    }

    pub fn get<T: 'static>(&self, key: &str) -> Option<&T> {
        self.storage.get(key)?.downcast_ref::<T>()
    }

    pub fn get_mut<T: 'static>(&mut self, key: &str) -> Option<&mut T> {
        self.storage.get_mut(key)?.downcast_mut::<T>()
    }

    pub fn contains(&self, key: &str) -> bool {
        self.storage.contains_key(key)
    }

    pub fn remove(&mut self, key: &str) -> bool {
        self.storage.remove(key).is_some()
    }
}

pub struct Context {
    pub blackboard: Blackboard,
}

impl Context {
    pub fn new() -> Self {
        Self {
            blackboard: Blackboard::new(),
        }
    }
}

impl Default for Context {
    fn default() -> Self {
        Self::new()
    }
}

// ======================================================================
// Status & Node Trait
// ======================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Success,
    Failure,
    Running,
}

pub trait BehaviourNode {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status;
    fn reset(&mut self) {}
}

// ======================================================================
// Composites: Sequence
// ======================================================================

pub struct Sequence {
    pub children: Vec<Box<dyn BehaviourNode>>,
    pub is_stateful: bool,
    pub running_idx: usize,
}

impl Sequence {
    pub fn new(children: Vec<Box<dyn BehaviourNode>>, is_stateful: bool) -> Self {
        Self {
            children,
            is_stateful,
            running_idx: 0,
        }
    }
}

impl BehaviourNode for Sequence {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        let start = if self.is_stateful { self.running_idx } else { 0 };

        for i in start..self.children.len() {
            let status = self.children[i].tick(ctx, dt);
            match status {
                Status::Running => {
                    if self.is_stateful {
                        self.running_idx = i;
                    }
                    return Status::Running;
                }
                Status::Failure => {
                    self.reset();
                    return Status::Failure;
                }
                Status::Success => continue,
            }
        }

        self.reset();
        Status::Success
    }

    fn reset(&mut self) {
        self.running_idx = 0;
        for child in &mut self.children {
            child.reset();
        }
    }
}

// ======================================================================
// Composites: Selector (Fallback)
// ======================================================================

pub struct Selector {
    pub children: Vec<Box<dyn BehaviourNode>>,
    pub is_stateful: bool,
    pub running_idx: usize,
}

impl Selector {
    pub fn new(children: Vec<Box<dyn BehaviourNode>>, is_stateful: bool) -> Self {
        Self {
            children,
            is_stateful,
            running_idx: 0,
        }
    }
}

impl BehaviourNode for Selector {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        let start = if self.is_stateful { self.running_idx } else { 0 };

        for i in start..self.children.len() {
            let status = self.children[i].tick(ctx, dt);
            match status {
                Status::Running => {
                    if self.is_stateful {
                        self.running_idx = i;
                    }
                    return Status::Running;
                }
                Status::Success => {
                    self.reset();
                    return Status::Success;
                }
                Status::Failure => continue,
            }
        }

        self.reset();
        Status::Failure
    }

    fn reset(&mut self) {
        self.running_idx = 0;
        for child in &mut self.children {
            child.reset();
        }
    }
}

// ======================================================================
// Composites: Parallel
// ======================================================================

pub struct Parallel {
    pub children: Vec<Box<dyn BehaviourNode>>,
    pub is_stateful: bool,
    pub completed: HashSet<usize>,
}

impl Parallel {
    pub fn new(children: Vec<Box<dyn BehaviourNode>>, is_stateful: bool) -> Self {
        Self {
            children,
            is_stateful,
            completed: HashSet::new(),
        }
    }
}

impl BehaviourNode for Parallel {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        let mut statuses = Vec::with_capacity(self.children.len());

        for i in 0..self.children.len() {
            if self.is_stateful && self.completed.contains(&i) {
                continue;
            }

            let status = self.children[i].tick(ctx, dt);
            statuses.push(status);

            if self.is_stateful && status == Status::Success {
                self.completed.insert(i);
            }
        }

        // If any child failed, fail immediately and reset
        if statuses.iter().any(|&s| s == Status::Failure) {
            self.reset();
            return Status::Failure;
        }

        // If any child is still running, or not all stateful children succeeded
        if statuses.iter().any(|&s| s == Status::Running)
            || (self.is_stateful && self.completed.len() < self.children.len())
        {
            return Status::Running;
        }

        self.reset();
        Status::Success
    }

    fn reset(&mut self) {
        self.completed.clear();
        for child in &mut self.children {
            child.reset();
        }
    }
}

// ======================================================================
// Leaves: Action & Condition
// ======================================================================

pub struct Action<F> {
    func: F,
}

impl<F> Action<F>
where
    F: FnMut(&mut Context, Option<f64>) -> Status,
{
    pub fn new(func: F) -> Self {
        Self { func }
    }
}

impl<F> BehaviourNode for Action<F>
where
    F: FnMut(&mut Context, Option<f64>) -> Status,
{
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        (self.func)(ctx, dt)
    }
}

pub struct Condition<F> {
    func: F,
}

impl<F> Condition<F>
where
    F: FnMut(&mut Context) -> bool,
{
    pub fn new(func: F) -> Self {
        Self { func }
    }
}

impl<F> BehaviourNode for Condition<F>
where
    F: FnMut(&mut Context) -> bool,
{
    fn tick(&mut self, ctx: &mut Context, _dt: Option<f64>) -> Status {
        if (self.func)(ctx) {
            Status::Success
        } else {
            Status::Failure
        }
    }
}

// ======================================================================
// Decorators
// ======================================================================

pub struct Invert {
    pub child: Box<dyn BehaviourNode>,
}

impl Invert {
    pub fn new(child: Box<dyn BehaviourNode>) -> Self {
        Self { child }
    }
}

impl BehaviourNode for Invert {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        match self.child.tick(ctx, dt) {
            Status::Success => Status::Failure,
            Status::Failure => Status::Success,
            Status::Running => Status::Running,
        }
    }

    fn reset(&mut self) {
        self.child.reset();
    }
}

pub struct Repeat {
    pub child: Box<dyn BehaviourNode>,
    pub count: Option<u32>,
    pub current: u32,
}

impl Repeat {
    pub fn new(child: Box<dyn BehaviourNode>, count: Option<u32>) -> Self {
        Self {
            child,
            count,
            current: 0,
        }
    }
}

impl BehaviourNode for Repeat {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        loop {
            let status = self.child.tick(ctx, dt);
            match status {
                Status::Running => return Status::Running,
                Status::Failure => {
                    self.reset();
                    return Status::Failure;
                }
                Status::Success => {
                    self.current += 1;
                    if let Some(target) = self.count {
                        if self.current >= target {
                            self.reset();
                            return Status::Success;
                        }
                    }
                    self.child.reset();
                }
            }
        }
    }

    fn reset(&mut self) {
        self.current = 0;
        self.child.reset();
    }
}

pub struct Retry {
    pub child: Box<dyn BehaviourNode>,
    pub count: Option<u32>,
    pub current: u32,
}

impl Retry {
    pub fn new(child: Box<dyn BehaviourNode>, count: Option<u32>) -> Self {
        Self {
            child,
            count,
            current: 0,
        }
    }
}

impl BehaviourNode for Retry {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        let status = self.child.tick(ctx, dt);
        match status {
            Status::Running => Status::Running,
            Status::Failure => {
                self.current += 1;
                if let Some(target) = self.count {
                    if self.current >= target {
                        self.reset();
                        return Status::Failure;
                    }
                }
                self.child.reset();
                Status::Running
            }
            Status::Success => {
                self.reset();
                Status::Success
            }
        }
    }

    fn reset(&mut self) {
        self.current = 0;
        self.child.reset();
    }
}

pub struct Timeout {
    pub child: Box<dyn BehaviourNode>,
    pub duration: f64,
    pub elapsed: f64,
}

impl Timeout {
    pub fn new(child: Box<dyn BehaviourNode>, duration: f64) -> Self {
        Self {
            child,
            duration,
            elapsed: 0.0,
        }
    }
}

impl BehaviourNode for Timeout {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        self.elapsed += dt.unwrap_or(0.0);
        if self.elapsed > self.duration {
            self.reset();
            return Status::Failure;
        }

        let status = self.child.tick(ctx, dt);
        if status != Status::Running {
            self.reset();
        }
        status
    }

    fn reset(&mut self) {
        self.elapsed = 0.0;
        self.child.reset();
    }
}

pub struct Delay {
    pub child: Box<dyn BehaviourNode>,
    pub duration: f64,
    pub elapsed: f64,
}

impl Delay {
    pub fn new(child: Box<dyn BehaviourNode>, duration: f64) -> Self {
        Self {
            child,
            duration,
            elapsed: 0.0,
        }
    }
}

impl BehaviourNode for Delay {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        self.elapsed += dt.unwrap_or(0.0);
        if self.elapsed < self.duration {
            return Status::Running;
        }

        let status = self.child.tick(ctx, dt);
        if status != Status::Running {
            self.reset();
        }
        status
    }

    fn reset(&mut self) {
        self.elapsed = 0.0;
        self.child.reset();
    }
}

pub struct Cooldown {
    pub child: Box<dyn BehaviourNode>,
    pub duration: f64,
    pub cooldown_remaining: f64,
    pub last_run_time: Option<Instant>,
}

impl Cooldown {
    pub fn new(child: Box<dyn BehaviourNode>, duration: f64) -> Self {
        Self {
            child,
            duration,
            cooldown_remaining: 0.0,
            last_run_time: None,
        }
    }
}

impl BehaviourNode for Cooldown {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        if let Some(delta) = dt {
            // Simulation time mode (dt)
            if self.cooldown_remaining > 0.0 {
                self.cooldown_remaining -= delta;
                if self.cooldown_remaining > 0.0 {
                    return Status::Failure;
                }
            }
            let status = self.child.tick(ctx, dt);
            if status != Status::Running {
                self.cooldown_remaining = self.duration;
            }
            status
        } else {
            // Realtime clock mode (Instant)
            let now = Instant::now();
            if let Some(last) = self.last_run_time {
                if now.duration_since(last).as_secs_f64() < self.duration {
                    return Status::Failure;
                }
            }
            let status = self.child.tick(ctx, dt);
            if status != Status::Running {
                self.last_run_time = Some(now);
            }
            status
        }
    }

    fn reset(&mut self) {
        self.cooldown_remaining = 0.0;
        self.last_run_time = None;
        self.child.reset();
    }
}

pub struct ForceSuccess {
    pub child: Box<dyn BehaviourNode>,
}

impl ForceSuccess {
    pub fn new(child: Box<dyn BehaviourNode>) -> Self {
        Self { child }
    }
}

impl BehaviourNode for ForceSuccess {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        match self.child.tick(ctx, dt) {
            Status::Running => Status::Running,
            _ => Status::Success,
        }
    }

    fn reset(&mut self) {
        self.child.reset();
    }
}

pub struct ForceFailure {
    pub child: Box<dyn BehaviourNode>,
}

impl ForceFailure {
    pub fn new(child: Box<dyn BehaviourNode>) -> Self {
        Self { child }
    }
}

impl BehaviourNode for ForceFailure {
    fn tick(&mut self, ctx: &mut Context, dt: Option<f64>) -> Status {
        match self.child.tick(ctx, dt) {
            Status::Running => Status::Running,
            _ => Status::Failure,
        }
    }

    fn reset(&mut self) {
        self.child.reset();
    }
}

// ======================================================================
// Blackboard Helper Functions
// ======================================================================

pub fn write_bb<T: 'static>(ctx: &mut Context, key: &str, val: T) -> Status {
    ctx.blackboard.set(key, val);
    Status::Success
}

// ======================================================================
// Unit Tests
// ======================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_blackboard() {
        let mut bb = Blackboard::new();
        bb.set("speed", 4.5f64);
        bb.set("active", true);

        assert_eq!(bb.get::<f64>("speed"), Some(&4.5));
        assert_eq!(bb.get::<bool>("active"), Some(&true));
        assert_eq!(bb.get::<i32>("speed"), None);
    }

    #[test]
    fn test_stateful_sequence() {
        let mut ctx = Context::new();
        let mut count = 0;

        let a1 = Action::new(|_ctx, _| Status::Success);
        let a2 = Action::new(move |_ctx, _| {
            count += 1;
            if count == 1 {
                Status::Running
            } else {
                Status::Success
            }
        });

        let mut seq = Sequence::new(vec![Box::new(a1), Box::new(a2)], true);
        assert_eq!(seq.tick(&mut ctx, None), Status::Running);
        assert_eq!(seq.running_idx, 1);
        assert_eq!(seq.tick(&mut ctx, None), Status::Success);
        assert_eq!(seq.running_idx, 0);
    }

    #[test]
    fn test_parallel_stateful() {
        let mut ctx = Context::new();
        let mut runs = 0;

        let a1 = Action::new(|_ctx, _| Status::Success);
        let a2 = Action::new(move |_ctx, _| {
            runs += 1;
            if runs == 1 {
                Status::Running
            } else {
                Status::Success
            }
        });

        let mut par = Parallel::new(vec![Box::new(a1), Box::new(a2)], true);
        assert_eq!(par.tick(&mut ctx, None), Status::Running);
        assert!(par.completed.contains(&0));
        assert_eq!(par.tick(&mut ctx, None), Status::Success);
        assert_eq!(par.completed.len(), 0); // reset
    }

    #[test]
    fn test_cooldown_simulation_time() {
        let mut ctx = Context::new();
        let action = Action::new(|_ctx, _| Status::Success);
        let mut cd = Cooldown::new(Box::new(action), 2.0);

        // 1st tick: executes and triggers cooldown
        assert_eq!(cd.tick(&mut ctx, Some(0.1)), Status::Success);
        // 2nd tick: during cooldown, returns Failure
        assert_eq!(cd.tick(&mut ctx, Some(1.0)), Status::Failure);
        // 3rd tick: cooldown finishes (1.0 + 1.0 >= 2.0)
        assert_eq!(cd.tick(&mut ctx, Some(1.0)), Status::Success);
    }
}
