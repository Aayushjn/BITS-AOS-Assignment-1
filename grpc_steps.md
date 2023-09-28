# Steps for developement of gRPC call
1. Build .proto file(s) and save it in proto/ folder
2. Run
    ```
    python -m grpc_tools.protoc -I ./proto --python_out=. --pyi_out=. --grpc_python_out=. ./proto/<proto_file_name>.proto
    ```
    This will generate 3 files the current directory:
    - `<proto_file_name>_pb2_grpc.py`
    - `<proto_file_name>_pb2.py`
    -  `<proto_file_name>_pb2.pyi` 
3. Server code layout
   ```
   from concurrent import futures
   import logging

   import grpc
   import <<proto_file_name>_pb2>
   import <<proto_file_name>_pb2_grpc>

   class <ServiceName>(<proto_file_name>_pb2_grpc.<ServiceName>Servicer):
       def <MethodName>(self, request, context):
           # implementation


   def serve():
       port = "50051"
       server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
       <proto_file_name>_pb2_grpc.add_<ServiceName>Servicer_to_server(<ServiceName>(), server)
       server.add_insecure_port("[::]:" + port)
       server.start()
       print("Server started, listening on " + port)
       server.wait_for_termination()


   if __name__ == "__main__":
       logging.basicConfig()
       serve()
   ```

4. Client code layout
    ```
    from __future__ import print_function

    import logging

    import grpc
    import <proto_file_name>_pb2
    import <proto_file_name>_pb2_grpc


    def run():
        server_ip = # some ip address
        server_port = # some port
        with grpc.insecure_channel(server_ip + ":" + server_port) as channel:
            stub = <proto_file_name>_pb2_grpc.<ServiceName>Stub(channel)
            response = stub.<MethodName>(<proto_file_name>_pb2.<MethodRequest>(name="you"))

    if __name__ == "__main__":
        logging.basicConfig()
        run()
    ```