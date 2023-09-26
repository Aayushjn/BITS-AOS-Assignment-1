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
from rich import print
from rich.box import HEAVY_HEAD
from rich.console import Console
from rich.table import Table

import war_pb2
import war_pb2_grpc

MAX_SPEED = 4
MIN_BOARD_SIZE = 8
MIN_SOLDIERS = 2

GRPC_SERVER_SHUTDOWN_TIMEOUT = 10
GRPC_CHANNEL_OPTIONS = (("grpc.enable_http_proxy", 0),)


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
    return max(0, missile_position[0] - missile_type + 1) <= position[0] <= min(
        missile_position[0] + missile_type - 1, board_size - 1
    ) and max(0, missile_position[1] - missile_type + 1) <= position[1] <= min(
        missile_position[1] + missile_type - 1, board_size - 1
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
    was_hit: bool
    is_alive: bool
    is_promoted: bool
    game_over: bool

    console = Console()

    def __init__(self):
        self.game_over = False
        self.is_promoted = False
        self.is_alive = True
        self.was_hit = False
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

        if not is_position_in_blast_radius(self.position, missile_type, missile_position, self.board_size):
            return
        elif self.speed == 0:
            self.was_hit = True
            return

        self.was_hit = True
        for direction in directions:
            # it is possible that while trying to escape, the soldier goes outside the board
            # to prevent that, ensure limits with max and min functions
            eff_speed = self.speed
            is_two_axes = direction[0] != 0 and direction[1] != 0

            new_position = self.position
            if not is_two_axes:
                step = (self.speed * direction[0], self.speed * direction[1])
                # if moving in only x-axis or y-axis, simply clamp within limits of the board
                new_position = (
                    max(0, min(self.position[0] + step[0], self.board_size - 1)),
                    max(0, min(self.position[1] + step[1], self.board_size - 1)),
                )

            while eff_speed > 0 and is_two_axes:
                # if moving in two axes, check the maximum movement possible within the limits of the board
                step = (eff_speed * direction[0], eff_speed * direction[1])
                new_position = (self.position[0] + step[0], self.position[1] + step[1])
                if 0 <= new_position[0] < self.board_size and 0 <= new_position[1] < self.board_size:
                    break
                eff_speed -= 1

            if eff_speed == 0:
                continue

            if not is_position_in_blast_radius(new_position, missile_type, missile_position, self.board_size):
                self.position = new_position
                self.was_hit = False
                self.console.print(f"[green]Escaping to {self.position}[/green]")
                break

        if self.was_hit:
            self.console.print("[bold red]Hit by missile[/bold red]")


class Commander(Soldier):
    time_to_missile: int
    game_time: int
    cur_time: int
    num_soldiers: int

    alive_soldiers: dict[int, SoldierMetadata]

    _missile_type: int | None = None
    _missile_pos: tuple[int, int] | None = None

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
            self.alive_soldiers = {
                i + 1: {"sid": i + 1, "addr": line.strip(), "position": (-1, -1)} for i, line in enumerate(f)
            }
        self.num_soldiers = len(self.alive_soldiers)
        if self.num_soldiers < MIN_SOLDIERS:
            raise ValueError(f"Need at least {MIN_SOLDIERS} soldiers, but only have {self.num_soldiers}")

    def set_position(self):
        position = (random.randrange(0, self.board_size), random.randrange(0, self.board_size))
        for sid, soldier in self.alive_soldiers.items():
            if position == soldier["position"]:
                position = (random.randrange(0, self.board_size), random.randrange(0, self.board_size))
        self.position = position

        self.console.print(f"Commander starting at {self.position} with speed {self.speed}")

    def send_startup_message(self):
        for sid in self.alive_soldiers:
            with grpc.insecure_channel(self.alive_soldiers[sid]["addr"], options=GRPC_CHANNEL_OPTIONS) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.StartupStatus(war_pb2.StartupRequest(soldier_id=sid, N=self.board_size))
                self.alive_soldiers[sid]["position"] = (resp.current_position.x, resp.current_position.y)

    def send_missile_approaching_message(self):
        self._missile_type, self._missile_pos = spawn_missile(self.board_size)
        # commander takes shelter and then notifies the soldiers
        self.take_shelter(missile_type=self._missile_type, missile_position=self._missile_pos)

        for soldier in self.alive_soldiers.values():
            with grpc.insecure_channel(soldier["addr"], options=GRPC_CHANNEL_OPTIONS) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                stub.MissileApproaching(
                    war_pb2.MissileApproachingRequest(
                        target=war_pb2.Point(x=self._missile_pos[0], y=self._missile_pos[1]),
                        time_to_hit=self.time_to_missile,
                        type=self._missile_type,
                    )
                )

    def send_round_status_message(self):
        to_delete = []
        for sid, soldier in self.alive_soldiers.items():
            with grpc.insecure_channel(soldier["addr"], options=GRPC_CHANNEL_OPTIONS) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.RoundStatus(war_pb2.Empty())
                if resp.was_hit:
                    # delete soldier from alive_soldiers
                    to_delete.append(sid)
                else:
                    # update soldier position
                    soldier["position"] = (resp.updated_position.x, resp.updated_position.y)
        for sid in to_delete:
            self.alive_soldiers.pop(sid)

    def send_new_commander_message(self):
        # select new commander randomly
        new_commander = random.choice(list(self.alive_soldiers.values()))
        alive_soldiers_grpc = [
            war_pb2.AliveSoldier(
                sid=sid,
                addr=soldier["addr"],
                position=war_pb2.Point(x=soldier["position"][0], y=soldier["position"][1]),
            )
            for sid, soldier in self.alive_soldiers.items()
            if sid != new_commander["sid"]
        ]
        with grpc.insecure_channel(new_commander["addr"], options=GRPC_CHANNEL_OPTIONS) as channel:
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
        for soldier in self.alive_soldiers.values():
            with grpc.insecure_channel(soldier["addr"], options=GRPC_CHANNEL_OPTIONS) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                stub.GameOver(war_pb2.Empty())

    def run_game_loop(self):
        self.print_layout()
        while not self.game_over and self.is_alive:
            self.send_missile_approaching_message()
            time.sleep(self.time_to_missile)
            self.cur_time += self.time_to_missile
            self.send_round_status_message()
            self.print_layout()
            self.is_alive = not self.was_hit
            if self.cur_time >= self.game_time:
                self.game_over = True

        if self.is_alive:
            self.send_game_over()
            self._missile_type = None
            self._missile_pos = None
        elif len(self.alive_soldiers) > 0:
            self.send_new_commander_message()

    def print_layout(self):
        self.console.rule(f"After Round {self.cur_time // self.time_to_missile}")
        table = Table(title="Board", show_header=True, show_lines=True, box=HEAVY_HEAD)
        for i in range(self.board_size + 1):
            table.add_column(" " if i == 0 else str(i - 1))

        for i in range(self.board_size):
            row = [f"[bold]{i}[/bold]"]
            for j in range(self.board_size):
                cur_pos = (i, j)
                cell_done = False
                if not self.was_hit and self.position == cur_pos:
                    row.append("[green]C[/green]")
                    cell_done = True
                elif self._missile_type is not None and is_position_in_blast_radius(
                    cur_pos, self._missile_type, self._missile_pos, self.board_size
                ):
                    row.append("[red]X[/red]")
                    cell_done = True
                else:
                    for sid, soldier in self.alive_soldiers.items():
                        if soldier["position"] == cur_pos:
                            row.append(f"[green]{sid}[/green]")
                            cell_done = True
                if not cell_done:
                    row.append(" ")
            table.add_row(*row)
        self.console.print(table)
        if self._missile_type is not None:
            self.console.print(f"Missile M{self._missile_type} at {self._missile_pos}")

        dead_soldiers = [i for i in range(1, self.num_soldiers + 1) if i not in self.alive_soldiers]
        self.console.print(
            f"Dead Soldiers: {dead_soldiers}",
            f"Current Time: {self.cur_time}",
            f"Total Time: {self.game_time}",
            sep="\t",
        )
        self.console.rule()


class War(war_pb2_grpc.WarServicer):
    soldier: Soldier
    commander: Commander

    def StartupStatus(self, request, context):
        self.soldier.sid = request.soldier_id
        self.soldier.board_size = request.N
        self.soldier.position = (
            random.randrange(0, self.soldier.board_size),
            random.randrange(0, self.soldier.board_size),
        )

        self.soldier.console.print(
            f"Soldier {self.soldier.sid} starting at {self.soldier.position} with speed {self.soldier.speed}"
        )

        return war_pb2.StartupResponse(
            current_position=war_pb2.Point(x=self.soldier.position[0], y=self.soldier.position[1]),
        )

    def MissileApproaching(self, request, context):
        self.soldier.take_shelter(missile_type=request.type, missile_position=(request.target.x, request.target.y))
        return war_pb2.Empty()

    def RoundStatus(self, request, context):
        self.soldier.is_alive = not self.soldier.was_hit
        # if soldier is dead, updated_position should be ignored
        return war_pb2.RoundStatusResponse(
            soldier_id=self.soldier.sid,
            was_hit=self.soldier.was_hit,
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
        self.soldier.console.print("Game ending now...")
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
        print(f"[bold red]Board size must at least be {MIN_BOARD_SIZE}[/bold red]", file=sys.stderr)
        sys.exit(1)
    if conf["t"] > conf["T"]:
        print("[bold red]Frequency between missiles cannot be greater than game time[/bold red]", file=sys.stderr)
        sys.exit(1)

    if args.commander:
        c = Commander(conf["N"], conf["t"], conf["T"], cur_time=0, is_initial_commander=True)
        c.send_startup_message()
        c.set_position()
        c.run_game_loop()
    else:
        s = Soldier()
        war_service = War()
        war_service.soldier = s
        server = grpc.server(ThreadPoolExecutor(max_workers=10), options=GRPC_CHANNEL_OPTIONS)
        war_pb2_grpc.add_WarServicer_to_server(war_service, server)
        server.add_insecure_port(conf["addr"])
        server.start()

        try:
            while True:
                if not s.is_alive or s.game_over or s.is_promoted:
                    server.stop(GRPC_SERVER_SHUTDOWN_TIMEOUT)
                    break
        except KeyboardInterrupt:
            server.stop(GRPC_SERVER_SHUTDOWN_TIMEOUT)
            sys.exit(1)

        # now onwards it behaves as commander
        if s.is_promoted:
            war_service.commander.run_game_loop()
