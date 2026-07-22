#!/usr/bin/env python3
"""Test mermaid-py API."""
import sys
import traceback

try:
    import mermaid
    print(f"mermaid version: {mermaid.__version__}")
    print(f"mermaid file: {mermaid.__file__}")

    from mermaid import Mermaid, Graph
    from mermaid.graph import Node, Edge
    print("Imports OK")

    # Try simplest possible graph
    nodes = [Node("A", "Hello"), Node("B", "World")]
    edges = [Edge("A", "B")]
    g = Graph("test", nodes + edges)
    print(f"Graph created: {type(g)}")

    m = Mermaid(g)
    print(f"Mermaid created: {type(m)}")

    # Try to get string representation
    result = str(m)
    print(f"String result:\n{result}")

except Exception as e:
    traceback.print_exc()
    sys.exit(1)
