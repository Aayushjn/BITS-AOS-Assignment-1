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

Inputs:

```toml
N = 8
M = 6
t = 3
T = 15
```

Scenarios:

- Simulation 1
  - Starting position

    ![Starting Position](./img/scenario-1-start-layout.png)
  - Output at soldier 5

    ![Soldier 5 Output](./img/scenario-1-soldier-5-output.png)
  - Board after missile hit
    
    ![Missile hit in round 1](./img/scenario-1-missile-hit.png)
  - Soldiers sharing cell after escaping missile
    
    ![Soldiers sharing cell](./img/scenario-1-cell-sharing.png)
  - Game won
    
    ![Game Won](./img/scenario-1-game-won.png)

- Simulation 2
  - Starting position

    ![Starting Position](./img/scenario-2-start-layout.png)
  - Commander hit by missile
  
    ![Commander hit by missile](./img/scenario-2-commander-hit.png)
  - New commander resuming duties
  
    ![New commander resuming duties](./img/scenario-2-new-commander-resume.png)
  - Winning with 50% alive soldiers
  
    ![Winning with 50% alive soldiers](./img/scenario-2-win-at-50-percent.png)

- Simulation 3
  - Starting position
  
    ![Starting position](./img/scenario-3-start-layout.png)
  - Round 1
  
    ![Game lost](./img/scenario-3-game-lost.png)
