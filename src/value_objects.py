import decimal
from decimal import Decimal

from limits import *

# Value Objects
# Represents a runtime object, storing its specific type and value.


# Types.
class TypeObject:
    pass


class VoidType(TypeObject):
    pass


class BoolType(TypeObject):
    def __init__(self) -> None:
        self.size = CHAR_KIND_SIZE[CharKind.char]
        self.alignment = CHAR_KIND_SIZE[CharKind.char]


class IntType(TypeObject):
    def __init__(self,
                 size: int,
                 alignment: int,
                 is_signed: bool) -> None:
        self.size = size
        self.alignment = alignment
        self.is_signed = is_signed


class FloatType(TypeObject):
    def __init__(self, size: int, alignment: int) -> None:
        self.size = size
        self.alignment = alignment


class DecType(TypeObject):
    def __init__(self, size: int, alignment: int) -> None:
        self.size = size
        self.alignment = alignment


class PtrType(TypeObject):
    def __init__(self, target_type: TypeObject | None) -> None:
        self.target_type = target_type

        self.size: int = PTR_SIZE
        self.alignment: int = PTR_SIZE


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
                 members: dict[str, TypeObject]) -> None:
        self.iden = iden
        self.members: dict[str, StructMember] = {}

        self.size: int = 0
        self.alignment: int = 1

        # NOTE: Relies on dictionary insertion order (Python 3.7+)
        # to preserve member layout.
        for member_iden, member_type in members.items():
            padding = -self.size % member_type.alignment
            self.size += padding

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
        self.alignment: int = 1

        for member_type in members.values():
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


class BoolValue(ValueObject):
    def __init__(self, value: bool) -> None:
        self.value_type = BoolType()
        self.value = value


class IntValue(ValueObject):
    def __init__(self, value_type: IntType, value: int) -> None:
        self.value_type = value_type
        self.value = value


class FloatValue(ValueObject):
    def __init__(self, value_type: FloatType, value: float) -> None:
        self.value_type = value_type
        self.value = value


class DecValue(ValueObject):
    def __init__(self, value_type: DecType, value: Decimal) -> None:
        self.value_type = value_type
        self.value = value


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
                 elems: list[ValueObject]) -> None:
        self.array_type = array_type
        self.elems = elems


class EnumValue(ValueObject):
    def __init__(self, enum_type: EnumType, value: IntValue) -> None:
        self.enum_type = enum_type
        self.value = value


class StructValue(ValueObject):
    def __init__(self,
                 struct_type: StructType,
                 elems: dict[str, ValueObject]) -> None:
        self.struct_type = struct_type
        self.elems = elems


class UnionValue(ValueObject):
    def __init__(self,
                 union_type: UnionType,
                 active_member: str,
                 value: ValueObject) -> None:
        self.union_type = union_type
        self.active_member = active_member
        self.value = value


# Predefined decimal context.
ctx32 = decimal.Context(prec=7,  Emin=-95,   Emax=96)
ctx64 = decimal.Context(prec=16, Emin=-383,  Emax=384)
ctx128 = decimal.Context(prec=34, Emin=-6143, Emax=6144)
