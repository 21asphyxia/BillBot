from typing import Any

import numpy as np
from tests.fixtures.proto_mapper.matching_builders import simple_workspace

from DBDofusUnity.proto_mapper_assembly.interfaces.assembly_access import AccessTraceDocument
from DBDofusUnity.proto_mapper_assembly.affinities.handler_cohorts import build_handler_cohort_affinity
from DBDofusUnity.proto_mapper_assembly.interfaces.affinity import AffinitySignalInputs

_OBF_CLASSES = ("obf_a1", "obf_a2", "obf_b1")
_NON_OBF_CLASSES = ("ClearA1", "ClearA2", "ClearB1", "ClearUnregistered")
_BASE_SCORES = np.array(
    [
        [0.9, 0.1, 0.1],
        [0.1, 0.9, 0.1],
        [0.1, 0.1, 0.9],
        [0.1, 0.1, 0.1],
    ]
)
_TIED_SIBLING_SCORES = np.array(
    [
        [0.5, 0.5, 0.1],
        [0.5, 0.5, 0.1],
        [0.1, 0.1, 0.9],
        [0.1, 0.1, 0.1],
    ]
)


def _access_trace(registrations_by_function: dict[str, list[str]]) -> AccessTraceDocument:
    functions_by_address: dict[str, Any] = {}
    for function_address, registered_classes in registrations_by_function.items():
        functions_by_address[function_address] = {
            "start_address": int(function_address, 16),
            "end_address": int(function_address, 16) + 1,
            "size": 1,
            "access_infos": [
                {
                    "type": "handler_registration",
                    "access_kind": "register",
                    "cls": registered_class,
                    "handler_method": f"Boolean Handle({registered_class})",
                    "method_info_address": index,
                    "filter_typeinfo_address": index,
                    "index_in_function": index,
                    "instruction_address": int(function_address, 16) + index,
                    "handler_function_address": int(function_address, 16) + 0x100 + index,
                    "registration_ordinal": index,
                }
                for index, registered_class in enumerate(registered_classes)
            ],
            "opcode_histogram": {},
            "aliases": [],
            "stable_callees": [],
            "cfg_stats": None,
        }
    return AccessTraceDocument.model_validate({"functions_by_address": functions_by_address})


def _build_affinity() -> tuple[np.ndarray, np.ndarray]:
    return build_handler_cohort_affinity(
        AffinitySignalInputs(
            workspace=simple_workspace(obf_classes=_OBF_CLASSES, non_obf_classes=_NON_OBF_CLASSES),
            base_scores_matrix=_BASE_SCORES,
            obf_access_trace=_access_trace({"0x10": ["obf_a1", "obf_a2"], "0x20": ["obf_b1"]}),
            non_obf_access_trace=_access_trace({"0x30": ["ClearA1", "ClearA2"], "0x40": ["ClearB1"]}),
        )
    )


class TestHandlerCohorts:
    def test_registration_order_breaks_ties_between_indistinguishable_siblings(self) -> None:
        affinity_matrix, _ = build_handler_cohort_affinity(
            AffinitySignalInputs(
                workspace=simple_workspace(obf_classes=_OBF_CLASSES, non_obf_classes=_NON_OBF_CLASSES),
                base_scores_matrix=_TIED_SIBLING_SCORES,
                obf_access_trace=_access_trace({"0x10": ["obf_a2", "obf_a1"], "0x20": ["obf_b1"]}),
                non_obf_access_trace=_access_trace({"0x30": ["ClearA1", "ClearA2"], "0x40": ["ClearB1"]}),
            )
        )

        assert affinity_matrix[0, 1] == 1.0
        assert affinity_matrix[1, 0] == 1.0
        assert affinity_matrix[0, 1] > affinity_matrix[0, 0]

    def test_ordering_is_skipped_when_the_cohorts_lost_too_many_handlers(self) -> None:
        affinity_matrix, _ = build_handler_cohort_affinity(
            AffinitySignalInputs(
                workspace=simple_workspace(obf_classes=_OBF_CLASSES, non_obf_classes=_NON_OBF_CLASSES),
                base_scores_matrix=_TIED_SIBLING_SCORES,
                obf_access_trace=_access_trace({"0x10": ["obf_a1"], "0x20": ["obf_b1"]}),
                non_obf_access_trace=_access_trace({"0x30": ["ClearA1", "ClearA2"], "0x40": ["ClearB1"]}),
            )
        )

        assert affinity_matrix[0, 0] == 1.0
        assert affinity_matrix[1, 0] == 1.0

    def test_a_decisive_score_still_wins_over_registration_order(self) -> None:
        affinity_matrix, _ = build_handler_cohort_affinity(
            AffinitySignalInputs(
                workspace=simple_workspace(obf_classes=_OBF_CLASSES, non_obf_classes=_NON_OBF_CLASSES),
                base_scores_matrix=_BASE_SCORES,
                obf_access_trace=_access_trace({"0x10": ["obf_a2", "obf_a1"], "0x20": ["obf_b1"]}),
                non_obf_access_trace=_access_trace({"0x30": ["ClearA1", "ClearA2"], "0x40": ["ClearB1"]}),
            )
        )

        assert affinity_matrix[0, 0] == 1.0

    def test_pairs_crossing_two_matched_cohorts_stay_constrained(self) -> None:
        _, applicable_mask = _build_affinity()

        assert applicable_mask[0, 2]
