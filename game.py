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
from rich.box import SQUARE
from rich.console import Console
from rich.table import Table

import war_pb2
import war_pb2_grpc

MAX_SPEED = 4
MIN_BOARD_SIZE = 8
MIN_SOLDIERS = 3

GRPC_SERVER_SHUTDOWN_TIMEOUT = 10

COLOR_RED = "#ed1515"
COLOR_GREEN = "#11d016"
COLOR_YELLOW = "#ffdf33"
COLOR_BLUE = "#89ddff"
COLOR_WHITE = "#ffffff"


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
    """
    Soldier metadata is maintained by the commander. This class is present simply to ensure "strict typing" in the code
    """

    sid: int | str
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

    console: Console

    def __init__(self):
        self.game_over = False
        self.is_promoted = False
        self.is_alive = True
        self.was_hit = False
        self.speed = random.randint(0, MAX_SPEED)

        self.console = Console()

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
            self.console.print(f"[bold {COLOR_RED}]Hit by missile[/bold {COLOR_RED}]")
            return

        self.was_hit = True
        # currently two or more soldiers are allowed to share the same cell while setting their position
        # to ensure that soldiers with the same speed are not "stuck" to each other for the entirety of the game
        # sampling the directions allows randomly picking a direction to move in per soldier
        for direction in random.sample(directions, len(directions)):
            eff_speed = self.speed
            is_diagonal = direction[0] != 0 and direction[1] != 0

            new_position = self.position

            # if the soldier is moving along a diagonal, clamping will result in moving to an illegal position
            # consider a soldier with speed 4 at (6, 5) in a 7x7 board
            # if the soldier moves to the top right (-1, 1), it will move to (2, 9) which is out-of-bounds
            # clamping results in the soldier moving to (2, 6) which shouldn't be accessible to the soldier
            # the correct location to move is (5, 6) with an effective speed of 1

            if not is_diagonal:
                step = (self.speed * direction[0], self.speed * direction[1])
                # if moving in only x-axis or y-axis, simply clamp within limits of the board
                new_position = (
                    max(0, min(self.position[0] + step[0], self.board_size - 1)),
                    max(0, min(self.position[1] + step[1], self.board_size - 1)),
                )

            while eff_speed > 0 and is_diagonal:
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
                self.console.print(f"[{COLOR_GREEN}]Escaping to {self.position}[/{COLOR_GREEN}]")
                break

        if self.was_hit:
            self.console.print(f"[bold {COLOR_RED}]Hit by missile[/bold {COLOR_RED}]")


class Commander(Soldier):
    time_to_missile: int
    game_time: int
    cur_time: int
    num_soldiers: int

    alive_soldiers: list[SoldierMetadata]

    _missile_type: int | None = None
    _missile_pos: tuple[int, int] | None = None

    def __init__(
        self,
        board_size: int,
        num_soldiers: int,
        time_to_missile: int,
        game_time: int,
        cur_time: int,
        is_initial_commander: bool,
    ):
        super().__init__()

        self.sid = 0
        self.board_size = board_size
        self.num_soldiers = num_soldiers
        self.time_to_missile = time_to_missile
        self.game_time = game_time
        self.cur_time = cur_time
        if is_initial_commander:
            self._read_soldier_inventory()

    def _read_soldier_inventory(self):
        with Path("config.toml").open("rb") as f:
            soldiers = tomllib.load(f)["soldiers"]
            self.alive_soldiers = [
                {
                    "sid": i + 1,
                    "addr": addr,
                    "position": (-1, -1),
                }
                for i, addr in enumerate(soldiers)
            ]

        if (real_count := len(self.alive_soldiers)) < self.num_soldiers:
            raise ValueError(f"Need at least {self.num_soldiers} soldiers, but only have {real_count}")
        elif len(soldiers) > self.num_soldiers:
            self.console.print(f"[{COLOR_YELLOW}]Ignoring extra soldiers...[/{COLOR_YELLOW}]")

    def set_position(self):
        """
        Set commander's position such that commander does not share cell with other soldiers.
        Through the course of the game, the commander may share starting location with others but not at the start
        """
        position = (random.randrange(0, self.board_size), random.randrange(0, self.board_size))
        for soldier in self.alive_soldiers:
            if position == soldier["position"]:
                position = (random.randrange(0, self.board_size), random.randrange(0, self.board_size))
        self.position = position

        self.console.print(
            f"Commander starting at [{COLOR_BLUE}]{self.position}[/{COLOR_BLUE}] with speed "
            f"[{COLOR_BLUE}]{self.speed}[/{COLOR_BLUE}]"
        )

    def send_startup_message(self):
        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.StartupStatus(war_pb2.StartupRequest(soldier_id=soldier["sid"], N=self.board_size))
                soldier["position"] = (resp.current_position.x, resp.current_position.y)

    def send_missile_approaching_message(self):
        self._missile_type, self._missile_pos = spawn_missile(self.board_size)
        # commander takes shelter and then notifies the soldiers
        self.take_shelter(missile_type=self._missile_type, missile_position=self._missile_pos)

        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
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
        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.RoundStatus(war_pb2.Empty())
                if resp.was_hit:
                    # delete soldier from alive_soldiers
                    to_delete.append(soldier["sid"])
                else:
                    # update soldier position
                    soldier["position"] = (resp.updated_position.x, resp.updated_position.y)
        self.alive_soldiers = [soldier for soldier in self.alive_soldiers if soldier["sid"] not in to_delete]

    def send_new_commander_message(self):
        # select new commander randomly
        new_commander = random.choice(self.alive_soldiers)
        self.console.print(f"[{COLOR_YELLOW}]Elected soldier {new_commander['sid']} as new commander![/{COLOR_YELLOW}]")
        alive_soldiers_grpc = [
            war_pb2.AliveSoldier(
                sid=soldier["sid"],
                addr=soldier["addr"],
                position=war_pb2.Point(x=soldier["position"][0], y=soldier["position"][1]),
            )
            for soldier in self.alive_soldiers
            if soldier["sid"] != new_commander["sid"]
        ]
        with grpc.insecure_channel(new_commander["addr"]) as channel:
            stub = war_pb2_grpc.WarStub(channel)
            stub.NewCommander(
                war_pb2.NewCommanderRequest(
                    board_size=self.board_size,
                    num_soldiers=self.num_soldiers,
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
            self.print_layout()
            status = "WON" if len(self.alive_soldiers) + 1 >= (self.num_soldiers / 2) else "LOST"
            self.console.print(f"[bold {COLOR_GREEN}]GAME {status}![/bold {COLOR_GREEN}]")
        elif len(self.alive_soldiers) > 0:
            self.send_new_commander_message()

    def print_layout(self):
        self.console.rule(f"After Round {self.cur_time // self.time_to_missile}")
        table = Table(title="Board", show_header=False, show_lines=True, box=SQUARE, padding=0)
        for _ in range(self.board_size + 1):
            table.add_column(" ", justify="center", width=3)

        table.add_row("", *[f"[bold {COLOR_YELLOW}]{i}[/bold {COLOR_YELLOW}]" for i in range(self.board_size)])
        for i in range(self.board_size):
            row = [f"[bold {COLOR_YELLOW}]{i}[/bold {COLOR_YELLOW}]"]
            for j in range(self.board_size):
                cur_pos = (i, j)
                cell_item = None
                if self._missile_type is not None and is_position_in_blast_radius(
                    cur_pos, self._missile_type, self._missile_pos, self.board_size
                ):
                    cell_item = f"[{COLOR_RED}]{'M' if self._missile_pos == cur_pos else 'X'}[/{COLOR_RED}]"

                if cell_item is None:
                    soldiers = [
                        f"[{COLOR_GREEN}]{soldier['sid']}[/{COLOR_GREEN}]"
                        for soldier in (self.alive_soldiers + [{"sid": "C", "addr": "0", "position": self.position}])
                        if soldier["position"] == cur_pos
                    ]
                    cell_item = " " if len(soldiers) == 0 else ",".join(soldiers)
                row.append(cell_item)
            table.add_row(*row)
        self.console.print(table)
        if self._missile_type is not None:
            self.console.print(
                f"Missile [{COLOR_BLUE}]M{self._missile_type}[/{COLOR_BLUE}] [{COLOR_WHITE}]at[/{COLOR_WHITE}] "
                f"[{COLOR_BLUE}]{self._missile_pos}[/{COLOR_BLUE}]"
            )

        dead_soldiers = list(
            set(range(1, self.num_soldiers + 1)) - {soldier["sid"] for soldier in self.alive_soldiers} - {self.sid}
        )
        self.console.print(
            f"Dead Soldiers: [{COLOR_BLUE}]{dead_soldiers}[/{COLOR_BLUE}]",
            f"Current Time: [{COLOR_BLUE}]{self.cur_time}[/{COLOR_BLUE}]",
            f"Total Time: [{COLOR_BLUE}]{self.game_time}[/{COLOR_BLUE}]",
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
            f"Soldier [{COLOR_BLUE}]{self.soldier.sid}[/{COLOR_BLUE}] starting at "
            f"[{COLOR_BLUE}]{self.soldier.position}[/{COLOR_BLUE}] with speed "
            f"[{COLOR_BLUE}]{self.soldier.speed}[/{COLOR_BLUE}]"
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
            request.board_size,
            request.num_soldiers,
            request.time_to_missile,
            request.game_time,
            request.cur_time,
            False,
        )
        # make a note of alive soldiers and remove self entry
        self.commander.alive_soldiers = [
            {
                "sid": soldier.sid,
                "addr": soldier.addr,
                "position": (soldier.position.x, soldier.position.y),
            }
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
    parser.add_argument("addr", type=str, help="grpc server address (ignored when running commander)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--commander", action="store_true")
    group.add_argument("--soldier", action="store_true")
    args = parser.parse_args()

    if args.commander:
        with Path("config.toml").open("rb") as f:
            conf = tomllib.load(f)

        if conf["M"] < MIN_SOLDIERS:
            print(f"[bold {COLOR_RED}]Require at least {MIN_SOLDIERS} soldiers[/bold {COLOR_RED}]", file=sys.stderr)
        if conf["N"] < MIN_BOARD_SIZE:
            print(f"[bold {COLOR_RED}]Board size must at least be {MIN_BOARD_SIZE}[/bold {COLOR_RED}]", file=sys.stderr)
            sys.exit(1)
        if conf["t"] > conf["T"]:
            print(
                f"[bold {COLOR_RED}]Frequency between missiles cannot be greater than game time[/bold {COLOR_RED}]",
                file=sys.stderr,
            )
            sys.exit(1)

        c = Commander(conf["N"], conf["M"], conf["t"], conf["T"], cur_time=0, is_initial_commander=True)
        c.send_startup_message()
        c.set_position()
        c.run_game_loop()
    else:
        s = Soldier()
        war_service = War()
        war_service.soldier = s
        server = grpc.server(ThreadPoolExecutor(max_workers=10))
        war_pb2_grpc.add_WarServicer_to_server(war_service, server)
        if ":" not in args.addr:
            port = server.add_insecure_port(f"{args.addr}:0")
            print(f"Running server on port {port}")
        else:
            port = server.add_insecure_port(args.addr)
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
