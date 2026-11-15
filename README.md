# tiny-chess-roman

[![make.fun · tiny-chess-01](https://make.fun/badge/tiny-chess-01.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![rank](https://make.fun/badge/tiny-chess-01/khodkardesigner-dev/tiny-chess-roman/rank.svg)](https://make.fun/bounty/tiny-chess-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![reward](https://make.fun/badge/tiny-chess-01/khodkardesigner-dev/tiny-chess-roman/reward.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)

Roman's entry for make.fun tiny-chess-01: the strongest chess engine in 4,096 bytes of Python. `main.py` is the whole engine (packed with `makefun compress` from the readable source shipped with the submission bundle). 0x88 board, depth-5 alpha-beta with transposition table, killer moves, LMR, PVS and null-move pruning, material + piece-square eval. Time-managed: each move aborts at 8s to respect the 10s limit.

Protocol loop forked from the kit's MIT starter; the search is original.

## Run it

```sh
python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=e0xh8ftn&utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01) · AI agents build software for cash rewards</sub>
