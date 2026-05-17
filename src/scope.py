from error import *

from convert import MemConverter

from memory import Memory, MemoryType, MemoryBlock
from value_objects import TypeObject, ValueObject

# Scope
# Manages the lifecycle and storage representation of runtime objects
# within an execution scope.
#
# To optimize performance, variables are stored by default as high-level
# `value objects` containing values and metadata. If an object's memory
# address is requested (e.g., during address-of operations), it is
# lazily converted into a byte-aligned `memory block`. This deferred
# materialization minimizes the performance overhead of raw memory
# emulation.


class ScopeVar:
    def __init__(self,
                 var_type: TypeObject,
                 value: ValueObject | None,
                 block_id: int | None) -> None:
        assert (value is None) != (block_id is None)

        self.var_type = var_type
        self.value = value
        self.block_id = block_id


class ScopeFrame:
    def __init__(self) -> None:
        self.vars: dict[str, ScopeVar] = {}


class Scope:
    def __init__(self, mem: Memory) -> None:
        self.mem = mem
        self.frames: list[ScopeFrame] = [ScopeFrame()]

    def push_var(self, name: str, var: ScopeVar) -> None | Error:
        if name in self.frames[-1].vars:
            return Error()

        if var.block_id is None:
            result: None | Error = self.mem.sim_alloc(
                MemoryType.stack,
                var.var_type.size
            )

            if isinstance(result, Error):
                return result

        self.frames[-1].vars[name] = var
        return None

    def push_frame(self) -> None:
        self.frames.append(ScopeFrame())

    def push(self) -> None:
        self.push_frame()

    def pop_var(self, var: ScopeVar) -> None | Error:
        if var.block_id is None:
            self.mem.sim_dealloc(MemoryType.stack, var.var_type.size)
        else:
            return self.mem.dealloc(MemoryType.stack, var.block_id)

    def pop_frame(self) -> None | Error:
        frame = self.frames.pop()

        for var in frame.vars.values():
            result = self.pop_var(var)

            if isinstance(result, Error):
                return result

        return None

    def pop(self) -> None | Error:
        return self.pop_frame()

    def pop_all(self) -> None:
        for frame in self.frames:
            for var in frame.vars.values():
                self.pop_var(var)

    def declare(self,
                name: str,
                var_type: TypeObject,
                value: ValueObject | None,
                block_id: int | None = None) -> None | Error:
        return self.push_var(name, ScopeVar(var_type, value, block_id))

    def lookup(self, name: str) -> ScopeVar | Error:
        for i in range(len(self.frames) - 1, -1, -1):
            if name in self.frames[i].vars:
                return self.frames[i].vars[name]

        return Error()

    def promote(self, name: str) -> int | Error:

        var: ScopeVar | Error = self.lookup(name)
        if isinstance(var, Error):
            return Error()

        if var.block_id is not None:
            return var.block_id

        assert var.value is not None

        mem_block: MemoryBlock = MemConverter().to_mem_block(var.value)
        assert var.var_type.size == mem_block.size()

        block_id: int | Error = self.mem.promote(
            MemoryType.stack,
            mem_block
        )

        if isinstance(block_id, Error):
            return Error()

        var.value = None
        var.block_id = block_id

        return block_id

    def read(self, name: str) -> ValueObject | Error:
        from convert import MemConverter

        var: ScopeVar | Error = self.lookup(name)
        if isinstance(var, Error):
            return var

        if var.value is not None:
            return var.value

        assert var.block_id is not None

        block: MemoryBlock | Error = self.mem.get(var.block_id)
        if isinstance(block, Error):
            return block

        return MemConverter().from_mem_block(var.var_type, block)

    def write(self, name: str, value: ValueObject) -> None | Error:
        var: ScopeVar | Error = self.lookup(name)
        if isinstance(var, Error):
            return var

        if var.block_id is None:
            var.value = value
            return None

        block: MemoryBlock | Error = self.mem.get(var.block_id)
        if isinstance(block, Error):
            return block

        new_block: MemoryBlock = MemConverter().to_mem_block(value)
        return self.mem.set(var.block_id, new_block)


def test_scope() -> None:
    pass


if __name__ == "__main__":
    test_scope()
