from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Point(_message.Message):
    __slots__ = ["x", "y"]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ...) -> None: ...

class StartupRequest(_message.Message):
    __slots__ = ["soldier_id", "N"]
    SOLDIER_ID_FIELD_NUMBER: _ClassVar[int]
    N_FIELD_NUMBER: _ClassVar[int]
    soldier_id: int
    N: int
    def __init__(self, soldier_id: _Optional[int] = ..., N: _Optional[int] = ...) -> None: ...

class StartupResponse(_message.Message):
    __slots__ = ["current_position"]
    CURRENT_POSITION_FIELD_NUMBER: _ClassVar[int]
    current_position: Point
    def __init__(self, current_position: _Optional[_Union[Point, _Mapping]] = ...) -> None: ...

class MissileApproachingRequest(_message.Message):
    __slots__ = ["target", "time_to_hit", "type"]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    TIME_TO_HIT_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    target: Point
    time_to_hit: int
    type: int
    def __init__(self, target: _Optional[_Union[Point, _Mapping]] = ..., time_to_hit: _Optional[int] = ..., type: _Optional[int] = ...) -> None: ...

class RoundStatusResponse(_message.Message):
    __slots__ = ["soldier_id", "was_hit", "updated_position"]
    SOLDIER_ID_FIELD_NUMBER: _ClassVar[int]
    WAS_HIT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_POSITION_FIELD_NUMBER: _ClassVar[int]
    soldier_id: int
    was_hit: bool
    updated_position: Point
    def __init__(self, soldier_id: _Optional[int] = ..., was_hit: bool = ..., updated_position: _Optional[_Union[Point, _Mapping]] = ...) -> None: ...

class AliveSoldier(_message.Message):
    __slots__ = ["sid", "addr", "position"]
    SID_FIELD_NUMBER: _ClassVar[int]
    ADDR_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    sid: int
    addr: str
    position: Point
    def __init__(self, sid: _Optional[int] = ..., addr: _Optional[str] = ..., position: _Optional[_Union[Point, _Mapping]] = ...) -> None: ...

class NewCommanderRequest(_message.Message):
    __slots__ = ["board_size", "time_to_missile", "game_time", "cur_time", "alive_soldiers"]
    BOARD_SIZE_FIELD_NUMBER: _ClassVar[int]
    TIME_TO_MISSILE_FIELD_NUMBER: _ClassVar[int]
    GAME_TIME_FIELD_NUMBER: _ClassVar[int]
    CUR_TIME_FIELD_NUMBER: _ClassVar[int]
    ALIVE_SOLDIERS_FIELD_NUMBER: _ClassVar[int]
    board_size: int
    time_to_missile: int
    game_time: int
    cur_time: int
    alive_soldiers: _containers.RepeatedCompositeFieldContainer[AliveSoldier]
    def __init__(self, board_size: _Optional[int] = ..., time_to_missile: _Optional[int] = ..., game_time: _Optional[int] = ..., cur_time: _Optional[int] = ..., alive_soldiers: _Optional[_Iterable[_Union[AliveSoldier, _Mapping]]] = ...) -> None: ...

class Empty(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
