from tests.fixtures.proto_mapper.field_builders import dump_field
from tests.fixtures.proto_mapper.message_builders import (
    build_field_mapping_for_test,
    build_message_lookup,
    field_signature,
    make_field_mapping_context,
    message_signature,
)
from tests.fixtures.proto_mapper.shapes import (
    ENUM_SHAPE,
    NUMBER_SHAPE,
    STRING_SHAPE,
)
from tests.fixtures.proto_mapper.signatures import (
    declared_field_signature,
)

from DBDofusUnity.proto_mapper_assembly.interfaces.dump_cs_message import DumpCSMessage, FieldKey
from DBDofusUnity.proto_mapper_assembly.interfaces.field_category import FieldCategoryEnum
from DBDofusUnity.proto_mapper_assembly.runtime.runtime_store import RuntimeDataStore


class TestBuildFieldMappingRejectedInfos:
    def test_unmapped_non_obf_fields_no_obf_candidate_when_obf_has_fewer_fields(
        self, runtime_data_store: RuntimeDataStore
    ) -> None:
        non_obf_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="SomeEvent",
            fields=[
                dump_field("map_id_", "MapId", 24, FieldCategoryEnum.NUMBER, proto_decl_order=0),
                dump_field("actor_id_", "ActorId", 32, FieldCategoryEnum.NUMBER, proto_decl_order=1),
            ],
        )
        obf_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="isu",
            fields=[dump_field("fhdb", "Fhdb", 24, FieldCategoryEnum.NUMBER)],
        )
        non_obf_sig = message_signature(
            "SomeEvent",
            declared_field_signatures=[
                declared_field_signature(NUMBER_SHAPE),
                declared_field_signature(NUMBER_SHAPE),
            ],
            field_signatures=[
                field_signature(24, NUMBER_SHAPE),
                field_signature(32, NUMBER_SHAPE),
            ],
            live_field_keys=frozenset({FieldKey(24, "map_id_"), FieldKey(32, "actor_id_")}),
            dump_cs_msg=non_obf_message,
        )
        obf_sig = message_signature(
            "isu",
            declared_field_signatures=[declared_field_signature(NUMBER_SHAPE)],
            field_signatures=[field_signature(24, NUMBER_SHAPE)],
            live_field_keys=frozenset({FieldKey(24, "fhdb")}),
            dump_cs_msg=obf_message,
        )

        result = build_field_mapping_for_test(
            non_obf_signature=non_obf_sig,
            obf_signature=obf_sig,
            non_obf_messages_by_cls=build_message_lookup([non_obf_message]),
            obf_messages_by_cls=build_message_lookup([obf_message]),
            field_mapping_context=make_field_mapping_context(runtime_data_store),
        )

        assert result.field_mapping_unmapped_non_obf_fields == {"actor_id": "no_obf_candidate"}

    def test_unmapped_non_obf_fields_score_below_threshold_when_types_incompatible(
        self, runtime_data_store: RuntimeDataStore
    ) -> None:
        non_obf_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="SomeEvent",
            fields=[dump_field("content_", "Content", 24, FieldCategoryEnum.STRING, proto_decl_order=0)],
        )
        obf_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="isu",
            fields=[dump_field("fhdb", "Fhdb", 32, FieldCategoryEnum.ENUM)],
        )
        non_obf_sig = message_signature(
            "SomeEvent",
            declared_field_signatures=[declared_field_signature(STRING_SHAPE)],
            field_signatures=[field_signature(24, STRING_SHAPE)],
            live_field_keys=frozenset({FieldKey(24, "content_")}),
            dump_cs_msg=non_obf_message,
        )
        obf_sig = message_signature(
            "isu",
            declared_field_signatures=[declared_field_signature(ENUM_SHAPE)],
            field_signatures=[field_signature(32, ENUM_SHAPE)],
            live_field_keys=frozenset({FieldKey(32, "fhdb")}),
            dump_cs_msg=obf_message,
        )

        result = build_field_mapping_for_test(
            non_obf_signature=non_obf_sig,
            obf_signature=obf_sig,
            non_obf_messages_by_cls=build_message_lookup([non_obf_message]),
            obf_messages_by_cls=build_message_lookup([obf_message]),
            field_mapping_context=make_field_mapping_context(runtime_data_store),
        )

        assert result.field_mapping == {}
        assert result.field_mapping_unmapped_non_obf_fields == {"content": "score_below_threshold"}

    def test_unmapped_non_obf_field_without_live_access_is_reported(
        self, runtime_data_store: RuntimeDataStore
    ) -> None:
        non_obf_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="SomeEvent",
            fields=[
                dump_field("actor_id_", "ActorId", 24, FieldCategoryEnum.NUMBER, proto_decl_order=0),
                dump_field("object_gid_", "ObjectGid", 32, FieldCategoryEnum.NUMBER, proto_decl_order=1),
            ],
        )
        obf_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="isu",
            fields=[dump_field("fhdb", "Fhdb", 24, FieldCategoryEnum.NUMBER)],
        )
        non_obf_sig = message_signature(
            "SomeEvent",
            declared_field_signatures=[declared_field_signature(NUMBER_SHAPE)],
            field_signatures=[field_signature(24, NUMBER_SHAPE)],
            live_field_keys=frozenset({FieldKey(24, "actor_id_")}),
            dump_cs_msg=non_obf_message,
        )
        obf_sig = message_signature(
            "isu",
            declared_field_signatures=[declared_field_signature(NUMBER_SHAPE)],
            field_signatures=[field_signature(24, NUMBER_SHAPE)],
            live_field_keys=frozenset({FieldKey(24, "fhdb")}),
            dump_cs_msg=obf_message,
        )

        result = build_field_mapping_for_test(
            non_obf_signature=non_obf_sig,
            obf_signature=obf_sig,
            non_obf_messages_by_cls=build_message_lookup([non_obf_message]),
            obf_messages_by_cls=build_message_lookup([obf_message]),
            field_mapping_context=make_field_mapping_context(runtime_data_store),
        )

        assert result.field_mapping == {"fhdb": "actor_id"}
        assert result.field_mapping_unmapped_non_obf_fields == {"object_gid": "no_obf_candidate"}
