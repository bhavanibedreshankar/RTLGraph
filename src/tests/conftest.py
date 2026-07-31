from __future__ import annotations

import pytest

from graph.builder import build_graph
from parser.verilator_parser import parse_design
from retrieval.engine import RetrievalEngine

TREE_PATH = "/Users/bhavanibs/Documents/Claude/tpe_database/design.tree.json"
META_PATH = "/Users/bhavanibs/Documents/Claude/tpe_database/design.meta.json"


@pytest.fixture(scope="session")
def design():
    return parse_design(TREE_PATH, META_PATH)


@pytest.fixture(scope="session")
def graph(design):
    return build_graph(design)


@pytest.fixture(scope="session")
def engine(graph):
    return RetrievalEngine(graph)
