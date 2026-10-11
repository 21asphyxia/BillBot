import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from DBDofusUnity.proto_mapper_assembly.interfaces.dump_cs_message import DumpCSMessage
from DBDofusUnity.proto_mapper_assembly.interfaces.pinned_pairs import PinnedPair, PinnedPairsConfig

from .field_builders import number_field

GAME_NS = "Com.Ankama.Dofus.Server.Game.Protocol.Game.Action"
MAP_NS = "Com.Ankama.Dofus.Server.Game.Protocol.Gamemap"
FIGHT_NS = "Com.Ankama.Dofus.Server.Game.Protocol.Fight"


@dataclass(frozen=True)
class PinnedResolveCase:
    pinned_pairs: PinnedPairsConfig
    obf_messages_by_cls: dict[str, DumpCSMessage]
    non_obf_messages_by_cls: dict[str, DumpCSMessage]
    expected_obf: str
    expected_non_obf: str


@dataclass(frozen=True)
class PinnedResolveErrorCase:
    pinned_pairs: PinnedPairsConfig
    obf_messages_by_cls: dict[str, DumpCSMessage]
    non_obf_messages_by_cls: dict[str, DumpCSMessage]
    match: str


@dataclass(frozen=True)
class SnapshotLayout:
    real_game_dir: Path
    snapshots_root: Path
    non_obf_game_dir: Path


def message_lookup(*messages: DumpCSMessage) -> dict[str, DumpCSMessage]:
    return {message.composed_name: message for message in messages}


def pinned_resolve_case(kind: str) -> PinnedResolveCase:
    match kind:
        case "root_non_obf":
            root = DumpCSMessage(
                file_descriptor="GameReflection",
                name="MapCurrentEvent",
                namespace=MAP_NS,
                fields=[number_field()],
            )
            return PinnedResolveCase(
                PinnedPairsConfig(pairs=[PinnedPair(obf="isy", non_obf=f"{MAP_NS}.MapCurrentEvent")]),
                {},
                message_lookup(root),
                "isy",
                root.composed_name,
            )
        case "nested_types_non_obf":
            root = DumpCSMessage(
                file_descriptor="GameReflection",
                name="GameActionFightEvent",
                namespace=GAME_NS,
                fields=[number_field()],
            )
            types = DumpCSMessage(
                file_descriptor="GameReflection",
                name="Types",
                namespace=GAME_NS,
                parent_name="GameActionFightEvent",
            )
            child = DumpCSMessage(
                file_descriptor="GameReflection",
                name="LifePointsLost",
                namespace=GAME_NS,
                parent_name="GameActionFightEvent.Types",
                fields=[number_field("loss_")],
            )
            return PinnedResolveCase(
                PinnedPairsConfig(
                    pairs=[
                        PinnedPair(obf="ixc.iwj", non_obf=f"{GAME_NS}.GameActionFightEvent.LifePointsLost")
                    ]
                ),
                {},
                message_lookup(root, types, child),
                "ixc.iwj",
                "GameActionFightEvent.Types.LifePointsLost",
            )
        case "obf_static_container":
            parent = DumpCSMessage(file_descriptor="FD", name="iyw", fields=[number_field()])
            static_container = DumpCSMessage(file_descriptor="FD", name="iyv", parent_name="iyw")
            nested = DumpCSMessage(
                file_descriptor="FD",
                name="iyu",
                parent_name="iyw.iyv",
                fields=[number_field("fjai_")],
            )
            non_obf = DumpCSMessage(
                file_descriptor="FD",
                name="FightEntityState",
                namespace=FIGHT_NS,
                parent_name="FightLiveStateEvent",
            )
            return PinnedResolveCase(
                PinnedPairsConfig(
                    pairs=[
                        PinnedPair(
                            obf="iyw.iyu",
                            non_obf=f"{FIGHT_NS}.FightLiveStateEvent.FightEntityState",
                        )
                    ]
                ),
                message_lookup(parent, static_container, nested),
                message_lookup(non_obf),
                "iyw.iyv.iyu",
                non_obf.composed_name,
            )
        case _:
            raise ValueError(kind)


def pinned_resolve_error_case(kind: Literal["unknown", "ambiguous"]) -> PinnedResolveErrorCase:
    match kind:
        case "unknown":
            return PinnedResolveErrorCase(
                PinnedPairsConfig(pairs=[PinnedPair(obf="xyz", non_obf="UnknownMessage")]),
                {},
                {},
                "Unknown non-obf message alias",
            )
        case "ambiguous":
            outer = DumpCSMessage(file_descriptor="FD", name="Outer", fields=[number_field()])
            direct_child = DumpCSMessage(
                file_descriptor="FD",
                name="Inner",
                parent_name="Outer",
                fields=[number_field("direct_")],
            )
            types = DumpCSMessage(file_descriptor="FD", name="Types", parent_name="Outer")
            types_child = DumpCSMessage(
                file_descriptor="FD",
                name="Inner",
                parent_name="Outer.Types",
                fields=[number_field("types_")],
            )
            return PinnedResolveErrorCase(
                PinnedPairsConfig(pairs=[PinnedPair(obf="xyz", non_obf="Inner")]),
                {},
                message_lookup(outer, direct_child, types, types_child),
                "Ambiguous non-obf message alias",
            )


def snapshot_layout(tmp_path: Path) -> SnapshotLayout:
    return SnapshotLayout(
        real_game_dir=tmp_path / "real",
        snapshots_root=tmp_path / "D3",
        non_obf_game_dir=tmp_path / "D3" / "BETA",
    )


def write_real_game_files(real_game_dir: Path, *, mtime_ns: int) -> tuple[Path, Path]:
    metadata_dir = real_game_dir / "Dofus_Data" / "il2cpp_data" / "Metadata"
    metadata_dir.mkdir(parents=True)
    assembly = real_game_dir / "GameAssembly.dll"
    metadata = metadata_dir / "global-metadata.dat"
    assembly.write_bytes(b"real-assembly")
    metadata.write_bytes(b"real-metadata")
    set_mtime_ns(assembly, mtime_ns)
    set_mtime_ns(metadata, mtime_ns)
    return assembly, metadata


def write_snapshot(snapshot_dir: Path, *, assembly_mtime_ns: int) -> Path:
    snapshot_dir.mkdir(parents=True)
    assembly = snapshot_dir / "GameAssembly.dll"
    metadata = snapshot_dir / "global-metadata.dat"
    assembly.write_bytes(b"snapshot-assembly")
    metadata.write_bytes(b"snapshot-metadata")
    set_mtime_ns(assembly, assembly_mtime_ns)
    set_mtime_ns(metadata, assembly_mtime_ns)
    return snapshot_dir


def set_mtime_ns(path: Path, mtime_ns: int) -> None:
    os.utime(path, ns=(mtime_ns, mtime_ns))
