from DBDofusUnity.proto_mapper_assembly.parsers._dump_cs_structure import parse_enum_member_values


class TestParseEnumMemberValues:
    def test_multiple_enums(self) -> None:
        code = "public enum A\n{ X = 0, Y = 1 }\npublic enum B\n{ P = 10, Q = 20 }\n"
        result = parse_enum_member_values(code)
        assert "A" in result
        assert "B" in result
        assert result["A"] == {"X": 0, "Y": 1}
        assert result["B"] == {"P": 10, "Q": 20}

    def test_non_public_enum_excluded(self) -> None:
        code = "private enum Hidden\n{ A = 0 }\npublic enum Visible\n{ B = 1 }\n"
        result = parse_enum_member_values(code)
        assert "Hidden" not in result
        assert "Visible" in result
