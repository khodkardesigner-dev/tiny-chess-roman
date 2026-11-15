# tiny-chess-roman

Roman's entry for make.fun tiny-chess-01: the strongest chess engine in
4,096 bytes of Python. `main.py` is the whole engine (packed with
`makefun compress` from the readable `engine.py`, kept beside it in the
working tree, not committed). 0x88 board, alpha-beta to a fixed depth of 3
with a good-captures-only quiescence, material + piece-square eval.
Deterministic: fixed depth, fixed node cap, no clock, no randomness.

Protocol loop forked from the kit's MIT starter; the search is original.
