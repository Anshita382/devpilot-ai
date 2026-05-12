"""BM25 sparse scorer (Okapi BM25). Pure Python, no dependencies.

Used as the lexical half of hybrid retrieval. Tokeniser is code-aware: it splits
identifiers on camelCase / snake_case so a query like "redis cache" matches a
``redisCache`` symbol.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for raw in _TOKEN.findall(text.lower()):
        out.append(raw)
        parts = re.findall(r"[a-z]+|[0-9]+", raw)
        if len(parts) > 1:
            out.extend(parts)
    return out


class BM25:
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(d) for d in corpus]
        self.n = len(self.docs)
        self.doc_len = [len(d) for d in self.docs]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.freqs = [Counter(d) for d in self.docs]
        df: Counter = Counter()
        for d in self.docs:
            for term in set(d):
                df[term] += 1
        self.idf = {
            term: math.log(1 + (self.n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = [0.0] * self.n
        if self.avgdl == 0:
            return out
        for term in q:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i in range(self.n):
                f = self.freqs[i].get(term, 0)
                if f == 0:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                out[i] += idf * (f * (self.k1 + 1)) / denom
        return out
