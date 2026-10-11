import numpy as np
import pytest
from tests.fixtures.proto_mapper.matching_builders import (
    select_best_signature_pair,
    simple_signature,
)
from tests.fixtures.proto_mapper.message_builders import (
    build_verified_mapping,
)

from DBDofusUnity.proto_mapper_assembly.matching.workspace import build_matching_workspace


class TestMatchSignaturesIteratively:
    def test_ambiguous_pair_does_not_hide_an_unrelated_confident_pair(self) -> None:
        obf_alpha = simple_signature("obf_alpha")
        obf_beta = simple_signature("obf_beta")
        obf_gamma = simple_signature("obf_gamma")
        clear_alpha = simple_signature("ClearAlpha")
        clear_beta = simple_signature("ClearBeta")
        workspace = build_matching_workspace(
            obf_signatures=[obf_alpha, obf_beta, obf_gamma],
            non_obf_signatures=[clear_alpha, clear_beta],
            obf_messages_by_cls={},
            non_obf_messages_by_cls={},
        )

        selected_pair = select_best_signature_pair(
            workspace=workspace,
            scores_matrix=np.array([[0.9, 0.88, 0.1], [0.1, 0.1, 0.8]]),
            available_non_obf=[clear_alpha, clear_beta],
            available_obf=[obf_alpha, obf_beta, obf_gamma],
            roots_only=False,
            pinned_pairs_config=build_verified_mapping(),
        )

        assert selected_pair is not None
        assert selected_pair.non_obf_signature is clear_beta
        assert selected_pair.obf_signature is obf_gamma

    def test_ambiguous_assignment_is_kept_with_its_low_margin(self) -> None:
        obf_alpha = simple_signature("obf_alpha")
        obf_beta = simple_signature("obf_beta")
        clear_alpha = simple_signature("ClearAlpha")
        workspace = build_matching_workspace(
            obf_signatures=[obf_alpha, obf_beta],
            non_obf_signatures=[clear_alpha],
            obf_messages_by_cls={},
            non_obf_messages_by_cls={},
        )

        selected_pair = select_best_signature_pair(
            workspace=workspace,
            scores_matrix=np.array([[0.9, 0.88]]),
            available_non_obf=[clear_alpha],
            available_obf=[obf_alpha, obf_beta],
            roots_only=False,
            pinned_pairs_config=build_verified_mapping(),
        )

        assert selected_pair is not None
        assert selected_pair.non_obf_signature is clear_alpha
        assert selected_pair.obf_signature is obf_alpha
        assert selected_pair.match_margin == pytest.approx(0.02)

    def test_global_assignment_avoids_greedy_pairing_trap(self) -> None:
        obf_alpha = simple_signature("obf_alpha")
        obf_beta = simple_signature("obf_beta")
        clear_alpha = simple_signature("ClearAlpha")
        clear_beta = simple_signature("ClearBeta")
        workspace = build_matching_workspace(
            obf_signatures=[obf_alpha, obf_beta],
            non_obf_signatures=[clear_alpha, clear_beta],
            obf_messages_by_cls={},
            non_obf_messages_by_cls={},
        )

        selected_pair = select_best_signature_pair(
            workspace=workspace,
            scores_matrix=np.array([[0.90, 0.80], [0.85, 0.10]]),
            available_non_obf=[clear_alpha, clear_beta],
            available_obf=[obf_alpha, obf_beta],
            roots_only=False,
            pinned_pairs_config=build_verified_mapping(),
        )

        assert selected_pair is not None
        assert selected_pair.non_obf_signature is clear_beta
        assert selected_pair.obf_signature is obf_alpha
