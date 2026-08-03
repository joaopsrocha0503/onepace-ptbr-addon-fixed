#!/usr/bin/env python3
"""Verifica se os nossos .srt continuam sincronizados com o corte atual do One Pace.

Descarrega as legendas oficiais de github.com/one-pace/one-pace-public-subtitles
e, para cada episodio, mede a distancia entre cada legenda nossa e o inicio de
referencia mais proximo.

    python scripts/check_sync_against_official.py 36_Wano "32 Wano" 54
    python scripts/check_sync_against_official.py 37_Egghead "33 Egghead" 20

Prefere-se a faixa ESPANHOLA: os nossos .ass sao um fork desse script (mesmos
estilos OP Normal2, Top, Enmedio2) e os tempos correspondem linha a linha. A
inglesa e um script independente -- serve de rede de seguranca quando nao ha
espanhol, mas produz alguns desvios de 2-10 s que nao sao dessincronizacao.

Como ler o resultado (calibrado no WA_4, o unico caso real encontrado ate hoje):

    ficheiro bom          mediana ~0.0 s, p90 < 1 s, nenhum acima de ~10 s
    dessincronizado       mediana 2.6 s, p90 214 s, dezenas acima de 10 s

Duas metricas que parecem obvias e NAO funcionam -- ja custaram dois
diagnosticos errados:

  * Contar coincidencias exactas. Diferencas de milissegundos entre codificacoes
    do mesmo script fazem episodios perfeitamente bons descer aos 11%.
  * Mediana ou percentil sobre TODAS as linhas da referencia. Estes .ass tem
    milhares de linhas de efeitos e tipografia (TOPPU, OPLetreros, Captions,
    Default) com duracoes de 0.04 s, amontoadas no inicio. Arrastam qualquer
    estatistica para valores sem sentido.
"""
import os
import re
import sys
import urllib.parse
import urllib.request
from bisect import bisect_left

RAW = "https://raw.githubusercontent.com/one-pace/one-pace-public-subtitles/main/main"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _t(x):
    h, m, s = x.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def fetch(arc, ep, cache):
    """Traz o .ass do episodio; espanhol se existir, senao ingles."""
    os.makedirs(cache, exist_ok=True)
    slug = arc.split(' ', 1)[1].lower()
    for lang in ('es', 'en'):
        dst = os.path.join(cache, f"{slug}_{ep}_{lang}.ass")
        if os.path.exists(dst):
            return dst, lang
        url = f"{RAW}/{urllib.parse.quote(arc)}/{ep}/{urllib.parse.quote(f'{slug} {ep} {lang}.ass')}"
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(dst, 'wb') as f:
                f.write(r.read())
            return dst, lang
        except Exception:
            if os.path.exists(dst):
                os.remove(dst)
    return None, None


def ref_starts(p):
    out = set()
    for l in open(p, encoding='utf-8', errors='replace'):
        if not l.startswith('Dialogue:'):
            continue
        f = l.split(',', 9)
        if re.sub(r'\{[^}]*\}', '', f[9]).replace('\\N', ' ').strip():
            out.add(_t(f[1]))
    return sorted(out)


def srt_starts(p):
    out = []
    for b in open(p, encoding='utf-8', errors='replace').read().replace('\r', '').split('\n\n'):
        L = b.strip().split('\n')
        if len(L) < 3:
            continue
        m = re.match(r'(\d+):(\d+):(\d+),(\d+) --> ', L[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        out.append(g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000)
    return sorted(out)


def nearest(t, xs):
    k = bisect_left(xs, t)
    c = []
    if k < len(xs):
        c.append(abs(xs[k] - t))
    if k:
        c.append(abs(xs[k - 1] - t))
    return min(c) if c else float('inf')


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    local_dir, arc, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
    cache = os.path.join(HERE, '.sync-cache', arc.replace(' ', '_'))
    base = os.path.join(HERE, 'subs', local_dir)

    # O prefixo dos ficheiros nao se deduz do nome da pasta (36_Wano -> WA_,
    # 37_Egghead -> EH_). Le-se do que la esta.
    if len(sys.argv) > 4:
        prefix = sys.argv[4]
    else:
        pref = {re.match(r'(.+)_\d+\.srt$', f).group(1)
                for f in os.listdir(base) if re.match(r'.+_\d+\.srt$', f)}
        if len(pref) != 1:
            print(f"nao consegui deduzir o prefixo em {base}: {sorted(pref)}")
            print("passa-o como 4o argumento")
            sys.exit(1)
        prefix = pref.pop()

    print(f"{'ep':>4} {'ln':>3} {'nossas':>7} {'mediana':>9} {'p90':>8} "
          f"{'max':>8} {'>10s':>6}  estado")
    bad = []
    for n in range(1, count + 1):
        ep = f"{n:02d}"
        ours = os.path.join(base, f"{prefix}_{n}.srt")
        if not os.path.exists(ours):
            print(f"{ep:>4}  {prefix}_{n}.srt nao existe")
            continue
        rp, lang = fetch(arc, ep, cache)
        if rp is None:
            print(f"{ep:>4}  sem referencia no repositorio")
            continue
        a, r = srt_starts(ours), ref_starts(rp)
        if not a or not r:
            print(f"{ep:>4}  vazio")
            continue
        d = sorted(nearest(t, r) for t in a)
        med, p90, mx = d[len(d)//2], d[int(0.9*(len(d)-1))], d[-1]
        over = sum(1 for x in d if x > 10)
        flag = 'DESSINCRONIZADO' if (med > 1.0 or over > 5) else 'ok'
        if flag != 'ok':
            bad.append(ep)
        print(f"{ep:>4} {lang:>3} {len(a):>7} {med:>8.2f}s {p90:>7.2f}s "
              f"{mx:>7.1f}s {over:>6}  {flag}")

    print()
    print(f"a corrigir: {' '.join(bad) if bad else 'nenhum'}")
    if bad:
        print("usar scripts/resync_to_official_cut.py com o .ass espanhol de cada um")


if __name__ == '__main__':
    main()
