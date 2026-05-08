from enum import Enum

from error import *
from memory import Memory, MemoryType, MemoryBlock

# Value Objects
#

# Types.
class TypeObject:
    pass


class IntType(TypeObject):
    def __init__(self,
                 size: int,
                 alignment: int,
                 is_signed: bool) -> None:
        self.size = size
        self.alignment = alignment
        self.is_signed = is_signed


class PtrType(TypeObject):
    def __init__(self, target_type: TypeObject) -> None:
        self.target_type = target_type

        # memory block_id: 8 bytes | block offset: 8 byte
        self.size: int = 16
        self.alignment: int = 16


class ArrayType(TypeObject):
    def __init__(self, elem_type: TypeObject, length: int) -> None:
        self.elem_type = elem_type
        self.length = length

        self.size = self.elem_type.size * length
        self.alignment = self.elem_type.alignment


class StructMember:
    def __init__(self, member_type: TypeObject, offset: int) -> None:
        self.member_type = member_type
        self.offset = offset


class StructType(TypeObject):
    def __init__(self,
                 iden: str | None,
                 members: dict[str, TypeObject]]) -> None:
        self.iden = iden
        self.members: dict[str, StructMember] = {}

        self.size: int = 0
        self.alignment: int = 1

        # NOTE: Dictionary keeps the order of iteration in the order
        # of insertion, thus, it has to be in the right order.
        for member_iden, member_type in members.items():
            padding = -self.size % member_type.alignment

            self.members[member_iden] = StructMember(member_type, self.size)

            self.size += member_type.size
            self.alignment = max(self.alignment, member_type.alignment)

        self.size += -self.size % self.alignment


class UnionType(TypeObject):
    def __init__(self,
                 iden: str | None,
                 members: dict[str, TypeObject]) -> None:
        self.iden = iden
        self.members = members

        self.size: int = 0
        self.alignment: int = 0

        for (_, member_type) in members:
            self.size = max(self.size, member_type.size)
            self.alignment = max(self.alignment, member_type.alignment)


class EnumType(TypeObject):
    def __init__(self,
                 iden: str | None,
                 elem_type: IntType,
                 elems: dict[str, int]) -> None:
        self.iden = iden

        self.elem_type = elem_type
        self.elems = elems

        self.size = elem_type.size
        self.alignment = elem_type.alignment


# Values.
class ValueObject:
    pass


class IntValue(ValueObject):
    def __init__(self, value_type: IntType, value: int) -> None:
        self.value_type = value_type
        self.value = value


class FloatValue(ValueObject):
    def __init__(self, value_type: FloatType, value: ) -> None:
        pass


class PtrValue(ValueObject):
    def __init__(self,
                 ptr_type: PtrType,
                 block_id: int,
                 offset: int) -> None:
        self.ptr_type = ptr_type
        self.block_id = block_id
        self.offset = offset


class ArrayValue(ValueObject):
    def __init__(self,
                 array_type: ArrayType,
                 elems: list[ValueObject | None]) -> None:
        self.array_type = array_type
        self.elems = elems


class StructValue(ValueObject):
    def __init__(self,
                 struct_type: StructType,
                 elems: dict[str, ValueObject]) -> None:
        self.struct_type = struct_type
        self.elems = elems


class UnionValue(ValueObject):
    def __init__(self,
                 union_type: UnionType,
                 value: ValueObject) -> None:
        self.union_type = union_type
        self.value = value


class EnumValue(ValueObject):
    def __init__(self, enum_type: EnumType, value: IntValue) -> None:
        self.enum_type = enum_type
        self.value = value


# Provides an interface for translating memory blocks into value
# objects. Manages data representation only — logical validation
# and operation correctness are deferred to the evaluator.
class Converter:
    def __init__(self) -> None:
        pass

    def int_to_bytearray(self, value_object: IntValue) -> bytearray:
        return bytearray(value_object.value.to_bytes(
            length=value_object.size,
            byteorder="little",
            signed=value_object.is_signed
        ))

    def float_to_bytearray(self) -> bytearray:
        pass

    def ptr_to_bytearray(self) -> bytearray:
        assert isinstance(self.value_object, PtrValue)

        fst = self.value_object.block_id.to_bytes(
            length=8,
            byteorder="little",
            signed=False
        )

        snd = self.value_object.offset.to_bytes(
            length=8,
            byteorder="little",
            signed=False
        )

        return bytearray(fst + snd)

    def struct_to_bytearray(self, value_object: StructValue) -> bytearray:
        pass

    def union_to_bytearray(self, value_object: UnionValue) -> bytearray:
        self.to_bytearray()
        pass

    def enum_to_bytearray(self, value_object: EnumValue) -> bytearray:
        return self.to_bytearray(value_object.value)

    def int_from_bytearray(self,
                           value_type: IntType,
                           raw_bytes: bytearray) -> IntValue:
        value: int = int.from_bytes(
            bytes=raw_bytes,
            byteorder="little",
            signed=value_type.is_signed
        )

        return IntValue(value_type, value)

    def float_from_bytearray(self,
                             value_type: FloatType,
                             raw_bytes: bytearray) -> FloatValue:
        pass

    def ptr_from_bytearray(self,
                           ptr_type: PtrType,
                           raw_bytes: bytearray) -> PtrValue:
        block_id: int = int.from_bytes(
            bytes=raw_bytes[0:8],
            byteorder="little",
            signed=False
        )

        offset: int = int.from_bytes(
            bytes=raw_bytes[8:],
            byteorder="little",
            signed=False
        )

        return PtrValue(ptr_type, block_id, offset)

    def struct_from_bytearray(self,
                              struct_type: StructType,
                              raw_bytes: bytearray) -> StructValue:
        pass

    def enum_from_bytearray(self,
                            enum_type: EnumType,
                            raw_bytes: bytearray) -> EnumValue:
        return self.from_bytearray(enum_type.elem_type, raw_bytes)

    def to_bytearray(self, value_object: ValueObject) -> bytearray:
        if isinstance(value_object, IntValue):
            return self.int_to_bytearray(value_object)

        if isinstance(value_object, FloatValue):
            return self.float_to_bytearray(value_object)

        if isinstance(value_object, PtrValue):
            return self.ptr_to_bytearray(value_object)

        if isinstance(value_object, StructValue):
            return self.struct_to_bytearray(value_object)

        if isinstance(value_object, UnionValue):
            return self.union_to_bytearray(value_object)

        if isinstance(value_object, EnumValue):
            return self.enum_to_bytearray(value_object)

        assert False

    def from_bytearray(self,
                       value_type: TypeObject,
                       raw_bytes: bytearray) -> ValueObject:
        if isinstance(value_type, IntType):
            return self.int_from_bytearray(value_type, raw_bytes)

        if isinstance(value_type, FloatType):
            return self.float_from_bytearray(value_type, raw_bytes)

        if isinstance(value_type, PtrType):
            return self.ptr_from_bytearray(value_type, raw_bytes)

        if isinstance(value_type, StructType):
            return self.struct_from_bytearray(value_type, raw_bytes)

        if isinstance(value_type, UnionType):
            return self.union_from_bytearray(value_type, raw_bytes)

        if isinstance(value_type, EnumType):
            return self.enum_from_bytearray(value_type, raw_bytes)

        assert False


I8  = TYPE(1, 1, True)
I16 = TYPE(2, 2, True)
I32 = Type(4, 4, True)
I64 = Type(8, 8, True)

U8  = TYPE(1, 1, False)
U16 = TYPE(2, 2, False)
U32 = TYPE(4, 4, False)
U64 = Type(8, 8, False)


def test() -> None:
    pass


if __name__ == "__main__":
    test()
