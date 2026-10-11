from DBDofusUnity.proto_mapper_assembly.interfaces.assembly_access import (
    format_trace_address,
)
from DBDofusUnity.proto_mapper_assembly.interfaces.enum_mapping import (
    EnumCalledFunctionRef,
    EnumMemberGroup,
    EnumSignatureEntry,
    EnumSwitchPattern,
)


def enum_function_ref(
    *,
    call_target_addr: int,
    function_addr: int | None = None,
    occurrence_count: int = 1,
) -> EnumCalledFunctionRef:
    resolved_function_addr = function_addr or call_target_addr
    return EnumCalledFunctionRef(
        function_address=format_trace_address(resolved_function_addr),
        call_target_address=format_trace_address(call_target_addr),
        occurrence_count=occurrence_count,
    )


def enum_entry(
    *member_groups: list[int],
    member_names: dict[str, str] | None = None,
) -> EnumSignatureEntry:
    resolved_member_names = member_names or {
        str(member_value): f"Value{member_value}"
        for member_group in member_groups
        for member_value in member_group
    }
    return EnumSignatureEntry(
        member_value_to_name=resolved_member_names,
        switch_patterns=[
            EnumSwitchPattern(
                function_addr=0x1000,
                field_offset=24,
                member_groups=[
                    EnumMemberGroup(
                        member_values=member_group,
                        called_functions=[
                            enum_function_ref(
                                call_target_addr=0x2000 + (100 * len(member_group)) + sum(member_group)
                            )
                        ],
                    )
                    for member_group in member_groups
                ],
            )
        ],
    )
