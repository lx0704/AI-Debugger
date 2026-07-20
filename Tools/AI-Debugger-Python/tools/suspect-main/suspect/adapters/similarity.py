"""
Textual Similarity Adapter
--------------------------

High-level workflow:
1) Parse the JUnit XML (.suspect.pytest.xml) to find failed test cases
   and extract their source code from the failure traceback text.

2) Combine all failed test sources into a single query string.

3) Build a MethodIndex of all source methods in the project
   (same approach as CoverageSBFLAdapter — skip test files).

4) Extract source text for each method via AST.

5) Compute BM25 and TF-IDF cosine similarity between the query
   and each method's source text.

6) Return scores as dict[method_key, {"bm25": float, "tfidf": float}]
"""

import os
import re
import math
import pathlib
import xml.etree.ElementTree as ET
import ast as pyast

from .base import MetricAdapter
from ..mapping import MethodIndex
from ..plugins import register_adapter

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class SimilarityAdapter(MetricAdapter):
    name = "similarity"

    def collect(self, ctx) -> dict[str, dict[str, float]]:
        project  = pathlib.Path(ctx["project_root"]).resolve()
        print(project)
        xml_path = project / ".suspect.pytest.xml"

        # ── 1. Parse XML → extract failed test source texts ───────────
        print("Parse XML")
        failed_sources = _extract_failed_test_sources(str(xml_path))

        if not failed_sources:
            # no failed tests found → all scores are 0
            return {}
        print("Done xml parsing for similarity")

        # ── 2. Combine into one query ──────────────────────────────────
        query_text = "\n\n".join(failed_sources)
    
        # ── 3. Build method index (skip test files) ────────────────────
        method_sources: dict[str, str] = {}  # method_key → source text
        skip_dirs = {
            ".venv", "venv", "env", ".git",
            "__pycache__", "build", "dist"
        }

        for root, dirs, files in os.walk(str(project)):
            dirs[:] = [
                d for d in dirs
                if d not in skip_dirs and not d.startswith(".")
            ]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                abs_path = pathlib.Path(root) / fn
                rel      = abs_path.relative_to(project).as_posix()

                if _is_test_file(rel):
                    continue

                try:
                    src = abs_path.read_text(encoding="utf-8")
                except Exception:
                    continue

                # extract every method from this file
                methods = _extract_methods_from_source(rel, src)
                method_sources.update(methods)

        if not method_sources:
            return {}
        print("Done Build method index for similarity")

        # ── 4. Compute similarity scores ───────────────────────────────
        method_keys  = list(method_sources.keys())
        method_texts = [method_sources[k] for k in method_keys]

        bm25_scores  = _bm25_scores(query_text, method_texts)
        tfidf_scores = _tfidf_scores(query_text, method_texts)

        # ── 5. Build output dict ───────────────────────────────────────
        out: dict[str, dict[str, float]] = {}
        for i, key in enumerate(method_keys):
            out[key] = {
                # "similarity_bm25":  round(float(bm25_scores[i]),  6),
                "similarity_tfidf": round(float(tfidf_scores[i]), 6),
            }

        print("Done Build output dict for similarity")

        return out


# Register adapter
try:
    register_adapter("similarity", SimilarityAdapter)
except Exception:
    pass


# ── XML parsing ────────────────────────────────────────────────────────────

def _extract_failed_test_sources(xml_path: str) -> list[str]:
    """
    Parse JUnit XML and extract source code snippets
    from all failed testcase failure texts.
    """
    try:
        tree = ET.parse(xml_path)
    except Exception:
        return []

    root    = tree.getroot()
    sources = []

    for testcase in root.iter("testcase"):
        failure = testcase.find("failure")
        if failure is None:
            continue                         # test passed — skip

        failure_text = failure.text or ""
        source       = _extract_test_source(failure_text)
        if source.strip():
            sources.append(source)

    return sources


def _extract_test_source(failure_text: str) -> str:
    """
    Extract only the test function source from a failure traceback.

    The failure text looks like:
        def test_foo():
            x = something()
        >   assert x == 1
        _ _ _ _ _ _ _ _ _       ← separator
        src/module.py:10: ...   ← internal trace (stop here)

    We keep everything before the first '_ _ _' separator line
    or before an internal file path line.
    """
    lines      = failure_text.split("\n")
    test_lines = []

    for line in lines:
        stripped = line.strip()
        # stop at separator line: '_ _ _ _ _'
        if re.match(r'^_[\s_]+$', stripped):
            break
        # stop at internal traceback file lines: 'src/file.py:10: in func'
        if re.match(r'^[a-zA-Z0-9_./-]+\.py:\d+:', stripped):
            break
        test_lines.append(line)

    return "\n".join(test_lines).strip()


# ── Method source extraction ───────────────────────────────────────────────

def _extract_methods_from_source(file_key: str,
                                  source: str) -> dict[str, str]:
    """
    Parse a Python source file and return:
        { "path/to/file.py:ClassName.method_name": source_text, ... }

    Matches the method key format used by MethodIndex.
    """
    try:
        tree = pyast.parse(source)
    except SyntaxError:
        return {}

    methods = {}

    for node in tree.body:
        # Top-level function
        if isinstance(node, pyast.FunctionDef):
            src = pyast.get_source_segment(source, node)
            if src:
                methods[f"{file_key}:{node.name}"] = src

        # Class methods
        elif isinstance(node, pyast.ClassDef):
            for item in node.body:
                if isinstance(item, pyast.FunctionDef):
                    src = pyast.get_source_segment(source, item)
                    if src:
                        methods[f"{file_key}:{node.name}.{item.name}"] = src

    return methods


# ── Tokenizer ──────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """
    Extract tokens from source text.
    - Keeps alphanumeric identifiers only
    - Splits camelCase: computeScore → ['computescore', 'compute', 'score']
    - Splits snake_case naturally via re.findall
    """
    raw    = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
    tokens = []

    for word in raw:
        # camel case split
        parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', word).split()
        tokens.append(word.lower())
        for p in parts:
            if p.lower() != word.lower():
                tokens.append(p.lower())

    return tokens


# ── BM25 ───────────────────────────────────────────────────────────────────

def _bm25_scores(query: str, documents: list[str],
                 k1: float = 1.0, b: float = 0.3) -> list[float]:
    """
    BM25 similarity between query and each document.
    k1=1.0, b=0.3 matches DeepFL paper configuration.
    """
    if not documents:
        return []

    tokenized_docs  = [_tokenize(d) for d in documents]
    tokenized_query = _tokenize(query)

    bm25   = BM25Okapi(tokenized_docs, k1=k1, b=b)
    scores = bm25.get_scores(tokenized_query)

    # normalize to [0, 1]
    max_s = scores.max()
    if max_s > 0:
        scores = scores / max_s

    return scores.tolist()


# ── TF-IDF cosine ──────────────────────────────────────────────────────────

def _tfidf_scores(query: str, documents: list[str]) -> list[float]:
    """
    TF-IDF cosine similarity between query and each document.
    """
    if not documents:
        return []

    corpus     = [query] + documents
    vectorizer = TfidfVectorizer(
        tokenizer=_tokenize,
        lowercase=False,
        token_pattern=None   # required when custom tokenizer is used
    )

    matrix = vectorizer.fit_transform(corpus)

    # query is row 0, documents are rows 1..N
    scores = cosine_similarity(matrix[0], matrix[1:])[0]

    return scores.tolist()


# ── Helpers ────────────────────────────────────────────────────────────────

def _is_test_file(path: str) -> bool:
    """Return True if path looks like a test module."""
    p    = str(path).replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    return "/tests/" in p or p.startswith("tests/") or name.startswith("test_") or p.endswith("_test.py")