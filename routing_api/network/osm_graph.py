"""
OSM street-network graph: build from XML or load from pickle cache.
"""
from __future__ import annotations

import os
import pickle
import time

import osmnx as ox

from routing_api.config import settings


def load_osm_graph(*, force_rebuild: bool | None = None):
    """
    Load the OSM walking network graph.

    Returns
    -------
    networkx.MultiDiGraph
        The OSM graph with edge ``length`` attributes (meters).
    """
    force = force_rebuild if force_rebuild is not None else settings.force_rebuild_graph
    xml_path = str(settings.resolve(settings.osm_xml_path))
    cache_path = str(settings.resolve(settings.graph_cache_path))

    start_t = time.time()

    if (not force) and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            g = pickle.load(f)
        source = "pickle cache"
    else:
        g = ox.graph_from_xml(xml_path, bidirectional=True, simplify=True)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(g, f, protocol=pickle.HIGHEST_PROTOCOL)
        source = "OSM XML build"

    elapsed = time.time() - start_t
    print(f"[osm_graph] Loaded from: {source}")
    print(f"[osm_graph] Nodes: {g.number_of_nodes():,} | Edges: {g.number_of_edges():,}")
    print(f"[osm_graph] Load time: {elapsed:.2f}s")
    return g
