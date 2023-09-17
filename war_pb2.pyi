from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

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
    __slots__ = ["soldier_id", "current_position"]
    SOLDIER_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_POSITION_FIELD_NUMBER: _ClassVar[int]
    soldier_id: int
    current_position: Point
    def __init__(self, soldier_id: _Optional[int] = ..., current_position: _Optional[_Union[Point, _Mapping]] = ...) -> None: ...
