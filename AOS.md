Constraints:
- N > 4
- 0 <= Si <= 4
- 0 < t <= T
- M >= 2

| Commander | Soldier |
|:-:|:-:|
| RPC client | RPC server + client |
| All hyperparameters as input + soldier IP info | Board size, speed as input |
| Generate starting locations and send to soldiers | Update locations after every round |

### RPC Messages:
- at round start `MissileApproaching(x-y, time-to-hit, type)` -> broadcast
- at round end `RoundStatus(soldier-id)`
    - `HitStatus(soldier-id, hit-flag, updated-x-y)` -> `hit-flag` and `updated-x-y` are mutually exclusive
- at round end `NewCommander(soldier-info, hyperparameters, remaining-time)`
- `StartStatus(soldier-id, N)` (internal)
    - `StartReply(soldier-id, x-y)`

### Startup Logic

1. Start `M-1` soldiers with IP:port (CLI args)
2. Start commander with hyperparameters (CLI args) and pass file containing soldier info (manually create file)
    - soldier-info -> (soldier-id, ip:port)
    - internally maintains
      ```python
      {
        "soldier-id": {
            "addr": "ip:port",
            "pos": (x, y),
        },
      }
      ```
3. Send `StartStatus` and get reply
4. Start timer of `T` seconds
5. Broadcast `MissileApproaching`


```python
class Soldier:
    sid: int
    speed: int
    pos: tuple[int, int]

class Commander(Soldier):
    alive_soldiers # see above metadata
```
