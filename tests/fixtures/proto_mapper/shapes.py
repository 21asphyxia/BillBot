from DBDofusUnity.proto_mapper_assembly.interfaces.field_category import (
    FieldCategoryEnum,
    FieldTypeLeafKind,
    FieldTypeShape,
)

NUMBER_SHAPE = FieldTypeShape(FieldCategoryEnum.NUMBER, None, None)
BOOLEAN_SHAPE = FieldTypeShape(FieldCategoryEnum.BOOLEAN, None, None)
STRING_SHAPE = FieldTypeShape(FieldCategoryEnum.STRING, None, None)
ENUM_SHAPE = FieldTypeShape(FieldCategoryEnum.ENUM, None, None)
MESSAGE_SHAPE = FieldTypeShape(FieldCategoryEnum.MESSAGE, FieldTypeLeafKind.MESSAGE, None)
REPEATED_MESSAGE_SHAPE = FieldTypeShape(FieldCategoryEnum.REPEATED, FieldTypeLeafKind.MESSAGE, None)
