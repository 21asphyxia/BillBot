import pytest
from tests.fixtures.proto_mapper.field_builders import dump_cs_field
from tests.fixtures.proto_mapper.shapes import (
    ENUM_SHAPE,
    NUMBER_SHAPE,
    STRING_SHAPE,
)
from tests.fixtures.proto_mapper.signatures import (
    build_access_signatures_for_test,
    build_field_resolution_lookup,
    build_file_descriptor_lookup,
    build_proto_accesses,
    builder_field_access_entry,
    enum_signature_entry,
    function_access_info,
)

from DBDofusUnity.proto_mapper_assembly.controllers.access_signatures import (
    build_message_access_signatures_by_cls,
)
from DBDofusUnity.proto_mapper_assembly.interfaces.assembly_access import FieldAccessEntry
from DBDofusUnity.proto_mapper_assembly.interfaces.field_comparison import FieldComparison
from DBDofusUnity.proto_mapper_assembly.interfaces.dump_cs_message import DumpCSMessage, FieldKey


class TestBuildMessageAccessSignatures:
    def test_comparison_context_survives_export_and_signature_projection(self) -> None:
        entry = builder_field_access_entry(cls="Message")
        entry.comparisons = [
            FieldComparison(
                predicate="eq",
                constant=42,
                width=32,
                signed=None,
                instruction_address=123,
            )
        ]
        exported = FieldAccessEntry.model_validate_json(entry.model_dump_json())
        function = function_access_info(name="Consumer", access_infos=(exported,))
        signature = build_access_signatures_for_test(function, message_classes=("Message",))["Message"]
        expected = (entry.comparisons[0].similarity_key,)
        assert signature.field_signatures[0].accesses_key[0].comparisons == expected
        assert signature.function_similarity_keys[0].self_accesses[0].comparisons == expected
        old_payload = entry.model_dump(exclude={"comparisons"})
        assert FieldAccessEntry.model_validate(old_payload).comparisons == []

    def test_deduplicates_accessor_and_memory_access_at_same_instruction(self) -> None:
        field = dump_cs_field("int", offset=24, field_name="value_")
        field.property_name = "Value"
        message = DumpCSMessage(file_descriptor="FD", name="Message", fields=[field])
        function = function_access_info(
            access_infos=(
                builder_field_access_entry(cls="Message", property_name="Value", access_kind="write"),
                builder_field_access_entry(cls="Message", property_name="Value", access_kind="setter"),
                builder_field_access_entry(
                    cls="Message",
                    property_name="Value",
                    access_kind="setter",
                    instruction_address=10,
                    index_in_function=10,
                ),
            )
        )

        signature = build_access_signatures_for_test(function, messages=(message,))["Message"]

        assert len(signature.field_signatures[0].accesses_key) == 2
        assert len(signature.function_signatures[0].self_accesses_key) == 2

    def test_supports_nested_message_lookup_keys(self) -> None:
        message = DumpCSMessage(file_descriptor="NestedReflection", name="Inner", parent_name="Outer.Types")
        function = function_access_info(
            name="Mapper::Void Run(Outer.Types.Inner)",
            parameters=("Inner",),
            access_infos=(builder_field_access_entry(cls="Outer.Types.Inner"),),
        )

        signature = build_access_signatures_for_test(function, messages=(message,))["Outer.Types.Inner"]

        assert signature.file_descriptor == "NestedReflection"

    def test_raises_when_runtime_message_class_is_missing_from_dump_cs_lookup(self) -> None:
        function = function_access_info(access_infos=(builder_field_access_entry(cls="Com.Game.Message"),))

        with pytest.raises(KeyError, match=r"Com.Game.Message"):
            build_message_access_signatures_by_cls(build_proto_accesses(function), {}, {}, {})

    def test_raises_when_runtime_message_class_is_missing_from_field_resolution_lookup(self) -> None:
        function = function_access_info(access_infos=(builder_field_access_entry(cls="Com.Game.Message"),))

        with pytest.raises(KeyError, match=r"Com.Game.Message"):
            build_message_access_signatures_by_cls(
                build_proto_accesses(function),
                build_file_descriptor_lookup("Com.Game.Message"),
                {},
                {},
            )

    def test_ambiguous_offset_access_fails_field_resolution(self) -> None:
        message = DumpCSMessage(
            file_descriptor="FD",
            name="Message",
            fields=[
                dump_cs_field("int", offset=0x18, field_name="first_"),
                dump_cs_field("string", offset=0x18, field_name="second_"),
            ],
        )
        function = function_access_info(
            access_infos=(
                builder_field_access_entry(
                    cls="Message",
                    field="missing_",
                    property_name=None,
                    field_offset=0x18,
                ),
            ),
        )

        with pytest.raises(KeyError):
            build_access_signatures_for_test(function, messages=(message,))

    def test_declared_similarity_fields_include_only_observed_proto_fields(self) -> None:
        scalar_field = dump_cs_field("int", offset=0x18, field_name="value_")
        oneof_backing_field = dump_cs_field("object", offset=0x20, field_name="choice_")
        oneof_variant_field = dump_cs_field("string", offset=0x20, field_name="ChoiceOne")
        oneof_variant_field.property_name = "ChoiceOne"
        oneof_variant_field.oneof_group_name = "choice"
        oneof_variant_field.is_synthetic_oneof_variant = True
        message = DumpCSMessage(
            file_descriptor="FD",
            name="Message",
            fields=[scalar_field, oneof_backing_field, oneof_variant_field],
        )
        function = function_access_info(
            access_infos=(
                builder_field_access_entry(
                    cls="Message", field="value_", property_name=None, field_offset=0x18
                ),
                builder_field_access_entry(
                    cls="Message",
                    field="ChoiceOne",
                    access_kind="getter",
                    property_name="ChoiceOne",
                    field_offset=None,
                ),
            ),
        )

        signature = build_access_signatures_for_test(function, messages=(message,))["Message"]

        assert sorted(
            (field.field_type_shape, field.oneof_group_name is not None)
            for field in signature.declared_similarity_fields
        ) == sorted(
            [
                (NUMBER_SHAPE, False),
                (STRING_SHAPE, True),
            ]
        )

    def test_declared_similarity_fields_only_include_resolved_proto_fields(self) -> None:
        first_field = dump_cs_field("long", offset=0x18, field_name="map_id_")
        first_field.property_name = "MapId"
        second_field = dump_cs_field("long", offset=0x20, field_name="instance_id_")
        second_field.property_name = "InstanceId"
        message = DumpCSMessage(file_descriptor="FD", name="Message", fields=[first_field, second_field])
        function = function_access_info(
            access_infos=(
                builder_field_access_entry(
                    cls="Message", field="map_id_", property_name="MapId", field_offset=0x18
                ),
            ),
        )

        signature = build_access_signatures_for_test(function, messages=(message,))["Message"]

        assert signature.live_field_keys == frozenset({FieldKey(0x18, "map_id_")})
        assert signature.field_signatures[0].field_key == FieldKey(0x18, "map_id_")
        assert tuple(field.field_type_shape for field in signature.declared_similarity_fields) == (
            NUMBER_SHAPE,
        )

    def test_parameter_only_skipped_when_short_name_is_ambiguous(self) -> None:
        function = function_access_info(
            name="Handler::Void Handle(Inner)",
            parameters=("Inner",),
            access_infos=(),
        )

        signatures = build_access_signatures_for_test(
            function,
            message_classes=("Namespace.A.Inner", "Namespace.B.Inner"),
        )

        assert signatures["Namespace.A.Inner"].function_signatures == []
        assert signatures["Namespace.B.Inner"].function_signatures == []

    def test_parameter_only_ignored_when_type_not_in_resolution_lookup(self) -> None:
        function = function_access_info(
            name="Handler::Void Handle(UnknownType)",
            parameters=("UnknownType",),
            access_infos=(builder_field_access_entry(cls="Com.Game.Message"),),
        )

        signature = build_access_signatures_for_test(function, message_classes=("Com.Game.Message",))[
            "Com.Game.Message"
        ]

        assert len(signature.function_signatures) == 1

    def test_enum_accesses_mark_matching_field_as_live_without_ida_data(self) -> None:
        enum_field = dump_cs_field(
            "Direction",
            offset=0x28,
            field_name="direction_",
            enum_names=frozenset({"Direction"}),
        )
        message = DumpCSMessage(file_descriptor="FD", name="Message", fields=[enum_field])

        signature = build_message_access_signatures_by_cls(
            build_proto_accesses(),
            {"Message": message},
            build_field_resolution_lookup(message),
            enum_signatures={"Direction": enum_signature_entry(field_offset=0x28)},
        )["Message"]

        assert signature.live_field_keys == frozenset({FieldKey(0x28, "direction_")})
        assert signature.field_signatures[0].field_key == FieldKey(0x28, "direction_")
        assert tuple(field.field_type_shape for field in signature.declared_similarity_fields) == (
            ENUM_SHAPE,
        )
        assert signature.declared_similarity_fields[0].enum_value_type == "Direction"
        assert len(signature.field_signatures) == 1
        assert signature.field_signatures[0].field_offset == 0x28
        assert signature.field_signatures[0].accesses == []

    def test_enum_accesses_merge_with_proto_accesses_without_duplicate_field_signature(self) -> None:
        scalar_field = dump_cs_field("int", offset=0x18, field_name="value_")
        enum_field = dump_cs_field(
            "Direction",
            offset=0x28,
            field_name="direction_",
            enum_names=frozenset({"Direction"}),
        )
        enum_field.property_name = "Direction"
        message = DumpCSMessage(file_descriptor="FD", name="Message", fields=[scalar_field, enum_field])
        function = function_access_info(
            access_infos=(
                builder_field_access_entry(
                    cls="Message", field="value_", property_name=None, field_offset=0x18
                ),
                builder_field_access_entry(
                    cls="Message", field="direction_", property_name="Direction", field_offset=0x28
                ),
            ),
        )

        signature = build_access_signatures_for_test(
            function,
            messages=(message,),
            enum_signatures={"Direction": enum_signature_entry(field_offset=0x28)},
        )["Message"]

        assert signature.live_field_keys == frozenset(
            {FieldKey(0x18, "value_"), FieldKey(0x28, "direction_")}
        )
        assert [field_signature.field_offset for field_signature in signature.field_signatures] == [
            0x18,
            0x28,
        ]
        assert len(signature.field_signatures[1].accesses) == 1
