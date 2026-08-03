"""Re-sincroniza um .srt nosso contra o .ass oficial do One Pace no corte atual.

  A. ANCORAS -- so falas longas e com semelhanca alta (>=0.70). Servem apenas
     para tracar a curva tempo-antigo -> tempo-novo (usa-se a maior subsequencia
     crescente; o corte reordena cenas, mas nao inverte o episodio).
  B. GLOBAL  -- TODAS as legendas, ancoras incluidas, disputam as linhas de
     referencia em pe de igualdade, restringidas a uma janela em torno do tempo
     previsto. Sem esta disputa, uma parecenca enganosa fecha o lugar antes de a
     dona legitima o poder reclamar.
  C. ENCAIXE -- o que sobrar, colocado entre as vizinhas ja emparelhadas quando
     a duracao encaixa. Apanha as falas curtas cuja traducao se afastou.

O que ficar sem par desapareceu do corte novo e nao entra no ficheiro.

Uso: python resync4.py NOSSO.srt REFERENCIA.ass [SAIDA.srt]
"""
import re, sys, unicodedata
from bisect import bisect_left
from difflib import SequenceMatcher

SKIP_STYLES = {'Karaoke', 'Default'}
ANCHOR_MINLEN, ANCHOR_MINSCORE = 16, 0.70
WINDOW, ACCEPT, DUR_TOL = 60.0, 0.44, 0.30


def _t(x):
    h, m, s = x.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def fmt(x):
    ms = int(round(max(0.0, x) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', s).split())


def load_ass(p):
    out = []
    for l in open(p, encoding='utf-8', errors='replace'):
        if not l.startswith('Dialogue:'):
            continue
        f = l.split(',', 9)
        if f[3] in SKIP_STYLES:
            continue
        txt = re.sub(r'\{[^}]*\}', '', f[9]).replace('\\N', ' ').strip()
        if txt:
            out.append((_t(f[1]), _t(f[2]), txt))
    return sorted(set(out))


def load_srt(p):
    out = []
    for b in open(p, encoding='utf-8', errors='replace').read().replace('\r', '').split('\n\n'):
        L = b.strip().split('\n')
        if len(L) < 3:
            continue
        m = re.match(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)', L[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        out.append([g[0]*3600+g[1]*60+g[2]+g[3]/1000,
                    g[4]*3600+g[5]*60+g[6]+g[7]/1000, '\n'.join(L[2:])])
    return out


def tsim(a, b):
    return SequenceMatcher(None, norm(a.replace('\n', ' ')), norm(b)).ratio()


def score(a, b):
    d = max(0.0, 1 - abs((b[1]-b[0]) - (a[1]-a[0])) / 1.5)
    return 0.75 * tsim(a[2], b[2]) + 0.25 * d


def lis(pairs):
    a = sorted(pairs)
    n = len(a)
    if not n:
        return []
    best, prev = [1]*n, [-1]*n
    for x in range(n):
        for y in range(x):
            if a[y][1] < a[x][1] and best[y]+1 > best[x]:
                best[x], prev[x] = best[y]+1, y
    k = max(range(n), key=lambda z: best[z])
    out = []
    while k != -1:
        out.append(a[k]); k = prev[k]
    return out[::-1]


def main():
    src, refp = sys.argv[1], sys.argv[2]
    dst = sys.argv[3] if len(sys.argv) > 3 else None
    ours, ref = load_srt(src), load_ass(refp)

    # A ------------------------------------------------------------------
    c = []
    for i, a in enumerate(ours):
        if len(norm(a[2])) < ANCHOR_MINLEN:
            continue
        for j, b in enumerate(ref):
            if len(norm(b[2])) < ANCHOR_MINLEN:
                continue
            s = score(a, b)
            if s >= ANCHOR_MINSCORE:
                c.append((s, i, j))
    c.sort(reverse=True)
    anc, uA, uB = [], set(), set()
    for s, i, j in c:
        if i in uA or j in uB:
            continue
        anc.append((i, j)); uA.add(i); uB.add(j)
    curve = lis(anc)
    print(f"A. ancoras: {len(anc)} -> curva com {len(curve)}")

    ax = [ours[i][0] for i, _ in curve]
    ay = [ref[j][0] for _, j in curve]

    def predict(t):
        k = bisect_left(ax, t)
        if k == 0:
            return ay[0] + (t - ax[0])
        if k >= len(ax):
            return ay[-1] + (t - ax[-1])
        f = (t - ax[k-1]) / max(1e-6, ax[k] - ax[k-1])
        return ay[k-1] + f * (ay[k] - ay[k-1])

    # B ------------------------------------------------------------------
    # A posicao prevista entra na pontuacao, nao so como corte. Sem isso, uma
    # fala cuja traducao PT-PT se afastou do espanhol (texto fraco, mas no
    # sitio certo) perde para outra que so por acaso partilha letras.
    c = []
    for i, a in enumerate(ours):
        p = predict(a[0])
        for j, b in enumerate(ref):
            if abs(b[0] - p) > WINDOW:
                continue
            pos = 1 - abs(b[0] - p) / WINDOW
            dur = max(0.0, 1 - abs((b[1]-b[0]) - (a[1]-a[0])) / 1.5)
            s = 0.55 * tsim(a[2], b[2]) + 0.15 * dur + 0.30 * pos
            if s >= ACCEPT:
                c.append((s, i, j))
    c.sort(reverse=True)
    pair, uB, conf = {}, set(), {}
    for s, i, j in c:
        if i in pair or j in uB:
            continue
        pair[i] = j; uB.add(j); conf[i] = s
    print(f"B. disputa global na janela +-{WINDOW:.0f}s: {len(pair)}")

    # C ------------------------------------------------------------------
    n3 = 0
    for _ in range(3):
        for i, a in enumerate(ours):
            if i in pair:
                continue
            lo = max((k for k in pair if k < i), default=None)
            hi = min((k for k in pair if k > i), default=None)
            if lo is None or hi is None:
                continue
            t0, t1 = ref[pair[lo]][1], ref[pair[hi]][0]
            if t1 <= t0:
                continue
            da = a[1] - a[0]
            cand = [(abs((ref[j][1]-ref[j][0]) - da), j) for j in range(len(ref))
                    if j not in uB and ref[j][0] >= t0 - 0.05 and ref[j][1] <= t1 + 0.05]
            cand = [x for x in cand if x[0] <= DUR_TOL]
            if cand:
                j = min(cand)[1]
                pair[i] = j; uB.add(j); conf[i] = 0.60; n3 += 1
    print(f"C. encaixe entre vizinhas: +{n3}")

    # D: orfas ------------------------------------------------------------
    # So se remove quando duas legendas nossas caem no MESMO intervalo exato --
    # assinatura de uma orfa que se colou ali por posicao (foi o caso do
    # "...Pistol!", cujo par "Gomu Gomu no..." o corte novo eliminou). Uma
    # sobreposicao parcial e legitima: o cartao de titulo cobre duas falas.
    n4 = 0
    while True:
        order = sorted(pair, key=lambda i: ref[pair[i]][0])
        drop = None
        for x in range(1, len(order)):
            p, q = order[x-1], order[x]
            a, b = ref[pair[p]], ref[pair[q]]
            if abs(a[0]-b[0]) <= 0.1 and abs(a[1]-b[1]) <= 0.1:
                drop = p if conf[p] < conf[q] else q
                break
        if drop is None:
            break
        uB.discard(pair.pop(drop)); conf.pop(drop, None); n4 += 1
    print(f"D. orfas removidas (mesmo intervalo exato): -{n4}")
    print(f"\nnossas: {len(ours)}   emparelhadas: {len(pair)}   sem par: {len(ours)-len(pair)}")

    print("\nsem par -- desapareceram do corte novo:")
    for i in range(len(ours)):
        if i not in pair:
            print(f"  {fmt(ours[i][0])}  {ours[i][2][:62]!r}")

    if not dst:
        return
    out = sorted((ref[j][0], ref[j][1], ours[i][2]) for i, j in pair.items())
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        for n, (s, e, txt) in enumerate(out, 1):
            f.write(f"{n}\n{fmt(s)} --> {fmt(e)}\n{txt}\n\n")
    print(f"\nescrito: {dst}  ({len(out)} legendas, fim {fmt(out[-1][1])})")


if __name__ == '__main__':
    main()
