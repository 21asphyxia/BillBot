from pathlib import Path
from unittest.mock import patch

import pytest

from tests.fixtures.proto_mapper.field_builders import dump_cs_field

from DBDofusUnity.proto_mapper_assembly.interfaces.dump_cs_message import DumpCSMessage
from DBDofusUnity.proto_mapper_assembly.interfaces.excluded_non_obf import ExcludedNonObfConfig
from tests.fixtures.proto_mapper.script_builders import game_mapping_entry
from DBDofusUnity.proto_mapper_assembly.interfaces.game_mappings import (
    GameMappingsDocument,
    SimpleGameMappingEntry,
    SimpleGameMappingsDocument,
)
from scripts.mapping import synchronize_protos
from scripts.mapping.synchronize_protos import (
    _preserve_existing_field_offsets,
    synchronize_non_obf_mapping_artifacts,
)
from DBDofusUnity.proto_mapper_assembly.interfaces.new_dump_cs import NewDumpCSFile
from DBDofusUnity.proto_mapper_assembly.interfaces.pinned_pairs import PinnedPair, PinnedPairsConfig
from DBDofusUnity.proto_mapper_assembly.interfaces.signature_overrides import (
    SignatureOverrideEntry,
    SignatureOverridesFile,
)


class TestPreserveExistingFieldOffsets:
    def test_copies_existing_offsets_and_keeps_new_fields_at_zero(self) -> None:
        existing_actor_id = dump_cs_field("int", offset=0x18, field_name="actorId_").model_copy(
            update={"property_name": "ActorId"}
        )
        existing_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="ActorEvent",
            namespace="Com.Ankama.Dofus.Server.Game.Protocol.Actor",
            fields=[
                existing_actor_id,
                dump_cs_field("string", offset=0x20, field_name="unrelated_").model_copy(
                    update={"property_name": "Unrelated"}
                ),
            ],
        )
        generated_message = existing_message.model_copy(
            update={
                "fields": [
                    dump_cs_field("int", offset=0, field_name="actorId_").model_copy(
                        update={"property_name": "ActorId", "proto_decl_order": 1}
                    ),
                    dump_cs_field("long", offset=0, field_name="newValue_").model_copy(
                        update={"property_name": "NewValue", "proto_decl_order": 2}
                    ),
                ]
            }
        )

        result = _preserve_existing_field_offsets(generated_message, existing_message)

        assert [field.memory_offset for field in result.fields] == [0x18, 0]
        assert [field.property_name for field in result.fields] == ["ActorId", "NewValue"]

    def test_returns_generated_message_when_no_existing_message_is_available(self) -> None:
        generated_message = DumpCSMessage(
            file_descriptor="GameReflection",
            name="NewEvent",
            fields=[dump_cs_field("int", offset=0, field_name="value_")],
        )

        result = _preserve_existing_field_offsets(generated_message, None)

        assert result is generated_message


class TestSynchronizeNonObfMappingArtifacts:
    def test_rebuilds_exclusions_and_prunes_orphaned_mapping_artifacts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        live_message = DumpCSMessage(
            file_descriptor="LiveReflection",
            name="LiveEvent",
            namespace="Com.Ankama.Dofus.Server.Game.Protocol.Live",
        )
        stale_message = DumpCSMessage(
            file_descriptor="StaleReflection",
            name="StaleEvent",
            namespace="Com.Ankama.Dofus.Server.Game.Protocol.Stale",
        )
        live_name = live_message.composed_name
        stale_name = stale_message.composed_name
        new_dump_path = tmp_path / "new_dump_cs.json"
        excluded_path = tmp_path / "excluded_non_obf.json"
        pins_path = tmp_path / "pinned_pairs.json"
        overrides_path = tmp_path / "overrides.json"
        mappings_path = tmp_path / "game_mappings.json"
        detailed_mappings_path = tmp_path / "game_mappings_detailed.json"
        new_dump_path.write_text(
            NewDumpCSFile(root={live_name: live_message, stale_name: stale_message}).model_dump_json(),
            encoding="utf-8",
        )
        pins_path.write_text(
            PinnedPairsConfig(
                pairs=[PinnedPair(obf="live", non_obf=live_name), PinnedPair(obf="stale", non_obf=stale_name)]
            ).model_dump_json(),
            encoding="utf-8",
        )
        empty_override = SignatureOverrideEntry(function_signatures=[], field_signatures={})
        overrides_path.write_text(
            SignatureOverridesFile(
                root={live_name: empty_override, stale_name: empty_override}
            ).model_dump_json(),
            encoding="utf-8",
        )
        live_mapping_key = ".com.ankama.dofus.server.game.protocol.live.LiveEvent"
        stale_mapping_key = ".com.ankama.dofus.server.game.protocol.stale.StaleEvent"
        mappings_path.write_text(
            SimpleGameMappingsDocument(
                root={
                    live_mapping_key: SimpleGameMappingEntry(obf_msg_namespace="live", field_mapping={}),
                    stale_mapping_key: SimpleGameMappingEntry(obf_msg_namespace="stale", field_mapping={}),
                }
            ).model_dump_json(),
            encoding="utf-8",
        )
        detailed_mappings_path.write_text(
            GameMappingsDocument(
                root={
                    live_mapping_key: game_mapping_entry(
                        field_mapping={}, obf_cls="live.child", non_obf_namespace=live_mapping_key
                    ),
                    stale_mapping_key: game_mapping_entry(
                        field_mapping={}, obf_cls="stale", non_obf_namespace=stale_mapping_key
                    ),
                }
            ).model_dump_json(),
            encoding="utf-8",
        )

        with (
            patch(
                "scripts.mapping.synchronize_protos.build_dump_cs_messages_from_pb2",
                return_value={live_name: live_message},
            ),
            patch(
                "scripts.mapping.synchronize_protos.parse_messages",
                return_value=[live_message, stale_message],
            ),
        ):
            synchronize_non_obf_mapping_artifacts(
                protos_dir=tmp_path,
                non_obf_dump_cs_path=tmp_path / "Ankama.Dofus.Protocol.Game.cs",
                new_dump_cs_path=new_dump_path,
                excluded_non_obf_path=excluded_path,
                pinned_pairs_path=pins_path,
                signature_overrides_path=overrides_path,
                game_mappings_path=mappings_path,
                game_mappings_detailed_path=detailed_mappings_path,
            )

        assert "mapped to the nested obfuscated class 'live.child'" in capsys.readouterr().out
        assert set(NewDumpCSFile.model_validate_json(new_dump_path.read_text()).root) == {live_name}
        assert [
            pair.non_obf for pair in PinnedPairsConfig.model_validate_json(pins_path.read_text()).pairs
        ] == [live_name]
        assert set(SignatureOverridesFile.model_validate_json(overrides_path.read_text()).root) == {live_name}
        exclusion_document = ExcludedNonObfConfig.model_validate_json(excluded_path.read_text())
        assert exclusion_document.root == [stale_name]
        assert set(SimpleGameMappingsDocument.model_validate_json(mappings_path.read_text()).root) == {
            live_mapping_key
        }
        assert set(GameMappingsDocument.model_validate_json(detailed_mappings_path.read_text()).root) == {
            live_mapping_key
        }

    def test_retains_and_normalizes_nested_pinned_aliases(self, tmp_path: Path) -> None:
        root_message = DumpCSMessage(
            file_descriptor="OuterReflection",
            name="Outer",
            namespace="Com.Ankama",
            fields=[dump_cs_field("int", field_name="value_")],
        )
        nested_message = DumpCSMessage(
            file_descriptor="OuterReflection",
            name="Inner",
            namespace="Com.Ankama",
            parent_name="Outer.Types",
        )
        pins_path = tmp_path / "pinned_pairs.json"
        pins_path.write_text(
            PinnedPairsConfig(
                pairs=[PinnedPair(obf="xyz", non_obf="Com.Ankama.Outer.Inner")]
            ).model_dump_json(),
            encoding="utf-8",
        )

        synchronize_protos._prune_pinned_pairs(
            messages_by_cls={
                root_message.composed_name: root_message,
                nested_message.composed_name: nested_message,
            },
            path=pins_path,
        )

        retained_pairs = PinnedPairsConfig.model_validate_json(pins_path.read_text()).pairs

        assert [pair.non_obf for pair in retained_pairs] == ["Com.Ankama.Outer.Inner"]

    def test_rebuilds_all_descriptors_with_assembly_then_bootstrap_offset_priority(
        self, tmp_path: Path
    ) -> None:
        first_message = DumpCSMessage(file_descriptor="FirstReflection", name="First")
        second_message = DumpCSMessage(file_descriptor="SecondReflection", name="Second")
        first_name = first_message.composed_name
        second_name = second_message.composed_name
        existing_field = dump_cs_field("int", offset=0x18, field_name="value_")
        generated_first = first_message.model_copy(
            update={
                "fields": [
                    existing_field.model_copy(update={"memory_offset": 0}),
                    dump_cs_field("int", offset=0, field_name="newValue_"),
                ]
            }
        )
        bootstrap_first = first_message.model_copy(update={"fields": [existing_field]})
        assembly_first = first_message.model_copy(
            update={"fields": [existing_field.model_copy(update={"memory_offset": 0x28})]}
        )
        generated_second = second_message.model_copy(
            update={"fields": [existing_field.model_copy(update={"memory_offset": 0})]}
        )
        bootstrap_second = second_message.model_copy(update={"fields": [existing_field]})
        new_dump_path = tmp_path / "new_dump_cs.json"
        new_dump_path.write_text(
            NewDumpCSFile(
                root={first_name: bootstrap_first, second_name: bootstrap_second}
            ).model_dump_json(),
            encoding="utf-8",
        )

        with (
            patch(
                "scripts.mapping.synchronize_protos.build_dump_cs_messages_from_pb2",
                return_value={first_name: generated_first, second_name: generated_second},
            ),
            patch("scripts.mapping.synchronize_protos.parse_messages", return_value=[assembly_first]),
        ):
            synchronize_non_obf_mapping_artifacts(
                protos_dir=tmp_path,
                non_obf_dump_cs_path=tmp_path / "Ankama.Dofus.Protocol.Game.cs",
                new_dump_cs_path=new_dump_path,
                excluded_non_obf_path=tmp_path / "excluded.json",
                pinned_pairs_path=tmp_path / "pins.json",
                signature_overrides_path=tmp_path / "overrides.json",
                game_mappings_path=tmp_path / "mappings.json",
                game_mappings_detailed_path=tmp_path / "detailed.json",
            )
        result = NewDumpCSFile.model_validate_json(new_dump_path.read_bytes())

        assert set(result.root) == {first_name, second_name}
        assert [field.memory_offset for field in result.root[first_name].fields] == [0x28, 0]
        assert result.root[second_name].fields[0].memory_offset == 0x18


class TestNestingGuard:
    NESTED_OBF = "klm.klk"
    FLAT_OBF = "klm"

    def test_warns_when_a_flat_declaration_maps_to_a_nested_obfuscated_class(self, tmp_path: Path) -> None:
        mappings = tmp_path / "game_mappings_detailed.json"
        mappings.write_text(
            GameMappingsDocument(
                root={
                    ".com.ankama.dofus.server.game.protocol.common.UnknownKlk": game_mapping_entry(
                        field_mapping={},
                        obf_cls=self.NESTED_OBF,
                        non_obf_namespace=".com.ankama.dofus.server.game.protocol.common.UnknownKlk",
                    )
                }
            ).model_dump_json(),
            encoding="utf-8",
        )
        message = DumpCSMessage(
            file_descriptor="CommonReflection",
            name="UnknownKlk",
            namespace="Com.Ankama.Dofus.Server.Game.Protocol.Common",
            fields=[],
            properties=[],
            parent_name=None,
        )

        warning = synchronize_protos.check_nesting_matches_obfuscated_side(
            message, GameMappingsDocument.model_validate_json(mappings.read_bytes())
        )

        assert warning is not None
        assert "klm.klk" in warning
        assert "synchronize-protos" in warning

    def test_stays_silent_when_the_obfuscated_class_is_top_level(self, tmp_path: Path) -> None:
        mappings = tmp_path / "game_mappings_detailed.json"
        mappings.write_text(
            GameMappingsDocument(
                root={
                    ".com.ankama.dofus.server.game.protocol.common.UnknownKlm": game_mapping_entry(
                        field_mapping={},
                        obf_cls=self.FLAT_OBF,
                        non_obf_namespace=".com.ankama.dofus.server.game.protocol.common.UnknownKlm",
                    )
                }
            ).model_dump_json(),
            encoding="utf-8",
        )
        message = DumpCSMessage(
            file_descriptor="CommonReflection",
            name="UnknownKlm",
            namespace="Com.Ankama.Dofus.Server.Game.Protocol.Common",
            fields=[],
            properties=[],
            parent_name=None,
        )

        assert (
            synchronize_protos.check_nesting_matches_obfuscated_side(
                message, GameMappingsDocument.model_validate_json(mappings.read_bytes())
            )
            is None
        )
