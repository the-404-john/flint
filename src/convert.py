import math
import struct
import decimal
from decimal import Decimal

from error import *
from limits import *

from memory import MemoryBlock
from value_objects import *

# Memory Converter
# Provides an interface for translating between value objects and
# raw bytearrays.
#
# Manages data representation only — logical validation and operation
# correctness are deferred to the evaluator.
class MemConverter:
    def __init__(self) -> None:
        pass

    def bytes_to_block(self, data: bytes | bytearray) -> MemoryBlock:
        block = MemoryBlock(len(data))

        for i, byte in enumerate(data):
            result = block.write(i, byte)
            assert not isinstance(result, Error)

        return block

    def read_block_bytes(self,
                         mem_block: MemoryBlock,
                         offset: int,
                         count: int) -> bytearray | Error:
        buffer = bytearray(count)

        for i in range(count):
            byte = mem_block.read(offset + i)

            if isinstance(byte, Error):
                return byte

            buffer[i] = byte

        return buffer

    # To Memory Block.
    def bool_to_mem_block(self, val: BoolValue) -> MemoryBlock:
        return self.bytes_to_block(bytes([1 if val.value else 0]))

    def int_to_mem_block(self, val: IntValue) -> MemoryBlock:
        value_type = val.value_type

        value_bytes = val.value.to_bytes(
            length=value_type.size,
            byteorder="little",
            signed=value_type.is_signed,
        )

        return self.bytes_to_block(value_bytes)

    def float_to_mem_block(self, val: FloatValue) -> MemoryBlock:
        if val.value_type.size == 4:
            value_bytes = struct.pack('<f', val.value)
        else:
            assert val.value_type.size == 8
            value_bytes = struct.pack('<d', val.value)

        return self.bytes_to_block(value_bytes)

    def dec_to_mem_block(self, val: DecValue) -> MemoryBlock:
        # WARNING: Breaking the pointer representation - if the pointer
        # will be cast to character pointer.
        value_bytes = str(val.value).encode('utf-8')
        return self.bytes_to_block(value_bytes)

    def ptr_to_mem_block(self, val: PtrValue) -> MemoryBlock:
        half: int = PTR_SIZE // 2

        block_id = val.block_id.to_bytes(
            half,
            byteorder="little",
            signed=False
        )

        offset = val.offset.to_bytes(
            half,
            byteorder="little",
            signed=False
        )

        return self.bytes_to_block(block_id + offset)

    def array_to_mem_block(self, val: ArrayValue) -> MemoryBlock:
        block = MemoryBlock(val.array_type.size)
        elem_size = val.array_type.elem_type.size

        for i, elem in enumerate(val.elems):
            elem_block = self.to_mem_block(elem)

            result = block.write_block(i * elem_size, elem_block)
            assert not isinstance(result, Error)

        return block

    def struct_to_mem_block(self, val: StructValue) -> MemoryBlock:
        block = MemoryBlock(val.struct_type.size)

        for iden, elem in val.elems.items():
            member = val.struct_type.members[iden]
            elem_block = self.to_mem_block(elem)

            result = block.write_block(member.offset, elem_block)
            assert not isinstance(result, Error)

        return block

    def union_to_mem_block(self, val: UnionValue) -> MemoryBlock:
        block = MemoryBlock(val.union_type.size)

        inner = self.to_mem_block(val.value)
        result = block.write_block(0, inner)
        assert not isinstance(result, Error)

        return block

    def enum_to_mem_block(self, val: EnumValue) -> MemoryBlock:
        return self.int_to_mem_block(val.value)

    def to_mem_block(self, val_obj: ValueObject) -> MemoryBlock:
        if isinstance(val_obj, BoolValue):
            return self.bool_to_mem_block(val_obj)

        if isinstance(val_obj, IntValue):
            return self.int_to_mem_block(val_obj)

        if isinstance(val_obj, FloatValue):
            return self.float_to_mem_block(val_obj)

        if isinstance(val_obj, DecValue):
            return self.dec_to_mem_block(val_obj)

        if isinstance(val_obj, PtrValue):
            return self.ptr_to_mem_block(val_obj)

        if isinstance(val_obj, ArrayValue):
            return self.array_to_mem_block(val_obj)

        if isinstance(val_obj, StructValue):
            return self.struct_to_mem_block(val_obj)

        if isinstance(val_obj, UnionValue):
            return self.union_to_mem_block(val_obj)

        if isinstance(val_obj, EnumValue):
            return self.enum_to_mem_block(val_obj)

        assert False

    # From Memory Block.
    def bool_from_mem_block(self, mem_block: MemoryBlock) -> BoolValue | Error:
        raw = self.read_block_bytes(mem_block, 0, 1)
        if isinstance(raw, Error):
            return raw

        return BoolValue(raw[0] != 0)

    def int_from_mem_block(self,
                           int_type: IntType,
                           mem_block: MemoryBlock) -> IntValue | Error:
        raw = self.read_block_bytes(mem_block, 0, int_type.size)
        if isinstance(raw, Error):
            return raw

        value = int.from_bytes(
            bytes(raw),
            byteorder="little",
            signed=int_type.is_signed
        )

        return IntValue(int_type, value)

    def float_from_mem_block(self,
                             float_type: FloatType,
                             mem_block: MemoryBlock) -> FloatValue | Error:
        raw = self.read_block_bytes(mem_block, 0, mem_block.size())
        if isinstance(raw, Error):
            return raw

        if float_type.size == 4:
            value, = struct.unpack('<f', raw)
        else:
            assert float_type.size == 8
            value, = struct.unpack('<d', raw)

        return FloatValue(float_type, value)

    def dec_from_mem_block(self,
                           dec_type: DecType,
                           mem_block: MemoryBlock) -> DecValue | Error:
        raw = self.read_block_bytes(mem_block, 0, mem_block.size())
        if isinstance(raw, Error):
            return raw

        value = Decimal(raw.decode("utf-8"))
        return DecValue(dec_type, value)

    def ptr_from_mem_block(self,
                           ptr_type: PtrType,
                           mem_block: MemoryBlock) -> PtrValue | Error:
        half: int = PTR_SIZE // 2

        raw = self.read_block_bytes(mem_block, 0, PTR_SIZE)
        if isinstance(raw, Error):
            return raw

        block_id = int.from_bytes(
            bytes(raw[:half]),
            byteorder="little",
            signed=False
        )

        offset = int.from_bytes(
            bytes(raw[half:]),
            byteorder="little",
            signed=False
        )

        return PtrValue(ptr_type, block_id, offset)

    def array_from_mem_block(self,
                             array_type: ArrayType,
                             mem_block: MemoryBlock) -> ArrayValue | Error:
        elems: list[ValueObject] = []
        elem_size = array_type.elem_type.size
        for i in range(array_type.length):
            sub = mem_block.read_block(i * elem_size, elem_size)
            if isinstance(sub, Error):
                return sub
            elem = self.from_mem_block(array_type.elem_type, sub)
            if isinstance(elem, Error):
                return elem
            elems.append(elem)
        return ArrayValue(array_type, elems)

    def struct_from_mem_block(self,
                              struct_type: StructType,
                              mem_block: MemoryBlock) -> StructValue | Error:
        elems: dict[str, ValueObject] = {}

        for iden, member in struct_type.members.items():
            sub_block = mem_block.read_block(
                member.offset,
                member.member_type.size
            )

            if isinstance(sub_block, Error):
                return sub_block

            value = self.from_mem_block(member.member_type, sub_block)
            if isinstance(value, Error):
                return value

            elems[iden] = value

        return StructValue(struct_type, elems)

    def enum_from_mem_block(self,
                            enum_type: EnumType,
                            mem_block: MemoryBlock) -> EnumValue | Error:
        value = self.int_from_mem_block(enum_type.elem_type, mem_block)

        if isinstance(value, Error):
            return value

        return EnumValue(enum_type, value)

    def from_mem_block(self,
                       val_obj_type: TypeObject,
                       mem_block: MemoryBlock) -> ValueObject | Error:
        if isinstance(val_obj_type, BoolType):
            return self.bool_from_mem_block(mem_block)

        if isinstance(val_obj_type, IntType):
            return self.int_from_mem_block(val_obj_type, mem_block)

        if isinstance(val_obj_type, FloatType):
            return self.float_from_mem_block(val_obj_type, mem_block)

        if isinstance(val_obj_type, DecType):
            return self.dec_from_mem_block(val_obj_type, mem_block)

        if isinstance(val_obj_type, PtrType):
            return self.ptr_from_mem_block(val_obj_type, mem_block)

        if isinstance(val_obj_type, ArrayType):
            return self.array_from_mem_block(val_obj_type, mem_block)

        if isinstance(val_obj_type, StructType):
            return self.struct_from_mem_block(val_obj_type, mem_block)

        if isinstance(val_obj_type, EnumType):
            return self.enum_from_mem_block(val_obj_type, mem_block)

        return Error()


# Type Converter
#
class TypeConverter:
    INT_TYPE = IntType(
        size=INT_KIND_SIZE[IntKind.int],
        alignment=INT_KIND_SIZE[IntKind.int],
        is_signed=True
    )

    def __init__(self) -> None:
        pass

    def int_range(self, val_type: IntType) -> tuple[int, int]:
        bits: int = val_type.size * CHAR_BIT_SIZE

        low: int = 0
        high: int = (1 << bits) - 1

        if val_type.is_signed:
            low = -(1 << (bits - 1))
            high = (1 << (bits - 1)) - 1

        return (low, high)

    def trunc_to_int(self, value: int, val_type: IntType) -> int:
        bits = val_type.size * CHAR_BIT_SIZE

        value %= (1 << bits)

        if val_type.is_signed and value >= (1 << (bits - 1)):
            value -= (1 << bits)

        return value

    def dec_context(self, val_type: DecType) -> decimal.Context:
        if val_type.size == DECIMAL_FLOAT_KIND_SIZE[DecimalFloatKind.decimal32]:
            return ctx32

        if val_type.size == DECIMAL_FLOAT_KIND_SIZE[DecimalFloatKind.decimal64]:
            return ctx64

        if val_type.size == DECIMAL_FLOAT_KIND_SIZE[DecimalFloatKind.decimal128]:
            return ctx128

        assert False

    def common_float_type(self,
                          left: ValueObject,
                          right: ValueObject) -> FloatType | None:
        left_type = None
        if isinstance(left, FloatValue):
            left_type = left.value_type

        right_type = None
        if isinstance(right, FloatValue):
            right_type = right.value_type

        if left_type is None:
            return right_type

        if right_type is None:
            return left_type

        if left_type.size >= right_type.size:
            return left_type
        else:
            return right_type

    def common_dec_type(self,
                        left: ValueObject,
                        right: ValueObject) -> DecType | None:
        left_type = None
        if isinstance(left, DecValue):
            left_type = left.value_type

        right_type = None
        if isinstance(right, DecValue):
            right_type = right.value_type

        if left_type is None:
            return right_type

        if right_type is None:
            return left_type

        if left_type.size >= right_type.size:
            return left_type
        else:
            return right_type

    def promote(self, val: ValueObject) -> ValueObject | Error:
        if isinstance(val, BoolValue):
            return IntValue(self.INT_TYPE, 1 if val.value else 0)

        if isinstance(val, IntValue):
            val_type = val.value_type

            if val_type.size < self.INT_TYPE.size:
                return IntValue(self.INT_TYPE, val.value)

            return val

        if isinstance(val, EnumValue):
            return self.promote(val.value)

        return val

    Converted = tuple[ValueObject, ValueObject]

    def usual_arith_int_same_sign(self,
                                  left: ValueObject,
                                  right: ValueObject) -> Converted | Error:
        left_type, right_type = left.value_type, right.value_type

        target = right_type

        if left_type.size > right_type.size:
            target = left_type

        left_cast = self.cast(left, target)
        if isinstance(left_cast, Error):
            return left_cast

        right_cast = self.cast(right, target)
        if isinstance(right_cast, Error):
            return right_cast

        return (left_cast, right_cast)

    def usual_arith_int(self,
                        left: ValueObject,
                        right: ValueObject) -> Converted | Error:
        left_type, right_type = left.value_type, right.value_type

        if left_type.size == right_type.size and \
           left_type.is_signed == right_type.is_signed:
            return (left, right)

        if left_type.is_signed == right_type.is_signed:
            return self.usual_arith_int_same_sign(left, right)

        signed_type = right_type
        unsigned_type = left_type

        if left_type.is_signed:
            signed_type = left_type
            unsigned_type = right_type

        target = unsigned_type

        if signed_type.size > unsigned_type.size:
            target = signed_type

        left_cast = self.cast(left, target)
        if isinstance(left_cast, Error):
            return left_cast

        right_cast = self.cast(right, target)
        if isinstance(right_cast, Error):
            return right_cast

        return (left_cast, right_cast)

    def usual_arith_float(self,
                          left: ValueObject,
                          right: ValueObject) -> Converted | Error:
        target = self.common_float_type(left, right)
        if target is None:
            return Error()

        left_cast = self.cast(left, target)
        if isinstance(left_cast, Error):
            return left_cast

        right_cast = self.cast(right, target)
        if isinstance(right_cast, Error):
            return right_cast

        return (left_cast, right_cast)

    def usual_arith_dec(self,
                        left: ValueObject,
                        right: ValueObject) -> Converted | Error:
        target = self.common_dec_type(left, right)
        if target is None:
            return Error()

        left_cast = self.cast(left, target)
        if isinstance(left_cast, Error):
            return left_cast

        right_cast = self.cast(right, target)
        if isinstance(right_cast, Error):
            return right_cast

        return (left_cast, right_cast)

    def usual_arith_convert(self,
                            left: ValueObject,
                            right: ValueObject) -> Converted | Error:
        left_dec  = isinstance(left, DecValue)
        right_dec = isinstance(right, DecValue)

        left_float  = isinstance(left, FloatValue)
        right_float = isinstance(right, FloatValue)

        if (left_dec and right_float) or (left_float and right_dec):
            return Error()

        if left_float or right_float:
            return self.usual_arith_float(left, right)

        if left_dec or right_dec:
            return self.usual_arith_dec(left, right)

        left_promo = self.promote(left)
        if isinstance(left_promo, Error):
            return left_promo

        right_promo = self.promote(right)
        if isinstance(right_promo, Error):
            return right_promo

        if not (isinstance(left_promo, IntValue) and
                isinstance(right_promo, IntValue)):
            return Error()

        return self.usual_arith_int(left_promo, right_promo)

    # Cast.
    def cast_bool(self, val_obj: BoolValue, new_type: TypeObject) -> ValueObject | Error:
        v = 1 if val_obj.value else 0

        if isinstance(new_type, BoolType):
            return BoolValue(val_obj.value)

        if isinstance(new_type, IntType):
            return IntValue(new_type, v)

        if isinstance(new_type, FloatType):
            return FloatValue(new_type, float(v))

        if isinstance(new_type, DecType):
            ctx = self.dec_context(new_type)
            return DecValue(new_type, ctx.create_decimal(v))

        return Error()

    def cast_int(self,
                 val_obj: IntValue,
                 new_type: TypeObject) -> ValueObject | Error:

        val = val_obj.value

        if isinstance(new_type, BoolType):
            return BoolValue(val != 0)

        if isinstance(new_type, IntType):
            return IntValue(new_type, self.trunc_to_int(val, new_type))

        if isinstance(new_type, FloatType):
            return FloatValue(new_type, float(val))

        if isinstance(new_type, DecType):
            ctx = self.dec_context(new_type)
            return DecValue(new_type, ctx.create_decimal(val))

        if isinstance(new_type, PtrType):
            return Error()

        return Error()

    def cast_float(self,
                   val_obj: FloatValue,
                   new_type: TypeObject) -> ValueObject | Error:
        val = val_obj.value

        if isinstance(new_type, BoolType):
            return BoolValue(val != 0.0)

        if isinstance(new_type, IntType):
            if not math.isfinite(val):
                return Error()

            truncated = math.trunc(val)
            lo, hi = self.int_range(new_type)

            if truncated < lo or truncated > hi:
                return Error()

            return IntValue(new_type, truncated)

        if isinstance(new_type, FloatType):
            return FloatValue(new_type, val)

        return Error()

    def cast_dec(self,
                 val_obj: DecValue,
                 new_type: TypeObject) -> ValueObject | Error:
        val = val_obj.value

        if isinstance(new_type, BoolType):
            return BoolValue(val != Decimal(0))

        if isinstance(new_type, IntType):
            if not val.is_finite():
                return Error()

            try:
                truncated = int(val.to_integral_value(rounding=decimal.ROUND_ZERO))

            except decimal.InvalidOperation:
                return Error()

            lo, hi = self.int_range(new_type)

            if truncated < lo or truncated > hi:
                return Error()

            return IntValue(new_type, truncated)

        if isinstance(new_type, DecType):
            ctx = self.dec_context(new_type)
            return DecValue(new_type, ctx.create_decimal(val))

        return Error()

    def cast_ptr(self,
                 val_obj: PtrValue,
                 new_type: TypeObject) -> ValueObject | Error:
        if isinstance(new_type, BoolType):
            return BoolValue(val_obj.block_id != 0)

        if isinstance(new_type, PtrType):
            return PtrValue(new_type, val_obj.block_id, val_obj.offset)

        return Error()

    def cast_enum(self,
                  val_obj: EnumValue,
                  new_type: TypeObject) -> ValueObject | Error:
        return self.cast(val_obj.value, new_type)

    def cast(self,
             val_obj: ValueObject,
             new_type: TypeObject) -> ValueObject | Error:

        if isinstance(val_obj, BoolValue):
            return self.cast_bool(val_obj, new_type)

        if isinstance(val_obj, IntValue):
            return self.cast_int(val_obj, new_type)

        if isinstance(val_obj, FloatValue):
            return self.cast_float(val_obj, new_type)

        if isinstance(val_obj, DecValue):
            return self.cast_dec(val_obj, new_type)

        if isinstance(val_obj, PtrValue):
            return self.cast_ptr(val_obj, new_type)

        if isinstance(val_obj, EnumValue):
            return self.cast_enum(val_obj, new_type)

        return Error()

    def implicit_convert(self,
                         val_obj: ValueObject,
                         new_type: TypeObject) -> ValueObject | Error:

        if isinstance(val_obj, PtrValue) and \
           isinstance(new_type, IntType):
            return Error()

        if isinstance(val_obj, IntValue) and \
           isinstance(new_type, PtrType):
            return Error()

        return self.cast(val_obj, new_type)
