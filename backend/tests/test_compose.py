"""Compose must keep PostgreSQL bound to loopback only."""

import pathlib

import yaml

COMPOSE_PATH = pathlib.Path(__file__).resolve().parents[2] / "docker-compose.yml"


def test_postgres_port_is_bound_to_loopback_only():
    spec = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    ports = spec["services"]["db"]["ports"]

    assert len(ports) == 1
    assert ports[0].startswith("127.0.0.1:")
    assert ports[0].endswith(":5432")
