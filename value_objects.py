from enum import Enum

from error import *
from memory import Memory, MemoryType, MemoryBlock

# Value Objects
# By the memory model we are given, that objects are represented
# as a discrete blocks of raw bytes. however, is not very uses full
# to work with just bytes, because we need to safe some type
# information about the objects, such

# all right cunt, here is the deal. if we create a pointer to an object,
# then we have to create memory block, but if the object is just chilling
# then fuck it, right? why would you do the whole saving and loading,
# when you can work with this. Also when we will store the object to
# the memory by the convertor, I guess we have to have some memory in hand
# or somehow hack it. Because if you have nested objects, like struct in struct
# you want to create bytes for that inner struct and then merge them with
# outer struct as mornfall showed you on one wednesday, and also
# in some way it makes sence, that you want to convert mem block to object
# and vice versa, because that's what you gonna do.
#
# also if the object won't have their own mem block, you still need to
# adjust memory stats, so have some sim_alloc and sim_dealloc that takes
# how many bytes were taken...

# To sumarise what you need to do is,
# - finish the memory model
# - write the fucking eval, like what should be done and what
# - write the fucking analysis to fix the issues with parser
# - finish the parser
# that's the bare minimum, it has to take max 2 days, otherwise we are
# fucked, so...
#
# wait, what about errors? well fuck them, or at least deal with them
# after this, because you still need to finish the text
#
# oh and what about formater and repl, well... make the minimum and
# then if you are speedy gonsales, then do something about it.
#
# oh, and what about informing mornfall, because it's already after friday
# shit... fuck!!!! idk, if I gonna show him this, he won't like it and
# probably don't wanna waist his time if stuffs aren't finished.
# duuuuude
#
# like the main obstical is me, because I can't not concentraite currently
# because I wrote like what 6K lines of code in 4 days, and basically
# doing everything in first try, and some of the stuff are good, but
# will it be good enough.
#
# also something something scope has to be recursive, because of shadow
# variables
#
# also something something, stack frame hold the objects and the memory
# and if the stack frame out, then memory out,
#
# also something something malloc and be simulated something like this
# with counter, but it is basically some weird style of shared pointer,
# but something something cycles in pointers... maybe detectable...
# if you look at the pointer ids??? because then you can detect cycle

# alhamdulillah ono to pôjde, aha nejako som prepol do slovenčiny
# divné... spať

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

        # NOTE: Relies on dictionary insertion order (Python 3.7+)
        # to preserve member layout.
        for member_iden, member_type in members:
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
                 elems: list[ValueObject]) -> None:
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

    def float_to_bytearray(self, value_object: FloatValue) -> bytearray:
        pass

    def ptr_to_bytearray(self, value_object: PtrValue) -> bytearray:
        fst = value_object.block_id.to_bytes(
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

    def array_to_bytearray(self, value_object: ArrayValue) -> bytearray:
        value = bytearray()

        for idx, elem in enumerate(value_object.elems):
            if elem is None:

            self.to_bytearray(elem)


    def struct_to_bytearray(self, value_object: StructValue) -> bytearray:
        assert MemoryFlags.poison == 0x00
        value = bytearray(struct_type.size)

        struct_type = value_object.struct_type

        for name, member_object in value_object.elems.items():
            offset = struct_type.members[name].offset
            member_bytes = self.to_bytearray(member_object)

            for idx in range(len(member_bytes)):
                value[idx + offset] = member_bytes[idx]

        return value

    def union_to_bytearray(self, value_object: UnionValue) -> bytearray:
        return self.to_bytearray(value_object.value)

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

        if isinstance(value_object, ArrayValue):
            return self.array_to_bytearray(value_object)

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

        if isinstance(value_type, ArrayTypeType):
            return self.array_from_bytearray(value_type, raw_bytes)

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
