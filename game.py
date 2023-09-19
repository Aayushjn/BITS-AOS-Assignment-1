import argparse
import os
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypedDict

import war_pb2
import war_pb2_grpc

MAX_SPEED = 4
MIN_BOARD_SIZE = 5
MIN_SOLDIERS = 2


def spawn_missile(board_size: int) -> tuple[int, tuple[int, int]]:
    """
    Spawn any one missile of the following types on the board:

    - M1 -> radius 1
    - M2 -> radius 2
    - M3 -> radius 3
    - M4 -> radius 4

    Parameters
    ----------
    board_size
        size of the board

    Returns
    -------
    tuple[int, tuple[int, int]]
        tuple with missile type and (x, y) co-ordinates
    """
    missile_type = random.randint(1, 4)

    return missile_type, (
        random.randint(missile_type, board_size - missile_type),
        random.randint(missile_type, board_size - missile_type),
    )


class SoldierMetadata(TypedDict):
    sid: int
    addr: str
    position: tuple[int, int]


class Soldier:
    board_size: int

    sid: int
    speed: int
    position: tuple[int, int]
    is_alive: bool
    is_promoted: bool
    game_over: bool

    def __init__(self, board_size: int):
        self.game_over = False
        self.is_promoted = False
        self.is_alive = True
        self.board_size = board_size
        self.speed = random.randint(0, MAX_SPEED)
        self.position = random.randrange(0, board_size), random.randrange(0, board_size)

    def _is_in_red_zone(self, missile_type: int, missile_position: tuple[int, int]) -> bool:
        """
        Check if the soldier is within missile blast radius

        Parameters
        ----------
        missile_type
            type of missile (see `spawn_missile` for types of missiles)
        missile_position
            (x, y) co-ordinates of the missile's center

        Returns
        -------
        bool
            `True` if the soldier is in the missile blast radius, `False` otherwise
        """
        return self.position[0] in (
            missile_position[0] - missile_type + 1,
            missile_position[0] + missile_type - 1,
        ) or self.position[1] in (
            missile_position[1] - missile_type + 1,
            missile_position[1] + missile_type - 1,
        )

    def take_shelter(self, missile_type: int, missile_position: tuple[int, int]):
        # if soldier is not in missile blast radius, do not move
        if not self._is_in_red_zone(missile_type, missile_position):
            return

        # TODO: Compute escape path


class Commander(Soldier):
    time_to_missile: int
    game_time: int

    alive_soldiers: list[SoldierMetadata]

    def __init__(self, board_size: int, time_to_missile: int, game_time: int):
        super().__init__(board_size)

        self.sid = 0
        self.time_to_missile = time_to_missile
        self.game_time = game_time
        self._read_soldier_inventory()

    def _read_soldier_inventory(self):
        """
        Reads a "soldiers.txt" inventory file. Each line contains the IP address and port of the soldiers
        """
        with Path("soldiers.txt").open("r") as f:
            self.alive_soldiers = [{"sid": i + 1, "addr": line, "position": (-1, -1)} for i, line in enumerate(f)]

    def send_startup_request(self):
        for soldier in self.alive_soldiers:
            print(f"sending to {soldier}")
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.StartupStatus(war_pb2.StartupRequest(soldier_id=soldier["sid"], N=self.board_size))
                soldier["position"] = (resp.current_position.x, resp.current_position.y)

    def send_missile_incoming_message(self):
        # TODO: Tie-in gRPC call
        pass

    def send_new_commander_message(self):
        # TODO: Tie-in gRPC call
        pass

    def print_layout(self):
        # TODO: Print board layout
        pass


class War(war_pb2_grpc.WarServicer):
    soldier: Soldier

    def StartupStatus(self, request, context):
        self.soldier.sid = request.soldier_id
        return war_pb2.StartupResponse(
            soldier_id=request.soldier_id,
            current_position=war_pb2.Point(x=self.soldier.position[0], y=self.soldier.position[1]),
        )

    # TODO: Add remaining RPC calls


def start_commander(is_promoted: bool) -> Commander:
    c = Commander(args.board_size, args.time_to_missile, args.game_time)
    if not is_promoted:
        c.send_startup_request()
    else:
        # TODO: Pass alive soldiers for soldier promotion to commander
        pass
    return c


def _check_board_size(n: str) -> int:
    conv = int(n)
    if conv >= MIN_BOARD_SIZE:
        return conv
    raise ValueError(f"board size must be at least {MIN_BOARD_SIZE}")


def _check_num_soldiers(m: str) -> int:
    conv = int(m)
    if conv >= MIN_SOLDIERS:
        return conv
    raise ValueError(f"number of soldiers must be at least {MIN_SOLDIERS}")


random.seed(os.urandom(16))

parser = argparse.ArgumentParser()
parser.add_argument(
    "--commander",
    action="store_true",
    required=False,
    help="run as commander",
)
parser.add_argument(
    "-N",
    type=_check_board_size,
    required=True,
    help="size of the board (NxN)",
    dest="board_size",
)
parser.add_argument(
    "-M",
    type=_check_num_soldiers,
    required=True,
    help="number of soldiers (including commander)",
    dest="num_soldiers",
)
parser.add_argument(
    "-t",
    required=True,
    help="frequency of missiles (must be greater than total game time)",
    dest="time_to_missile",
)
parser.add_argument("-T", required=True, help="total game time", dest="game_time")
parser.add_argument("--addr", required=True, help="soldier IP address and port")

args = parser.parse_args()

if args.time_to_missile > args.game_time:
    raise ValueError("game time must be greater than missile frequency")

if args.commander:
    c = start_commander(False)

    c.print_layout()
    while not c.game_over:
        c.send_missile_incoming_message()
        # TODO: Send status message
        # TODO: Update alive soldiers dict
        if not c.is_alive:
            c.send_new_commander_message()
            break
        c.print_layout()
else:
    s = Soldier(args.board_size)
    war_service = War()
    war_service.soldier = s
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    war_pb2_grpc.add_WarServicer_to_server(war_service, server)
    server.add_insecure_port(args.addr)
    server.start()
    print(f"gRPC server started, listening on {args.addr}")
    server.wait_for_termination()
    while True:
        if s.is_promoted or not s.is_alive or s.game_over:
            # stop gRPC server
            break

    if s.is_promoted:
        c = start_commander(True)
