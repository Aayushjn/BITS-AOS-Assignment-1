### Development/Test Environment

- Language: **Python 3.11** 
- RPC Framework: **gRPC**
- OS: **Linux/Windows**

### Design Considerations

- Minimum board size is **8**
  - If an M4 missile lands directly in the center of 7x7 grid, it will cover the entire grid and the game may end in a 
    single round itself
- Since the commander initiates any messages, the commander runs a gRPC client while the soldiers 
  run gRPC servers
  - _M_ soldiers need to be started first before the commander can be started
  - Since the commander needs to be able to communicate with the soldiers, a list of addresses needs to be passed to it
- Players are allowed to share cells on the board
- At the start of the game, the commander selects a random position for itself that is not shared by any soldier
- To decouple the RPC from the core behavior of the soldiers, the RPC service takes the soldier (and a commander) as a 
  dependency
  - Since game logic depends on the incoming RPC messages, the RPC service itself modifies soldier states
- To simplify configuring the commander, a `config.toml` file (documented in [readme.txt](./readme.txt)) is used

_Note: The code documents most (if not all) the implementation details that may be present. Thus, no other 
documentation on the code is included in this document._

___

### Testing

Since the game is designed to be completely random (including starting positions and speeds), it is not possible to 
force certain conditions without modifying the code. Nevertheless, we have tested with variations of the 
hyperparameters (including illegal values) specified via the configuration file.

Scenarios verified:
- Missiles do not hit any soldiers for the entirety of the game
- All players manage to escape in all rounds
- Soldiers attempt to escape missile by running out-of-bounds but are limited to board limits
- Soldiers get hit and report their status to the commander
- Commander gets hit and transfers control to a randomly elected soldier
- More than 50% soldiers are hit by missiles and the game is lost
- No players survive the game 
