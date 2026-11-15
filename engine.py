# tiny-chess-01 engine: 0x88 alpha-beta + quiescence, transposition table,
# killer moves, LMR. Deterministic: fixed node budget per move, no clock.
# Plays the make.fun env at MAKEFUN_ENV_URL (POST /game, /move, /resign).
# Python 3.13 standard library only.
import json, os, sys, urllib.request, random

V = (0, 100, 320, 330, 500, 900, 0)
# Piece-square tables, rank 8 first (Michniewski's simplified eval).
PT = (
    # pawn
    (0,0,0,0,0,0,0,0, 50,50,50,50,50,50,50,50, 10,10,20,30,30,20,10,10,
     5,5,10,25,25,10,5,5, 0,0,0,20,20,0,0,0, 5,-5,-10,0,0,-10,-5,5,
     5,10,10,-20,-20,10,10,5, 0,0,0,0,0,0,0,0),
    # knight
    (-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,0,0,0,-20,-40,
     -30,0,10,15,15,10,0,-30, -30,5,15,20,20,15,5,-30,
     -30,0,15,20,20,15,0,-30, -30,5,10,15,15,10,5,-30,
     -40,-20,0,5,5,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50),
    # bishop
    (-20,-10,-10,-10,-10,-10,-10,-20, -10,0,0,0,0,0,0,-10,
     -10,0,5,10,10,5,0,-10, -10,5,5,10,10,5,5,-10,
     -10,0,10,10,10,10,0,-10, -10,10,10,10,10,10,10,-10,
     -10,5,0,0,0,0,5,-10, -20,-10,-10,-10,-10,-10,-10,-20),
    # rook
    (0,0,0,0,0,0,0,0, 5,10,10,10,10,10,10,5,
     -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
     -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
     -5,0,0,0,0,0,0,-5, 0,0,0,5,5,0,0,0),
    # queen
    (-20,-10,-10,-5,-5,-10,-10,-20, -10,0,0,0,0,0,0,-10,
     -10,0,5,5,5,5,0,-10, -5,0,5,5,5,5,0,-5,
     0,0,5,5,5,5,0,-5, -10,5,5,5,5,5,0,-10,
     -10,0,5,0,0,0,0,-10, -20,-10,-10,-5,-5,-10,-10,-20),
    # king middlegame
    (-30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
     -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
     -20,-30,-30,-40,-40,-30,-30,-20, -10,-20,-20,-20,-20,-20,-20,-10,
     20,20,0,0,0,0,20,20, 20,30,10,0,0,10,30,20),
    # king endgame
    (-50,-40,-30,-20,-20,-30,-40,-50, -30,-20,-10,0,0,-10,-20,-30,
     -30,-10,20,30,30,20,-10,-30, -30,-10,30,40,40,30,-10,-30,
     -30,-10,30,40,40,30,-10,-30, -30,-10,20,30,30,20,-10,-30,
     -30,-30,0,0,0,0,-30,-30, -50,-30,-30,-30,-30,-30,-30,-50),
)
KN = (-33, -31, -18, -14, 14, 18, 31, 33)
KI = (-17, -16, -15, -1, 1, 15, 16, 17)
RD = (-16, -1, 1, 16)
BD = (-17, -15, 15, 17)
CM = {4: 3, 7: 1, 0: 2, 116: 12, 119: 4, 112: 8}  # castling-right bits lost
PM = {"q": 5, "r": 4, "b": 3, "n": 2}  # promotion char -> piece
PC = "  nbrq"  # piece -> promotion char

_R = random.Random(20261115)
ZW = [[_R.getrandbits(64) for _ in range(128)] for _ in range(13)]  # by pc+6
ZC = [_R.getrandbits(64) for _ in range(16)]  # by castling rights
ZE = [_R.getrandbits(64) for _ in range(128)]  # by ep square

B = [0] * 128
S = 1
CR = 0
EP = -1
KEY = 0
WK = 4
BK = 116
H = set()       # game history of keys, for repetition
TT = {}
KL = {}         # killer moves per ply
ND = 0
BUD = 200000     # nodes per move
G = 0           # game number in play
URL = ""


def sq(s):
    return (ord(s[0]) - 97) + (int(s[1]) - 1) * 16


def uci(s):
    return chr(97 + (s & 7)) + str((s >> 4) + 1)


def parse(fen):
    global S, CR, EP, KEY, WK, BK
    w = fen.split()
    for i in range(128):
        B[i] = 0
    r = f = 0
    for c in w[0]:
        if c == "/":
            r += 1
            f = 0
        elif c.isdigit():
            f += int(c)
        else:
            q = "PNBRQK".index(c.upper()) + 1
            s = (7 - r) * 16 + f
            B[s] = q if c.isupper() else -q
            if q == 6:
                if c.isupper():
                    WK = s
                else:
                    BK = s
            f += 1
    S = 1 if w[1] == "w" else -1
    CR = 0
    for c in w[2]:
        if c == "K":
            CR |= 1
        if c == "Q":
            CR |= 2
        if c == "k":
            CR |= 4
        if c == "q":
            CR |= 8
    EP = sq(w[3]) if w[3] != "-" else -1
    KEY = 0
    for i in range(128):
        p = B[i]
        if p:
            KEY ^= ZW[p + 6][i]
    if S < 0:
        KEY ^= 1
    KEY ^= ZC[CR]
    if EP >= 0:
        KEY ^= ZE[EP]
    H.add(KEY)


def atk(s, by):
    b = B
    # pawns: a white pawn attacks from s-15/s-17, a black one from s+15/s+17
    d = -by
    for o in (15, 17):
        t = s + o * d
        if 0 <= t < 128 and not t & 0x88 and b[t] == by:
            return True
    for o in KN:
        t = s + o
        if 0 <= t < 128 and not t & 0x88 and b[t] == by * 2:
            return True
    for o in KI:
        t = s + o
        if 0 <= t < 128 and not t & 0x88 and b[t] == by * 6:
            return True
    for o in RD:
        t = s + o
        while 0 <= t < 128 and not t & 0x88:
            q = b[t]
            if q:
                if q == by * 4 or q == by * 5:
                    return True
                break
            t += o
    for o in BD:
        t = s + o
        while 0 <= t < 128 and not t & 0x88:
            q = b[t]
            if q:
                if q == by * 3 or q == by * 5:
                    return True
                break
            t += o
    return False


def gen(cap):
    b = B
    s_side = S
    ms = []
    for s in range(128):
        p = b[s]
        if not p or (p > 0) != (s_side > 0):
            continue
        a = abs(p)
        if a == 1:
            d = 16 * s_side
            t = s + d
            if not b[t] and not cap:
                if (t >> 4) in (0, 7):
                    ms.extend((s, t, q) for q in (5, 4, 3, 2))
                else:
                    ms.append((s, t, 0))
                    t2 = s + 2 * d
                    if ((s >> 4) == 1 and s_side > 0 or (s >> 4) == 6 and s_side < 0) and not b[t2]:
                        ms.append((s, t2, 0))
            for o in (15, 17):
                t = s + o * s_side
                if 0 <= t < 128 and not t & 0x88 and (b[t] * s_side < 0 or t == EP):
                    if (t >> 4) in (0, 7):
                        ms.extend((s, t, q) for q in (5, 4, 3, 2))
                    else:
                        ms.append((s, t, 0))
        elif a in (2, 6):
            for o in KN if a == 2 else KI:
                t = s + o
                if 0 <= t < 128 and not t & 0x88 and b[t] * s_side <= 0 and (b[t] or not cap):
                    ms.append((s, t, 0))
        else:
            for o in RD if a == 4 else BD if a == 3 else RD + BD:
                t = s + o
                while 0 <= t < 128 and not t & 0x88:
                    q = b[t]
                    if q:
                        if q * s_side < 0:
                            ms.append((s, t, 0))
                        break
                    if not cap:
                        ms.append((s, t, 0))
                    t += o
    if not cap:
        if s_side > 0:
            if (CR & 1 and not b[5] and not b[6] and b[4] == 6 and b[7] == 4
                    and not atk(4, -1) and not atk(5, -1) and not atk(6, -1)):
                ms.append((4, 6, 0))
            if (CR & 2 and not b[3] and not b[2] and not b[1] and b[4] == 6 and b[0] == 4
                    and not atk(4, -1) and not atk(3, -1) and not atk(2, -1)):
                ms.append((4, 2, 0))
        else:
            if (CR & 4 and not b[117] and not b[118] and b[116] == -6 and b[119] == -4
                    and not atk(116, 1) and not atk(117, 1) and not atk(118, 1)):
                ms.append((116, 118, 0))
            if (CR & 8 and not b[115] and not b[114] and not b[113] and b[116] == -6 and b[112] == -4
                    and not atk(116, 1) and not atk(115, 1) and not atk(114, 1)):
                ms.append((116, 114, 0))
    return ms


def make(m):
    global S, CR, EP, KEY, WK, BK
    f, t, p = m
    pc = B[f]
    cp = B[t]
    cs = 0
    zw = ZW
    KEY ^= zw[pc + 6][f]
    if t == EP and abs(pc) == 1:
        cs = t - 16 * S
        cp = B[cs]
        B[cs] = 0
        KEY ^= zw[cp + 6][cs]
    elif cp:
        KEY ^= zw[cp + 6][t]
    if p:
        B[f] = 0
        B[t] = S * p
        KEY ^= zw[S * p + 6][t]
    else:
        B[f] = 0
        B[t] = pc
        KEY ^= zw[pc + 6][t]
    if abs(pc) == 6:
        if S > 0:
            WK = t
        else:
            BK = t
        if abs(f - t) == 2:
            rf = (7 if t > f else 0) + (112 if S < 0 else 0)
            rt = (5 if t > f else 3) + (112 if S < 0 else 0)
            B[rt] = B[rf]
            B[rf] = 0
            KEY ^= zw[4 + 6][rf] ^ zw[4 + 6][rt] if S > 0 else zw[-4 + 6][rf] ^ zw[-4 + 6][rt]
    u = (m, cp, cs, CR, EP)
    ncr = CR & ~(CM.get(f, 0) | CM.get(t, 0))
    KEY ^= ZC[CR] ^ ZC[ncr]
    CR = ncr
    if EP >= 0:
        KEY ^= ZE[EP]
    nep = t - 16 * S if abs(pc) == 1 and abs(f - t) == 32 else -1
    EP = nep
    if nep >= 0:
        KEY ^= ZE[nep]
    S = -S
    KEY ^= 1
    return u


def unmake(u):
    global S, CR, EP, KEY, WK, BK
    m, cp, cs, ocr, oep = u
    f, t, p = m
    S = -S
    KEY ^= 1
    # key: drop post-move castling/ep factors, restore the pre-move ones
    KEY ^= ZC[CR] ^ ZC[ocr]
    if EP >= 0:
        KEY ^= ZE[EP]
    if oep >= 0:
        KEY ^= ZE[oep]
    CR, EP = ocr, oep
    pc = B[t]
    zw = ZW
    if abs(pc) == 6:
        if S > 0:
            WK = f
        else:
            BK = f
        if abs(f - t) == 2:
            rf = (7 if t > f else 0) + (112 if S < 0 else 0)
            rt = (5 if t > f else 3) + (112 if S < 0 else 0)
            B[rf] = B[rt]
            B[rt] = 0
            KEY ^= zw[4 + 6][rf] ^ zw[4 + 6][rt] if S > 0 else zw[-4 + 6][rf] ^ zw[-4 + 6][rt]
    if p:
        B[t] = 0
        KEY ^= zw[S * p + 6][t]
        B[f] = S
        KEY ^= zw[S + 6][f]
    else:
        B[t] = 0
        KEY ^= zw[pc + 6][t]
        B[f] = pc
        KEY ^= zw[pc + 6][f]
    if cs:
        B[cs] = cp
        KEY ^= zw[cp + 6][cs]
    elif cp:
        B[t] = cp
        KEY ^= zw[cp + 6][t]


def ev():
    b = B
    pt = PT
    v = V
    s = 0
    mat = 0
    wb = bb = 0
    wk = bk = -1
    for i in range(128):
        p = b[i]
        if not p:
            continue
        a = abs(p)
        mat += v[a]
        q = i if p > 0 else i ^ 112
        s += (v[a] + pt[a - 1][(7 - (q >> 4)) * 8 + (q & 7)]) * (1 if p > 0 else -1)
        if a == 3:
            if p > 0:
                wb += 1
            else:
                bb += 1
        elif a == 6:
            if p > 0:
                wk = i
            else:
                bk = i
    if wb > 1:
        s += 30
    if bb > 1:
        s -= 30
    if mat < 1300:
        for k, g in ((wk, 1), (bk, -1)):
            if k < 0:
                continue
            q = k if g > 0 else k ^ 112
            x = (7 - (q >> 4)) * 8 + (q & 7)
            s += (pt[6][x] - pt[5][x]) * g
    return s if S > 0 else -s


def order(ms, tt, pl):
    b = B
    kl = KL.get(pl, ())
    def sc(m):
        v = 0
        if tt and m == tt:
            v += 100000
        c = b[m[1]]
        if c:
            v += V[abs(c)] * 10 - V[abs(b[m[0]])]
        if m in kl:
            v += 5000
        if m[2]:
            v += 9000
        return v
    ms.sort(key=sc, reverse=True)
    return ms


def qs(a, b):
    global ND
    ND += 1
    if ND > BUD:
        raise TimeoutError
    ks = WK if S > 0 else BK
    chk = atk(ks, -S)
    if not chk:
        st = ev()
        if st >= b:
            return b
        if st > a:
            a = st
    ms = gen(1) if not chk else gen(0)
    if not chk:
        ms = [m for m in ms if m[2] or not B[m[1]] or V[abs(B[m[1]])] >= V[abs(B[m[0]])]]
        ms.sort(key=lambda m: V[abs(B[m[1]])] * 10 - V[abs(B[m[0]])], reverse=True)
    for m in ms:
        u = make(m)
        if atk(WK if S < 0 else BK, S):
            unmake(u)
            continue
        sc = -qs(-b, -a)
        unmake(u)
        if sc >= b:
            return b
        if sc > a:
            a = sc
    return a


def sr(d, a, b, pl):
    global ND
    ND += 1
    if ND > BUD:
        raise TimeoutError
    if KEY in H:
        return 0
    e = TT.get(KEY)
    ttm = None
    if e and e[0] >= d:
        _, fl, v, ttm = e
        if fl == 0:
            return v
        if fl == 1 and v >= b:
            return b
        if fl == 2 and v <= a:
            return a
    if d <= 0:
        return qs(a, b)
    if len(TT) > 300000:
        TT.clear()
    ms = gen(0)
    if not ms:
        return -99999 + pl if atk(WK if S > 0 else BK, -S) else 0
    order(ms, ttm, pl)
    fl = 2
    bv = -999999
    bs = None
    for i, m in enumerate(ms):
        u = make(m)
        if atk(WK if S < 0 else BK, S):
            unmake(u)
            continue
        if i > 3 and d >= 3 and not B[m[1]] and not m[2]:
            sc = -sr(d - 2, -b, -a, pl + 1)
            if sc > a:
                sc = -sr(d - 1, -b, -a, pl + 1)
        else:
            sc = -sr(d - 1, -b, -a, pl + 1)
        unmake(u)
        if sc > bv:
            bv = sc
            bs = m
        if sc > a:
            a = sc
            fl = 0
        if a >= b:
            KL.setdefault(pl, []).insert(0, m)
            KL[pl] = KL[pl][:2]
            fl = 1
            break
    TT[KEY] = (d, fl, bv, bs)
    return bv


def best(legal):
    global ND, KL
    lm = [(sq(m[:2]), sq(m[2:4]), PM.get(m[4:], 0)) for m in legal]
    bm = lm[0]
    KL = {}
    ND = 0
    try:
        for d in range(1, 5):
            ba = -999999
            bb = None
            for m in sorted(lm, key=lambda m: m == bm, reverse=True):
                u = make(m)
                if atk(WK if S < 0 else BK, S):
                    unmake(u)
                    continue
                sc = -sr(d - 1, -999999, 999999, 1)
                unmake(u)
                if sc > ba:
                    ba = sc
                    bb = m
            if bb:
                bm = bb
    except TimeoutError:
        pass
    return bm


def post(p, b):
    q = urllib.request.Request(
        URL + p, data=json.dumps(b).encode(),
        headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(q) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(p + " HTTP " + str(e.code))


def main():
    global G, URL
    URL = os.environ.get("MAKEFUN_ENV_URL") or sys.exit("no env")
    st = post("/game", {})
    while st.get("status") != "done":
        if st.get("status") == "over":
            st = post("/game", {})
            continue
        if st["game"] != G:
            G = st["game"]
            H.clear()
            TT.clear()
        parse(st["fen"])
        m = best(st["legal_moves"])
        u = uci(m[0]) + uci(m[1]) + (PC[m[2]] if m[2] else "")
        st = post("/move", {"game": st["game"], "move": u})
    print(st)


if __name__ == "__main__":
    main()
