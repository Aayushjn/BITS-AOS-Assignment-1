import argparse
import os
import random
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypedDict

import grpc

import war_pb2
import war_pb2_grpc

MAX_SPEED = 4
MIN_BOARD_SIZE = 5
MIN_SOLDIERS = 2

GRPC_SERVER_SHUTDOWN_TIMEOUT = 10


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
    # missile's blast radius may fall partially outside the bounds of the board
    missile_pos = (random.randrange(0, board_size), random.randrange(0, board_size))
    return missile_type, missile_pos


def is_position_in_blast_radius(
    position: tuple[int, int], missile_type: int, missile_position: tuple[int, int], board_size: int
) -> bool:
    """
    Check if the point is within missile blast radius

    Parameters
    ----------
    position
        (x, y) co-ordinates of position to check
    missile_type
        type of missile (see `spawn_missile` for types of missiles)
    missile_position
        (x, y) co-ordinates of the missile's center
    board_size
        size of the board

    Returns
    -------
    bool
        `True` if the point is in the missile blast radius, `False` otherwise
    """
    return max(missile_position[0] - missile_type + 1, 0) <= position[0] <= min(
        missile_position[0] + missile_type - 1, board_size - 1
    ) and max(missile_position[1] - missile_type + 1, 0) <= position[1] <= min(
        missile_position[1] + missile_type - 1, board_size - 1
    )


def is_valid_position(position: tuple[int, int], board_size: int) -> bool:
    """
    Check if the given position is within board limits

    Parameters
    ----------
    position
        (x, y) co-ordinates on the board
    board_size
        size of the board

    Returns
    -------
    bool
        `True` if within board limits, `False` otherwise
    """
    return 0 <= position[0] < board_size and 0 <= position[1] < board_size


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

    def __init__(self):
        self.game_over = False
        self.is_promoted = False
        self.is_alive = True
        self.speed = random.randint(0, MAX_SPEED)

    def take_shelter(self, missile_type: int, missile_position: tuple[int, int]):
        """
        When the soldier is notified of an incoming missile, it attempts to run away.
        The soldier may move in any of the eight directions at most `self.speed` number of steps.

        Parameters
        ----------
        missile_type
            type of missile (see `spawn_missile` for types of missiles)
        missile_position
            (x, y) co-ordinates of the missile's center
        """
        # must choose one of possible eight directions to move in
        directions = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
        # assume that the missile will hit the soldier and later correct it while trying to escape
        self.is_alive = False

        if is_position_in_blast_radius(self.position, missile_type, missile_position, self.board_size):
            for direction in directions:
                step = (self.speed * direction[0], self.speed * direction[1])
                # it is possible that while trying to escape, the soldier goes outside the board
                # to prevent that, ensure limits with max and min functions
                new_position = (
                    max(self.position[0] + step[0], 0),
                    min(self.position[1] + step[1], self.board_size - 1),
                )
                if is_valid_position(new_position, self.board_size) and not is_position_in_blast_radius(
                    new_position, missile_type, missile_position, self.board_size
                ):
                    self.position = new_position
                    self.is_alive = True
                    break


class Commander(Soldier):
    time_to_missile: int
    game_time: int
    cur_time: int

    alive_soldiers: list[SoldierMetadata]

    def __init__(
        self, board_size: int, time_to_missile: int, game_time: int, cur_time: int, is_initial_commander: bool
    ):
        super().__init__()

        self.sid = 0
        self.board_size = board_size
        self.time_to_missile = time_to_missile
        self.game_time = game_time
        self.cur_time = cur_time
        if is_initial_commander:
            self._read_soldier_inventory()

    def _read_soldier_inventory(self):
        """
        Reads a "soldiers.txt" inventory file. Each line contains the IP address and port of the soldiers
        """
        with Path("soldiers.txt").open("r") as f:
            self.alive_soldiers = [
                {"sid": i + 1, "addr": line.strip(), "position": (-1, -1)} for i, line in enumerate(f)
            ]

    def set_position(self):
        position = (random.randrange(0, self.board_size), random.randrange(0, self.board_size))
        for soldier in self.alive_soldiers:
            if position == soldier["position"]:
                position = (random.randrange(0, self.board_size), random.randrange(0, self.board_size))
        self.position = position

    def send_startup_request(self):
        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.StartupStatus(war_pb2.StartupRequest(soldier_id=soldier["sid"], N=self.board_size))
                soldier["position"] = (resp.current_position.x, resp.current_position.y)

    def send_missile_approaching_request(self):
        missile = spawn_missile(self.board_size)
        # commander takes shelter and then notifies the soldiers
        self.take_shelter(missile_type=missile[0], missile_position=missile[1])

        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                stub.MissileApproaching(
                    war_pb2.MissileApproachingRequest(
                        target=war_pb2.Point(x=missile[1][0], y=missile[1][1]),
                        time_to_hit=self.time_to_missile,
                        type=missile[0],
                    )
                )

    def send_round_status_request(self):
        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.RoundStatus(war_pb2.Empty())
                if resp.was_hit:
                    # delete soldier from alive_soldiers
                    self.alive_soldiers = [sol for sol in self.alive_soldiers if sol["sid"] != resp.soldier_id]
                else:
                    # update soldier position
                    soldier["position"] = (resp.updated_position.x, resp.updated_position.y)

    def send_new_commander_message(self):
        # select new commander randomly
        new_commander = random.choice(self.alive_soldiers)
        alive_soldiers_grpc = [
            war_pb2.AliveSoldier(
                sid=soldier["sid"],
                addr=soldier["addr"],
                position=war_pb2.Point(x=soldier["position"][0], y=soldier["position"][1]),
            )
            for soldier in self.alive_soldiers
        ]
        with grpc.insecure_channel(new_commander["addr"]) as channel:
            stub = war_pb2_grpc.WarStub(channel)
            stub.NewCommander(
                war_pb2.NewCommanderRequest(
                    board_size=self.board_size,
                    time_to_missile=self.time_to_missile,
                    game_time=self.game_time,
                    cur_time=self.cur_time,
                    alive_soldiers=alive_soldiers_grpc,
                )
            )

    def send_game_over(self):
        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                stub.GameOver(war_pb2.Empty())

    def run_game_loop(self):
        while self.cur_time <= self.game_time:
            self.send_missile_approaching_request()
            time.sleep(self.time_to_missile)
            self.cur_time += self.time_to_missile
            self.send_round_status_request()
            if not self.is_alive:
                if len(self.alive_soldiers) > 0:
                    self.send_new_commander_message()
                self.is_alive = False
                break
            self.print_layout()

        if self.is_alive:
            self.send_game_over()

    def print_layout(self):
        # TODO: Print board layout
        pass


class War(war_pb2_grpc.WarServicer):
    soldier: Soldier
    commander: Commander

    def StartupStatus(self, request, context):
        self.soldier.sid = request.soldier_id
        self.soldier.board_size = request.board_size
        self.soldier.position = (
            random.randrange(0, self.soldier.board_size),
            random.randrange(0, self.soldier.board_size),
        )
        return war_pb2.StartupResponse(
            current_position=war_pb2.Point(x=self.soldier.position[0], y=self.soldier.position[1]),
        )

    def MissileApproaching(self, request, context):
        self.soldier.take_shelter(missile_type=request.type, missile_position=(request.target.x, request.target.y))
        return war_pb2.Empty()

    def RoundStatus(self, request, context):
        # if soldier is dead, updated_position should be ignored
        return war_pb2.RoundStatusResponse(
            soldier_id=self.soldier.sid,
            was_hit=not self.soldier.is_alive,
            updated_position=war_pb2.Point(x=self.soldier.position[0], y=self.soldier.position[1]),
        )

    def NewCommander(self, request, context):
        self.soldier.is_promoted = True
        self.commander = Commander(
            request.board_size, request.time_to_missile, request.game_time, request.cur_time, False
        )
        # make a note of alive soldiers and remove self entry
        self.commander.alive_soldiers = [
            {"sid": soldier.sid, "addr": soldier.addr, "position": (soldier.position.x, soldier.position.y)}
            for soldier in request.alive_soldiers
            if soldier.sid != self.soldier.sid
        ]
        self.commander.position = self.soldier.position
        return war_pb2.Empty()

    def GameOver(self, request, context):
        self.soldier.game_over = True
        return war_pb2.Empty()


if __name__ == "__main__":
    random.seed(os.urandom(16))

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--commander", action="store_true")
    group.add_argument("--soldier", action="store_true")
    args = parser.parse_args()

    with Path("config.toml").open("rb") as f:
        conf = tomllib.load(f)
    if conf["N"] < MIN_BOARD_SIZE:
        print(f"Board size must at least be {MIN_BOARD_SIZE}", file=sys.stderr)
        sys.exit(1)
    if conf["t"] > conf["T"]:
        print("Frequency between missiles cannot be greater than game time", file=sys.stderr)
        sys.exit(1)

    if args.commander:
        c = Commander(conf["N"], conf["t"], conf["T"], cur_time=0, is_initial_commander=True)
        c.send_startup_request()
        c.set_position()
        c.print_layout()
        c.run_game_loop()
    else:
        s = Soldier()
        war_service = War()
        war_service.soldier = s
        server = grpc.server(ThreadPoolExecutor(max_workers=10))
        war_pb2_grpc.add_WarServicer_to_server(war_service, server)
        server.add_insecure_port(conf["addr"])
        server.start()

        try:
            while True:
                if not s.is_alive or s.game_over or s.is_promoted:
                    # stop gRPC server
                    server.stop(GRPC_SERVER_SHUTDOWN_TIMEOUT)
                    break
        except KeyboardInterrupt:
            server.stop(GRPC_SERVER_SHUTDOWN_TIMEOUT)

        # now onwards it behaves as commander
        if s.is_promoted:
            war_service.commander.print_layout()
            war_service.commander.run_game_loop()
