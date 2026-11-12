# -*- coding: utf-8 -*-
"""
Паралельна побудова гістограми для PARCS-Python (Hummer12007/parcs-python).

Формат вхідного файлу (один рядок):
    N K SEED CHUNKS
    N      - кількість значень у масиві даних
    K      - кількість кошиків (bins) гістограми, значення лежать у [0, 256)
    SEED   - зерно генератора (щоб послідовний і паралельний варіанти
             обробляли однакові дані)
    CHUNKS - на скільки блоків поділено дані (має ділитися на воркерів;
             однакове значення для всіх запусків = однакові дані)

Вихідний файл: K рядків "номер_кошика кількість" + контрольна сума.
"""
from Pyro4 import expose
import random
import time

MAX_VALUE = 256  # значення як у 8-бітному зображенні: 0..255


class Solver:
    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name
        self.workers = workers

    # ---------- головний вузол ----------
    def solve(self):
        n, k, seed, chunks = self.read_input()
        w = len(self.workers)
        start = time.time()

        # 1. Розбиття: блоки 0..chunks-1 розподіляються між воркерами по колу
        blocks_per_worker = [[] for _ in range(w)]
        for c in range(chunks):
            blocks_per_worker[c % w].append(c)

        # 2. Map: кожен воркер рахує локальну гістограму своїх блоків
        #    (виклики асинхронні - повертаються future-об'єкти)
        mapped = []
        for i in range(w):
            mapped.append(self.workers[i].mymap(blocks_per_worker[i], n, k, seed, chunks))

        # 3. Reduce: сумування локальних гістограм
        hist = self.myreduce(mapped, k)

        elapsed = time.time() - start
        self.write_output(hist, n, w, elapsed)

    # ---------- воркер ----------
    @staticmethod
    @expose
    def mymap(block_ids, n, k, seed, chunks):
        local = [0] * k
        block_size = n // chunks
        for b in block_ids:
            size = block_size if b < chunks - 1 else n - block_size * (chunks - 1)
            rnd = random.Random(seed * 100003 + b)  # дані блоку b завжди однакові
            for _ in range(size):
                v = rnd.randint(0, MAX_VALUE - 1)
                local[v * k // MAX_VALUE] += 1
        return local

    @staticmethod
    @expose
    def myreduce(mapped, k):
        total = [0] * k
        for future in mapped:
            part = future.value  # чекаємо результат воркера
            for j in range(k):
                total[j] += part[j]
        return total

    # ---------- введення / виведення ----------
    def read_input(self):
        with open(self.input_file_name, 'r') as f:
            n, k, seed, chunks = [int(x) for x in f.readline().split()]
        return n, k, seed, chunks

    def write_output(self, hist, n, w, elapsed):
        with open(self.output_file_name, 'w') as f:
            for j, cnt in enumerate(hist):
                f.write('%d %d\n' % (j, cnt))
            f.write('# sum=%d (expected %d), workers=%d, time=%.3f s\n'
                    % (sum(hist), n, w, elapsed))
