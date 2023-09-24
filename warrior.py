from __future__ import print_function
from concurrent import futures
import logging
import grpc
import war_pb2
import war_pb2_grpc
import random

import sys


class Soldier:
    soldier_id: int
    speed: int
    current_position: (int, int)

    def __init__(self, soldier_id, speed, current_position):
        self.soldier_id = soldier_id
        self.speed = speed
        self.current_position = current_position


class War(war_pb2_grpc.WarServicer):
    def StartupStatus(self, request, context):
        print("Solder received " + str(request.soldier_id) + " " + str(request.board_size))
        # Soldier initializes a random position, speed
        soldier = Soldier(
            request.soldier_id,
            random.randint(0, 4),
            (random.randint(0, request.board_size - 1), random.randint(0, request.board_size - 1)),
        )
        return war_pb2.StartupResponse(
            soldier_id=soldier.soldier_id,
            current_position=war_pb2.Point(x=soldier.current_position[0], y=soldier.current_position[1]),
        )


# TODO: number of soldiers is predefined, can we do it programatically?
def main():
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
        N = input("Enter dimension of grid(N): ")
        t = input("Enter time interval of missile launches(t): ")
        T = input("Enter total war time(T): ")
        # TODO: should be hardcoded?
        # sol_data_filename = input("Enter file name of soldier data: ")
        # sol_data_file = open(sol_data_filename, 'r')

        client_port = ["50051"]
        for i in range(len(client_port)):
            with grpc.insecure_channel("172.17.84.47:" + client_port[i]) as channel:
                stub = war_pb2_grpc.WarStub(channel)
                response = stub.StartupStatus(war_pb2.StartupRequest(soldier_id=i, N=int(N)))
                print(response.soldier_id, response.current_position.x, response.current_position.y)

    elif args[0] == "sol":
        ip = input("Enter your IP address: ")
        port = input("Enter your port: ")

        logging.basicConfig()
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        war_pb2_grpc.add_WarServicer_to_server(War(), server)
        server.add_insecure_port(ip + ":" + port)
        server.start()
        print("Server started, listening on " + port)
        server.wait_for_termination()


main()
