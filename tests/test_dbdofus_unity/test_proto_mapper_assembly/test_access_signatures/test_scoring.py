from tests.fixtures.proto_mapper.enum_builders import enum_entry
from tests.fixtures.proto_mapper.field_builders import (
    enum_field,
    msg_typed_field,
    scalar_field,
)
from tests.fixtures.proto_mapper.message_builders import message_signature
from tests.fixtures.proto_mapper.shapes import (
    BOOLEAN_SHAPE,
    NUMBER_SHAPE,
)
from tests.fixtures.proto_mapper.signatures import (
    access_atom,
    builder_structure_similarity_context,
    field_access_signature,
)

from DBDofusUnity.proto_mapper_assembly.interfaces.assembly_access import MessageAccessSignature
from DBDofusUnity.proto_mapper_assembly.interfaces.field_comparison import FieldComparisonKey
from DBDofusUnity.proto_mapper_assembly.interfaces.dump_cs_message import DumpCSMessage, DumpCSMessageField
from DBDofusUnity.proto_mapper_assembly.interfaces.field_category import FieldCategoryEnum
from DBDofusUnity.proto_mapper_assembly.scoring.message_scoring import (
    compute_structure_score,
)
from DBDofusUnity.proto_mapper_assembly.scoring.signature_scoring import (
    field_signature_similarity,
)


class TestFieldEvidenceSimilarity:
    def test_comparison_context_discriminates_otherwise_identical_fields(self) -> None:
        context = (FieldComparisonKey("eq", 42, 32, None),)
        left = field_access_signature(accesses=[access_atom().model_copy(update={"comparisons": context})])
        matching = field_access_signature(
            accesses=[access_atom().model_copy(update={"comparisons": context})]
        )
        different = field_access_signature(
            accesses=[
                access_atom().model_copy(
                    update={
                        "comparisons": (FieldComparisonKey("eq", 7, 32, None),),
                    }
                )
            ]
        )
        assert field_signature_similarity(left, matching) > field_signature_similarity(left, different) > 0
        assert left.field_similarity_key != different.field_similarity_key

    def test_comparison_context_does_not_override_incompatible_shapes(self) -> None:
        context = (FieldComparisonKey("eq", 1, 32, None),)
        left = field_access_signature(
            accesses=[access_atom(field_type_shape=NUMBER_SHAPE).model_copy(update={"comparisons": context})]
        )
        right = field_access_signature(
            field_type_shape=BOOLEAN_SHAPE,
            accesses=[
                access_atom(field_type_shape=BOOLEAN_SHAPE).model_copy(update={"comparisons": context})
            ],
        )
        assert field_signature_similarity(left, right) == 0


class TestAssemblyAccessSimilarity:
    def test_field_signature_similarity_ignores_duplicate_alias_accesses(self) -> None:
        left = field_access_signature(
            field_offset=24,
            field_type_shape=NUMBER_SHAPE,
            accesses=[
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=3),
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=3),
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=3),
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=72),
            ],
        )
        right = field_access_signature(
            field_offset=24,
            field_type_shape=NUMBER_SHAPE,
            accesses=[
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=3),
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=72),
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=72),
                access_atom(field_offset=24, field_type_shape=NUMBER_SHAPE, field_access_index=72),
            ],
        )

        assert field_signature_similarity(left, right) == 1.0

    def test_contextual_structure_similarity_uses_repeated_child_message_structure(self) -> None:
        left_parent, left_parent_signature, left_child_signature = _parent_with_repeated_child_signature(
            parent_name="LeftParent",
            child_name="LeftChild",
            child_fields=[
                scalar_field("first_", 0x20),
                scalar_field("second_", 0x28),
            ],
        )
        right_parent, right_parent_signature, right_child_signature = _parent_with_repeated_child_signature(
            parent_name="RightParent",
            child_name="RightChild",
            child_fields=[scalar_field("first_", 0x20)],
        )
        context = builder_structure_similarity_context(
            left_signatures=[left_parent_signature, left_child_signature],
            right_signatures=[right_parent_signature, right_child_signature],
        )

        assert compute_structure_score(left_parent_signature, right_parent_signature) == 1.0
        assert (
            compute_structure_score(
                left_parent_signature,
                right_parent_signature,
                context=context,
            )
            < 1.0
        )
        assert left_parent.fields[0].normalized_type == "RepeatedField<LeftChild>"
        assert right_parent.fields[0].normalized_type == "RepeatedField<RightChild>"

    def test_contextual_structure_similarity_uses_enum_signatures_when_available(self) -> None:
        left_field = enum_field(
            field_name="outcome_",
            property_name="Outcome",
            offset=0x10,
            enum_type="LeftOutcome",
        )
        right_field = enum_field(
            field_name="outcome_",
            property_name="Outcome",
            offset=0x10,
            enum_type="RightOutcome",
        )
        left_message = DumpCSMessage(file_descriptor="FD", name="LeftMessage", fields=[left_field])
        right_message = DumpCSMessage(file_descriptor="FD", name="RightMessage", fields=[right_field])
        left_signature = message_signature(
            "LeftMessage",
            declared_field_signatures=[],
            dump_cs_msg=left_message,
            live_field_keys=frozenset(field.field_key for field in left_message.fields),
        )
        right_signature = message_signature(
            "RightMessage",
            declared_field_signatures=[],
            dump_cs_msg=right_message,
            live_field_keys=frozenset(field.field_key for field in right_message.fields),
        )
        context = builder_structure_similarity_context(
            left_signatures=[left_signature],
            right_signatures=[right_signature],
            left_enum_signatures_by_name={"LeftOutcome": enum_entry([1], [2])},
            right_enum_signatures_by_name={"RightOutcome": enum_entry()},
        )

        assert compute_structure_score(left_signature, right_signature) == 1.0
        assert compute_structure_score(left_signature, right_signature, context=context) < 1.0


def _parent_with_repeated_child_signature(
    *,
    parent_name: str,
    child_name: str,
    child_fields: list[DumpCSMessageField],
) -> tuple[DumpCSMessage, MessageAccessSignature, MessageAccessSignature]:
    parent_field = msg_typed_field(
        field_name="children_",
        property_name="Children",
        offset=0x10,
        clr_type=f"RepeatedField<{child_name}>",
        category=FieldCategoryEnum.REPEATED,
    )
    parent_message = DumpCSMessage(file_descriptor="FD", name=parent_name, fields=[parent_field])
    child_message = DumpCSMessage(file_descriptor="FD", name=child_name, fields=child_fields)
    parent_signature = message_signature(
        parent_message.composed_name,
        declared_field_signatures=[],
        dump_cs_msg=parent_message,
        live_field_keys=frozenset(field.field_key for field in parent_message.fields),
    )
    child_signature = message_signature(
        child_message.composed_name,
        declared_field_signatures=[],
        dump_cs_msg=child_message,
        live_field_keys=frozenset(field.field_key for field in child_message.fields),
    )
    return parent_message, parent_signature, child_signature
