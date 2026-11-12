# -*- coding: utf-8 -*-
"""
Послідовна версія (еталон для перевірки й порівняння часу).
Запуск: python sequential.py input.txt output_seq.txt
Генерує ті самі дані, що й solver.py (той самий SEED і CHUNKS).
"""
import random
import sys
import time

MAX_VALUE = 256


def main(inp, out):
    with open(inp) as f:
        n, k, seed, chunks = [int(x) for x in f.readline().split()]
    start = time.time()
    hist = [0] * k
    block_size = n // chunks
    for b in range(chunks):
        size = block_size if b < chunks - 1 else n - block_size * (chunks - 1)
        rnd = random.Random(seed * 100003 + b)
        for _ in range(size):
            v = rnd.randint(0, MAX_VALUE - 1)
            hist[v * k // MAX_VALUE] += 1
    elapsed = time.time() - start
    with open(out, 'w') as f:
        for j, cnt in enumerate(hist):
            f.write('%d %d\n' % (j, cnt))
        f.write('# sum=%d (expected %d), workers=1 (sequential), time=%.3f s\n'
                % (sum(hist), n, elapsed))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
