import os
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypedDict

import grpc

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
    radius = board_size - missile_type
    return missile_type, (
        random.randint(min(missile_type, radius), max(missile_type, radius)),
        random.randint(min(missile_type, radius), max(missile_type, radius)),
    )

def is_point_in_blast_radius(point: tuple[int, int], missile_type: int, missile_position: tuple[int, int]) -> bool:
        """
        Check if the point is within missile blast radius

        Parameters
        ----------
        point
            (x, y) co-ordinates of point which we want to check
        missile_type
            type of missile (see `spawn_missile` for types of missiles)
        missile_position
            (x, y) co-ordinates of the missile's center

        Returns
        -------
        bool
            `True` if the point is in the missile blast radius, `False` otherwise
        """
        return( point[0] >= missile_position[0] - missile_type + 1
            and point[0] <= missile_position[0] + missile_type - 1
            and point[1] >= missile_position[1] - missile_type + 1
            and point[1] <= missile_position[1] + missile_type - 1
        )

def is_valid_point(point: tuple[int, int], N: int) -> bool:
    return (
        point[0] >= 0 and point[0] < N and point[1] >= 0 and point[1] < N
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

    def __init__(self):
        self.game_over = False
        self.is_promoted = False
        self.is_alive = True
        self.was_hit = False
        self.speed = random.randint(0, MAX_SPEED)

    # TODO: @Aayush
    def take_shelter(self, missile_type: int, missile_position: tuple[int, int]):
        # if soldier is in missile blast radius, compute escape path, else don't move
        directions = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
        was_hit = True
        if is_point_in_blast_radius(self.position, missile_type, missile_position):
            print("I am in blast radius")
            for direction in directions:
                step = (missile_type * direction[0], missile_type * direction[0])
                new_position = (self.position[0] + step[0], self.position[1] + step[1])
                if(is_valid_point(new_position, self.board_size)
                   and not is_point_in_blast_radius(new_position, missile_type, missile_position)):
                    # update current position of soldier
                    self.position = new_position
                    print(f"Found safe position as ({self.position[0]}, {self.position[1]})")
                    was_hit = False
                    break
            if was_hit:
                self.was_hit = True
                print("I am dead")



class Commander(Soldier):
    time_to_missile: int
    game_time: int
    board_size: int
    cur_time: int

    alive_soldiers: list[SoldierMetadata]

    def __init__(self, board_size: int, time_to_missile: int, game_time: int, cur_time: int, is_initial_commander: bool):
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
            self.alive_soldiers = [{"sid": i + 1, "addr": line.strip(), "position": (-1, -1)} for i, line in enumerate(f)]

    def send_startup_request(self):
        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                resp = stub.StartupStatus(war_pb2.StartupRequest(soldier_id=soldier["sid"], N=self.board_size))
                soldier["position"] = (resp.current_position.x, resp.current_position.y)
                
    def send_missile_approaching_request(self):
        print("Send missile approaching")
        missile = spawn_missile(self.board_size)
        print(missile)
        # commander himself takes shelter
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
                    self.alive_soldiers = [i for i in self.alive_soldiers if not (i["sid"] == resp.soldier_id)]
                    print(f"Soldier {soldier['sid']} was hit")
                else:
                    # update soldier position
                    soldier["position"] = (resp.updated_position.x, resp.updated_position.y)
                    print(f"{soldier['sid']} -> ({soldier['position'][0]}, {soldier['position'][1]})")


    def send_new_commander_message(self, cur_time):
        # select new commander randomly
        new_commander = self.alive_soldiers[random.randint(0, len(self.alive_soldiers)-1)]
        alive_soldiers_grpc = [
            war_pb2.AliveSoldier(
                sid=soldier["sid"],
                addr=soldier["addr"],
                position=war_pb2.Point(x=soldier["position"][0], y=soldier["position"][1])
            )
            for soldier in self.alive_soldiers
        ]
        with grpc.insecure_channel(new_commander["addr"]) as channel:
            stub = war_pb2_grpc.WarStub(channel)
            stub.NewCommander(
                            war_pb2.NewCommanderRequest(board_size=self.board_size, 
                                time_to_missile=self.time_to_missile, 
                                game_time=self.game_time, 
                                cur_time=cur_time, 
                                alive_soldiers=alive_soldiers_grpc
                            )
            )

    def send_game_over(self):
        for soldier in self.alive_soldiers:
            with grpc.insecure_channel(soldier["addr"]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                stub.GameOver(war_pb2.Empty())

    def print_layout(self):
        # TODO: Print board layout
        pass


class War(war_pb2_grpc.WarServicer):
    soldier: Soldier
    commander: Commander

    def StartupStatus(self, request, context):
        self.soldier.sid = request.soldier_id
        self.soldier.board_size = request.N
        initial_x = random.randint(0, self.soldier.board_size - 1)
        initial_y = random.randint(0, self.soldier.board_size - 1)
        self.soldier.position = (initial_x, initial_y)
        print(f"Soldier {self.soldier.sid} took position {self.soldier.position}")
        return war_pb2.StartupResponse(
            current_position=war_pb2.Point(x=initial_x, y=initial_y),
        )

    def MissileApproaching(self, request, context):
        self.soldier.take_shelter(missile_type=request.type, missile_position=(request.target.x, request.target.y))
        print(f"{self.soldier.sid} -> {self.soldier.position[0]}, {self.soldier.position[1]}")
        return war_pb2.Empty()

    def RoundStatus(self, request, context):
        # if soldier is dead, updated_position is garbage value
        if self.soldier.was_hit:
            self.soldier.is_alive = False
        return war_pb2.RoundStatusResponse(
            soldier_id=self.soldier.sid, 
            was_hit = self.soldier.was_hit, 
            updated_position=war_pb2.Point(x=self.soldier.position[0], y=self.soldier.position[1])
        )
    
    def NewCommander(self, request, context):
        self.soldier.is_promoted = True
        self.commander = Commander(request.board_size, request.time_to_missile, request.game_time, request.cur_time, False)
        # make a note of alive soldiers and remove self entry
        self.commander.alive_soldiers = [
            {
                "sid": soldier.sid, 
                "addr": soldier.addr, 
                "position": (soldier.position.x, soldier.position.y)
            }
            for soldier in request.alive_soldiers
            if soldier.sid != self.soldier.sid
        ]
        self.commander.position = self.soldier.position
        return war_pb2.Empty()


    def GameOver(self, request, context):
        self.soldier.game_over = True
        return war_pb2.Empty()


def start_commander(board_size: int, time_to_missile: int, game_time: int) -> Commander:
    c = Commander(board_size, time_to_missile, game_time, 0, True)
    # if not is_promoted:
    c.send_startup_request()
    # else:
    #     # TODO: Pass alive soldiers for soldier promotion to commander
    #     pass
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


# Execution starts here
random.seed(os.urandom(16))

"""
python warrior.py <sol|com>
"""
args = sys.argv[1:]
argc = len(args)
# TODO: robust error checking for CLI args    
if argc != 1:
    sys.exit("Usage: python warrior.py <sol|com>")
if args[0] != "sol" and args[0] != "com":
    sys.exit("Usage: python warrior.py <sol|com>")


if args[0] == "com":
    N = int(input("Enter dimension of grid(N): "))
    t = int(input("Enter time interval of missile launches(t): "))
    T = int(input("Enter total war time(T): "))
    
    c = start_commander(N, t, T)

    # commander will also take position
    c.position = (random.randint(0, N - 1), random.randint(0, N - 1))

    print(f"Commander took position {c.position}")

    c.print_layout()
    # TODO: remove after testing
    print("Initial arrangement:")
    for soldier in c.alive_soldiers:
        print(f"{soldier['sid']} -> ({soldier['position'][0]}, {soldier['position'][1]})")
    
    timer = c.cur_time
    while timer <= c.game_time:
        c.send_missile_approaching_request()
        time.sleep(c.time_to_missile)
        timer += c.time_to_missile
        c.send_round_status_request()
        if c.was_hit:
            if len(c.alive_soldiers) > 0:
                c.send_new_commander_message(timer)
            c.is_alive = False
            break

    if c.is_alive:
        c.send_game_over()

elif args[0] == "sol":
    ip = input("Enter your IP address: ")
    port = input("Enter your port: ")

    s = Soldier()
    war_service = War()
    war_service.soldier = s
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    war_pb2_grpc.add_WarServicer_to_server(war_service, server)
    server.add_insecure_port(ip + ":" + port)
    server.start()
    print(f"Soldier active on {ip}:{port}")
    # server.wait_for_termination()
    # TODO: run on a different thread
    while True:
        if not s.is_alive or s.game_over or s.is_promoted:
            # stop gRPC server
            server.stop(10)
            break

    # now onwards it behaves as commander
    if s.is_promoted:
        c = war_service.commander
        timer = c.cur_time
        while timer <= c.game_time:
            c.send_missile_approaching_request()
            time.sleep(c.time_to_missile)
            timer += c.time_to_missile
            c.send_round_status_request()
            if c.was_hit:
                if len(c.alive_soldiers) > 0:
                    c.send_new_commander_message(timer)
                c.is_alive = False
                break

        if c.is_alive:
            c.send_game_over()