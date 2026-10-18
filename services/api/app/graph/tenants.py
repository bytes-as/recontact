"""Tenant graph names. A lab graph and a health-system graph never read each other."""

from __future__ import annotations


def lab_graph(tenant: str) -> str:
    if tenant == "demo":
        return "lab_demo"
    return f"{tenant}_lab"


def hs_graph(tenant: str) -> str:
    if tenant == "demo":
        return "hs_demo"
    return f"{tenant}_hs"
