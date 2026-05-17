from enum import Enum

from error import *
from limits import *
from common import is_byte

# Memory Model
# Objects are represented as discrete blocks of raw bytes. A shadow
# memory layer tracks the initialization and accessibility of each
# byte to detect undefined behavior.
#
# A pointer is composed of block_id + offset, each represeting half
# of the pointer.

assert PTR_SIZE % 2 == 0
assert PTR_SIZE // 2 != 0

PTR_HALF_MAX_VALUE: int = (1 << (PTR_SIZE // 2 ) * CHAR_BIT_SIZE) - 1

BLOCK_ID_MAX: int = PTR_HALF_MAX_VALUE
BLOCK_OFFSET_MAX: int = PTR_HALF_MAX_VALUE


class MemoryType(Enum):
    data  = "data"
    stack = "stack"
    heap  = "heap"


class MemoryFlags(Enum):
    poison = 0x00
    mine   = 0x01
    clean  = 0x02


class MemoryBlock:
    def __init__(self, byte_size: int) -> None:
        self.data: bytearray = bytearray(byte_size)
        self.metadata: bytearray = bytearray(byte_size)

    def read(self, idx: int) -> int | Error:
        if not (-1 < idx < len(self.data)):
            return Error()

        if self.metadata[idx] == MemoryFlags.mine.value:
            return Error()

        if self.metadata[idx] == MemoryFlags.poison.value:
            return Error()

        return self.data[idx]

    def read_block(self, offset: int, byte_size: int) -> MemoryBlock:
        assert offset >= 0

        if offset + byte_size > self.size():
            return Error()

        result: MemoryBlock = MemoryBlock(byte_size)

        for i in range(byte_size):
            idx = offset + i

            result.data[i] = self.data[idx]
            result.metadata[i] = self.metadata[idx]

        return result

    def write(self, idx: int, byte: int) -> None | Error:
        assert is_byte(byte)

        if not (-1 < idx < len(self.data)):
            return Error()

        if self.metadata[idx] == MemoryFlags.mine.value:
            return Error()

        self.data[idx] = byte
        self.metadata[idx] = MemoryFlags.clean.value

        return None

    def write_block(self,
                    offset: int,
                    mem_block: MemoryBlock) -> None | Error:
        assert offset >= 0

        if offset + mem_block.size() > self.size():
            return Error()

        for i in range(mem_block.size()):
            idx = offset + i

            if self.has_mine(idx) and not mem_block.has_mine(i):
                return Error()

            self.data[idx] = mem_block.data[i]
            self.metadata[idx] = mem_block.metadata[i]

        return None

    def size(self) -> int:
        return len(self.data)

    # Read and write methods are mainly designed to detect
    # uninitialized memory and invalid pointer arithmetic.
    #
    # However, set_mine is designed to catch invalid pointer alignment,
    # obtaining address of struct gaps or padding.
    def set_mine(self, idx: int) -> None:
        self.metadata[idx] = MemoryFlags.mine.value

    def has_mine(self, idx: int) -> bool:
        return self.metadata[idx] == MemoryFlags.mine.value


class Memory:
    def __init__(self,
                 data_byte_size: int,
                 stack_byte_size: int,
                 heap_byte_size: int) -> None:

        assert data_byte_size >= 0
        assert stack_byte_size >= 0
        assert heap_byte_size >= 0

        self.mem_limits: dict[MemoryType, int] = {
            MemoryType.data:  data_byte_size,
            MemoryType.stack: stack_byte_size,
            MemoryType.heap:  heap_byte_size,
        }

        # NOTE: The memory block ID 0 is a placeholder for raw memory.
        # For example, `int *ptr = 0` is a valid pointer to address 0.
        self.next_id: int = 1
        self.blocks: dict[int, tuple[MemoryType, MemoryBlock]] = {}

    def alloc(self,
              mem_type: MemoryType,
              mem_size: int) -> int | Error:
        assert mem_size >= 0

        if self.mem_limits[mem_type] < mem_size:
            return Error()

        if self.next_id > BLOCK_ID_MAX:
            return Error()

        if mem_size > BLOCK_OFFSET_MAX:
            return Error()

        block_id = self.next_id
        self.blocks[block_id] = (mem_type, MemoryBlock(mem_size))

        self.mem_limits[mem_type] -= mem_size
        self.next_id += 1

        return block_id

    def dealloc(self,
                mem_type: MemoryType,
                block_id: int) -> None | Error:
        if block_id not in self.blocks:
            return Error()

        block_mem_type, _ = self.blocks[block_id]

        if block_mem_type != mem_type:
            return Error()

        _, block = self.blocks.pop(block_id)
        self.mem_limits[mem_type] += len(block.data)

        return None

    def promote(self,
                mem_type: MemoryType,
                mem_block: MemoryBlock) -> int | Error:
        if self.next_id > BLOCK_ID_MAX:
            return Error()

        block_id = self.next_id
        self.blocks[block_id] = (mem_type, mem_block)

        self.next_id += 1

        return block_id

    def sim_alloc(self,
                  mem_type: MemoryType,
                  mem_size: int) -> None | Error:
        assert mem_size >= 0

        if self.mem_limits[mem_type] < mem_size:
            return Error()

        self.mem_limits[mem_type] -= mem_size
        return None

    def sim_dealloc(self,
                    mem_type: MemoryType,
                    mem_size: int) -> None | Error:
        self.mem_limits[mem_type] += mem_size
        return None

    def get(self, block_id: int) -> MemoryBlock | Error:
        if block_id not in self.blocks:
            return Error()

        _, block = self.blocks[block_id]
        return block

    def set(self,
            block_id: int,
            new_block: MemoryBlock) -> None | Error:
        if block_id not in self.blocks:
            return Error()

        mem_type, old_block = self.blocks[block_id]

        if old_block.size() != new_block.size():
            return Error()

        self.blocks[block_id] = (mem_type, new_block)


def test_mem_block_write_success(mem_block: MemoryBlock,
                                 idx: int,
                                 value: int) -> None:
    assert is_byte(value)

    result: None | Error = mem_block.write(idx, value)
    assert not isinstance(result, Error)


def test_mem_block_write_failure(mem_block: MemoryBlock,
                                 idx: int,
                                 value: int) -> None:
    assert is_byte(value)

    result: None | Error = mem_block.write(idx, value)
    assert isinstance(result, Error)


def test_mem_block_read_success(mem_block: MemoryBlock,
                                idx: int,
                                expected: int) -> None:
    assert is_byte(expected)

    result: int | Error = mem_block.read(idx)
    assert not isinstance(result, Error)
    assert result == expected


def test_mem_block_read_failure(mem_block: MemoryBlock,
                                idx: int) -> None:
    result: int | Error = mem_block.read(idx)
    assert isinstance(result, Error)


def test_mem_block_read_write_success() -> None:
    # Test: Verify successful write and read of a single-byte memory
    #       block.
    mem_block = MemoryBlock(1)

    test_mem_block_write_success(mem_block, 0, 0xff)
    test_mem_block_read_success(mem_block, 0, 0xff)

    # Test: Verify data persistence across multiple read operations.
    mem_block = MemoryBlock(1)

    test_mem_block_write_success(mem_block, 0, 0xff)

    test_mem_block_read_success(mem_block, 0, 0xff)
    test_mem_block_read_success(mem_block, 0, 0xff)

    # Test: Verify that subsequent writes correctly update existing
    #       memory data.
    mem_block = MemoryBlock(1)

    test_mem_block_write_success(mem_block, 0, 0xff)
    test_mem_block_write_success(mem_block, 0, 0xfe)

    test_mem_block_read_success(mem_block, 0, 0xfe)

    # Test: Verify sequential write and read operations across
    #       multiple offsets.
    mem_block = MemoryBlock(4)

    test_mem_block_write_success(mem_block, 0, 0x00)
    test_mem_block_read_success(mem_block, 0, 0x00)

    test_mem_block_write_success(mem_block, 1, 0x01)
    test_mem_block_read_success(mem_block, 1, 0x01)

    test_mem_block_write_success(mem_block, 2, 0x02)
    test_mem_block_read_success(mem_block, 2, 0x02)

    test_mem_block_write_success(mem_block, 3, 0x03)
    test_mem_block_read_success(mem_block, 3, 0x03)

    # Test: Verify data integrity for multi-offset writes and reads
    #       in varying orders
    mem_block = MemoryBlock(4)

    test_mem_block_write_success(mem_block, 3, 0x00)
    test_mem_block_write_success(mem_block, 2, 0x01)
    test_mem_block_write_success(mem_block, 1, 0x02)
    test_mem_block_write_success(mem_block, 0, 0x03)

    test_mem_block_read_success(mem_block, 3, 0x00)
    test_mem_block_read_success(mem_block, 2, 0x01)
    test_mem_block_read_success(mem_block, 1, 0x02)
    test_mem_block_read_success(mem_block, 0, 0x03)

    test_mem_block_read_success(mem_block, 0, 0x03)
    test_mem_block_read_success(mem_block, 1, 0x02)
    test_mem_block_read_success(mem_block, 2, 0x01)
    test_mem_block_read_success(mem_block, 3, 0x00)


def test_mem_block_read_write_failure() -> None:
    # Test: Verify write failure for an index exceeding the allocated
    #       block size.
    mem_block = MemoryBlock(1)
    test_mem_block_write_failure(mem_block, 1, 0xff)

    # Test: Verify write failure for indices out-of-bounds memory
    #       offsets.
    mem_block = MemoryBlock(4)

    test_mem_block_write_failure(mem_block, -23, 0xff)
    test_mem_block_write_failure(mem_block, -1, 0xff)

    test_mem_block_write_success(mem_block, 0, 0xff)
    test_mem_block_write_success(mem_block, 1, 0xff)
    test_mem_block_write_success(mem_block, 2, 0xff)
    test_mem_block_write_success(mem_block, 3, 0xff)

    test_mem_block_write_failure(mem_block, 4, 0xff)
    test_mem_block_write_failure(mem_block, 23, 0xff)

    # Test: Verify read failure when accessing uninitialized memory.
    mem_block = MemoryBlock(1)
    test_mem_block_read_failure(mem_block, 0)

    # Test: Verify read failure on uninitialized memory prior to
    #       a valid write/read sequence.
    mem_block = MemoryBlock(1)
    test_mem_block_read_failure(mem_block, 0)

    test_mem_block_write_success(mem_block, 0, 0xff)
    test_mem_block_read_success(mem_block, 0, 0xff)

    # Test: Verify read failure across all indices of an uninitialized
    #       multi-byte block.
    mem_block = MemoryBlock(4)

    test_mem_block_read_failure(mem_block, 0)
    test_mem_block_read_failure(mem_block, 1)
    test_mem_block_read_failure(mem_block, 2)
    test_mem_block_read_failure(mem_block, 3)

    # Test: Verify read access validation for initialized,
    #       uninitialized, and out-of-bounds offsets.
    mem_block = MemoryBlock(4)

    test_mem_block_write_success(mem_block, 0, 0xff)
    test_mem_block_write_success(mem_block, 2, 0xff)

    test_mem_block_read_failure(mem_block, -23)
    test_mem_block_read_failure(mem_block, -1)

    test_mem_block_read_success(mem_block, 0, 0xff)
    test_mem_block_read_failure(mem_block, 1)
    test_mem_block_read_success(mem_block, 2, 0xff)
    test_mem_block_read_failure(mem_block, 3)

    test_mem_block_read_failure(mem_block, 4)
    test_mem_block_read_failure(mem_block, 23)


def test_mem_block_mine_success() -> None:
    # Test: Verify continued accessibility of unrestricted indices
    #       following a partial block restriction.
    mem_block = MemoryBlock(2)

    test_mem_block_write_success(mem_block, 0, 0x00)
    test_mem_block_write_success(mem_block, 1, 0x01)

    test_mem_block_read_success(mem_block, 0, 0x00)
    test_mem_block_read_success(mem_block, 1, 0x01)

    mem_block.set_mine(0)

    test_mem_block_write_success(mem_block, 1, 0xff)
    test_mem_block_read_success(mem_block, 1, 0xff)


def test_mem_block_mine_failure() -> None:
    # Test: Verify read and write access restriction of indices within
    #       a block.
    mem_block = MemoryBlock(1)
    mem_block.set_mine(0)

    test_mem_block_read_failure(mem_block, 0)
    test_mem_block_write_failure(mem_block, 0, 0xff)

    # Test: Verify access control enforcement for specific restricted
    #       and unrestricted indices in block.
    mem_block = MemoryBlock(4)
    mem_block.set_mine(0)
    mem_block.set_mine(3)

    test_mem_block_write_failure(mem_block, 0, 0xff)
    test_mem_block_write_failure(mem_block, 3, 0xff)

    test_mem_block_write_success(mem_block, 1, 0xff)
    test_mem_block_write_success(mem_block, 2, 0xff)

    test_mem_block_read_failure(mem_block, 0)
    test_mem_block_read_failure(mem_block, 3)

    test_mem_block_read_success(mem_block, 1, 0xff)
    test_mem_block_read_success(mem_block, 2, 0xff)

    # Test: Verify access revocation on a previously initialized index
    #       after setting a restriction.
    mem_block = MemoryBlock(1)

    test_mem_block_read_failure(mem_block, 0)

    test_mem_block_write_success(mem_block, 0, 0xff)
    test_mem_block_read_success(mem_block, 0, 0xff)

    mem_block.set_mine(0)

    test_mem_block_read_failure(mem_block, 0)

    test_mem_block_write_failure(mem_block, 0, 0xff)
    test_mem_block_read_failure(mem_block, 0)


def test_mem_create(mem_type: MemoryType, limit: int) -> Memory:
    mem_limits: dict[MemoryType, int] = {
        MemoryType.data:  0,
        MemoryType.stack: 0,
        MemoryType.heap:  0,
    }

    mem_limits[mem_type] = limit

    mem = Memory(
        mem_limits[MemoryType.data],
        mem_limits[MemoryType.stack],
        mem_limits[MemoryType.heap]
    )

    return mem


def test_unique_block_id(block_ids: list[int], block_id: int) -> None:
    for curr_block_id in block_ids:
        assert curr_block_id != block_id


def test_mem_get_success(mem: Memory,
                         byte_size: int,
                         block_id: int) -> None:
    block: MemoryBlock | Error = mem.get(block_id)
    assert not isinstance(block, Error)

    assert len(block.data) == byte_size
    assert len(block.metadata) == byte_size


def test_mem_get_failure(mem: Memory, block_id: int) -> None:
    block: MemoryBlock | Error = mem.get(block_id)
    assert isinstance(block, Error)


def test_mem_alloc_success(mem: Memory,
                           mem_type: MemoryType,
                           byte_size: int,
                           block_ids: list[int]) -> int:
    block_id: int | Error = mem.alloc(mem_type, byte_size)
    assert not isinstance(block_id, Error)

    test_unique_block_id(block_ids, block_id)
    block_ids.append(block_id)

    test_mem_get_success(mem, byte_size, block_id)
    return block_id


def test_mem_alloc_failure(mem: Memory,
                           mem_type: MemoryType,
                           byte_size: int) -> None:
    block_id: int | Error = mem.alloc(mem_type, byte_size)
    assert isinstance(block_id, Error)

    test_mem_get_failure(mem, block_id)
    return None


def test_mem_dealloc_success(mem: Memory,
                             mem_type: MemoryType,
                             block_id: int) -> None:
    result: None | Error = mem.dealloc(mem_type, block_id)
    assert not isinstance(result, Error)

    test_mem_get_failure(mem, block_id)


def test_mem_dealloc_failure(mem: Memory,
                             mem_type: MemoryType,
                             block_id: int) -> None:
    result: None | Error = mem.dealloc(mem_type, block_id)
    assert isinstance(result, Error)


def test_mem_alloc_dealloc_success(mem_type: MemoryType) -> None:
    LIMIT: int = 4096

    block_ids: list[int] = []
    mem: Memory = test_mem_create(mem_type, LIMIT)

    # Test: Verify capacity constant integrity.
    SMALL: int = 3
    HALF: int = LIMIT // 2

    assert LIMIT > 3 * SMALL
    assert LIMIT == HALF * 2

    # Test: Verify allocation and deallocation of a single byte.
    block_id = test_mem_alloc_success(mem, mem_type, 1, block_ids)
    test_mem_dealloc_success(mem, mem_type, block_id)

    # Test: Verify allocation and deallocation of maximum memory
    #       capacity.
    block_id = test_mem_alloc_success(mem, mem_type, LIMIT, block_ids)
    test_mem_dealloc_success(mem, mem_type, block_id)

    # Test: Verify LIFO deallocation order for two equal-sized blocks.
    block_id1 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)
    block_id2 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)

    test_mem_dealloc_success(mem, mem_type, block_id2)
    test_mem_dealloc_success(mem, mem_type, block_id1)

    # Test: Verify FIFO deallocation order for two equal-sized blocks.
    block_id1 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)
    block_id2 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)

    test_mem_dealloc_success(mem, mem_type, block_id1)
    test_mem_dealloc_success(mem, mem_type, block_id2)

    # Test: Verify memory reuse following deallocation of the initial
    #       block.
    block_id1 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)
    block_id2 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)

    test_mem_dealloc_success(mem, mem_type, block_id1)

    block_id3 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)

    test_mem_dealloc_success(mem, mem_type, block_id3)
    test_mem_dealloc_success(mem, mem_type, block_id2)

    # Test: Verify memory reuse following deallocation of the trailing
    #       block.
    block_id1 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)
    block_id2 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)

    test_mem_dealloc_success(mem, mem_type, block_id2)

    block_id3 = test_mem_alloc_success(mem, mem_type, HALF, block_ids)

    test_mem_dealloc_success(mem, mem_type, block_id3)
    test_mem_dealloc_success(mem, mem_type, block_id1)

    # Test: Verify exact byte allocation for non-even memory request
    #       sizes.
    block_id1 = test_mem_alloc_success(mem, mem_type, SMALL, block_ids)
    block_id2 = test_mem_alloc_success(mem, mem_type, SMALL, block_ids)
    block_id3 = test_mem_alloc_success(mem, mem_type, SMALL, block_ids)

    test_mem_dealloc_success(mem, mem_type, block_id3)
    test_mem_dealloc_success(mem, mem_type, block_id2)
    test_mem_dealloc_success(mem, mem_type, block_id1)


def test_mem_alloc_dealloc_failure(mem_type: MemoryType) -> None:
    LIMIT: int = 4096

    block_ids: list[int] = []
    mem: Memory = test_mem_create(mem_type, LIMIT)

    # Test: Verify double deallocation failure.
    block_id = test_mem_alloc_success(mem, mem_type, 1, block_ids)
    test_mem_dealloc_success(mem, mem_type, block_id)
    test_mem_dealloc_failure(mem, mem_type, block_id)

    # Test: Verify allocation failure upon memory exhaustion.
    block_id = test_mem_alloc_success(mem, mem_type, LIMIT, block_ids)
    test_mem_alloc_failure(mem, mem_type, 1)

    test_mem_dealloc_success(mem, mem_type, block_id)

    # Test: Verify allocation failure for requests exceeding limit.
    test_mem_alloc_failure(mem, mem_type, LIMIT + 1)

    # Test: Verify deallocation failure for invalid block ID.
    block_id = 1000_000
    assert block_id not in block_ids

    test_mem_dealloc_failure(mem, mem_type, block_id)

    # Test: Verify deallocation failure for mismatched memory types.
    other_mem_type = MemoryType.heap

    if mem_type == MemoryType.heap:
        other_mem_type = MemoryType.stack

    block_id = test_mem_alloc_success(mem, mem_type, LIMIT, block_ids)
    test_mem_dealloc_failure(mem, other_mem_type, block_id)


def test_mem_block_read_write() -> None:
    test_mem_block_read_write_success()
    test_mem_block_read_write_failure()


def test_mem_block_mine() -> None:
    test_mem_block_mine_success()
    test_mem_block_mine_failure()


def test_mem_alloc_dealloc(mem_type: MemoryType) -> None:
    test_mem_alloc_dealloc_success(mem_type)
    test_mem_alloc_dealloc_failure(mem_type)


def test_mem_block() -> None:
    test_mem_block_read_write()
    test_mem_block_mine()


def test_mem() -> None:
    # Test: Verify memory block operations.
    test_mem_block()

    # Test: Verify general memory management functionality for all
    #       supported memory types.
    for mem_type in MemoryType:
        if mem_type != MemoryType.text:
            test_mem_alloc_dealloc(mem_type)


if __name__ == "__main__":
    test_mem()
