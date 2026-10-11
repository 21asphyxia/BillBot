from pathlib import Path

import pytest

from DBDofusUnity.proto_mapper_assembly.matching.static_scores import build_static_score_data
from DBDofusUnity.proto_mapper_assembly.runtime.runtime_store import RuntimeDataStore
from tests.fixtures.proto_mapper.matching_builders import (
    number_signature,
    root_signature,
)
from tests.fixtures.proto_mapper.message_builders import (
    build_verified_mapping,
)
from tests.fixtures.proto_mapper.runtime_store import seed_runtime_content
from tests.fixtures.proto_mapper.signatures import (
    builder_structure_similarity_context,
)


class TestStaticScorePreparation:
    @pytest.mark.parametrize("value,rejected", [(344, True), (0, False), (None, False)])
    def test_untraced_runtime_payload_cannot_match_an_empty_event(
        self, value: int | None, rejected: bool, tmp_path: Path, runtime_data_store: RuntimeDataStore
    ) -> None:
        obf = number_signature("obf").model_copy(update={"field_signatures": [], "function_signatures": []})
        empty = root_signature("GameOverEvent")
        seed_runtime_content(tmp_path, {"obf": [{"from_server": True, "is_root_msg": True, "field0": value}]})

        scores = build_static_score_data(
            obf_signatures=[obf],
            non_obf_signatures=[empty],
            pinned_pairs_config=build_verified_mapping(),
            runtime_data_store=runtime_data_store,
            structure_context=builder_structure_similarity_context(
                left_signatures=[obf], right_signatures=[empty]
            ),
        )

        assert bool(scores.candidate_eligibility_mask[0, 0]) == (not rejected)
        assert (scores.static_scores_matrix[0, 0] > 0) == (not rejected)

    @pytest.mark.parametrize("captured,from_server", [(False, True), (True, True), (True, False)])
    def test_untraced_declared_shape_needs_runtime_capture(
        self, captured: bool, from_server: bool, tmp_path: Path, runtime_data_store: RuntimeDataStore
    ) -> None:
        obf_with_trace = number_signature("obf")
        obf = obf_with_trace.model_copy(update={"field_signatures": []})
        clear_with_trace = number_signature("UpdateLifePointsEvent")
        clear = clear_with_trace.model_copy(
            update={
                "dump_cs_msg": clear_with_trace.dump_cs_msg.model_copy(
                    update={"name": "UpdateLifePointsEvent"}
                )
            }
        )
        if captured:
            seed_runtime_content(
                tmp_path, {"obf": [{"from_server": from_server, "is_root_msg": True, "field_0": 334}]}
            )

        scores = build_static_score_data(
            obf_signatures=[obf],
            non_obf_signatures=[clear],
            pinned_pairs_config=build_verified_mapping(),
            runtime_data_store=runtime_data_store,
            structure_context=builder_structure_similarity_context(
                left_signatures=[obf], right_signatures=[clear]
            ),
        )

        assert (scores.static_scores_matrix[0, 0] > 0) == (captured and from_server)

    @pytest.mark.parametrize("message_name", ["Message", "GameMessage"])
    def test_captured_game_envelope_keeps_its_candidate(
        self, message_name: str, tmp_path: Path, runtime_data_store: RuntimeDataStore
    ) -> None:
        seed_runtime_content(
            tmp_path,
            {"obf": [{"from_server": None, "is_game_msg": True, "is_root_msg": True}]},
        )
        obf = root_signature("obf")
        envelope = root_signature(message_name)
        payload = root_signature("OtherEvent")

        scores = build_static_score_data(
            obf_signatures=[obf],
            non_obf_signatures=[envelope, payload],
            pinned_pairs_config=build_verified_mapping(),
            runtime_data_store=runtime_data_store,
            structure_context=builder_structure_similarity_context(
                left_signatures=[obf], right_signatures=[envelope, payload]
            ),
        )

        assert scores.static_scores_matrix[0, 0] > 0
        assert scores.static_scores_matrix[1, 0] == 0
