import pytest

from DBDofusUnity.proto_mapper_assembly.controllers.enum_signatures import (
    build_canonical_enum_signature,
    validate_enum_signature_member_values,
)
from DBDofusUnity.proto_mapper_assembly.interfaces.enum_mapping import (
    EnumMemberGroup,
    EnumSignatureEntry,
    EnumSwitchPattern,
)


def _enum_signature(*groups: EnumMemberGroup, members: dict[str, str]) -> EnumSignatureEntry:
    return EnumSignatureEntry(
        member_value_to_name=members,
        switch_patterns=[
            EnumSwitchPattern(
                function_addr=0x2000,
                field_offset=24,
                member_groups=list(groups),
            )
        ],
    )


class TestEnumSignatureEntry:
    def test_build_canonical_enum_signature_drops_explicit_groups_with_only_unmapped_members(
        self,
    ) -> None:
        entry = _enum_signature(
            EnumMemberGroup(member_values=[0], called_functions=[]),
            EnumMemberGroup(member_values=[1], called_functions=[]),
            members={"0": "a", "1": "b"},
        )

        result = build_canonical_enum_signature(
            obf_enum_signature=entry,
            value_mapping={"1": "20"},
            non_obf_value_to_name={"20": "Twenty"},
            obf_function_signature_by_address={},
        )

        assert result.member_value_to_name == {"20": "Twenty"}
        assert [group.member_values for group in result.switch_patterns[0].member_groups] == [[20]]

    def test_validate_enum_signature_member_values_rejects_unknown_group_value(self) -> None:
        entry = _enum_signature(
            EnumMemberGroup(member_values=[99], called_functions=[]),
            members={"10": "Ten"},
        )

        with pytest.raises(ValueError, match="undeclared member values"):
            validate_enum_signature_member_values(entry)
