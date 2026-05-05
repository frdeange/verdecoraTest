from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.models.store import Store
from src.shared.stores.loader import load_stores

pytestmark = pytest.mark.unit

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "stores" / "verdecora-stores.json"
EXPECTED_STORE_NAMES = {
    "Chamberí Urban",
    "Ríos Rosas Urban",
    "López de Hoyos Urban",
    "Floristería Santa Engracia 41",
    "Floristería Núñez de Balboa 58",
    "Calle Alcalá 108",
    "Floristería Castellana 192",
    "Aravaca",
    "Parquesur",
    "Floristería La Moraleja",
    "Los Peñotes",
    "Floristería Alcobendas",
    "Arroyo Culebro M-50",
    "Majadahonda",
    "Torrelodones",
    "Floristería Santo Domingo",
    "Alcalá de Henares",
    "Paterna",
    "Valencia Urban",
    "Avenida del Puerto",
    "Denia",
    "Zaragoza",
    "Málaga",
    "Vigo",
    "Sant Quirze",
    "Diagonal 534",
    "Alicante",
}


def test_store_catalog_json_loads_correctly() -> None:
    raw_payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    stores = load_stores()

    assert len(raw_payload) == 27
    assert len(stores) == len(raw_payload)
    assert {store.name for store in stores} == EXPECTED_STORE_NAMES
    assert all(isinstance(store, Store) for store in stores)


def test_store_catalog_has_required_fields() -> None:
    for store in load_stores():
        assert store.id
        assert store.name
        assert store.region
        assert store.address
        assert store.city
        assert store.postal_code
        assert store.bc_location_code
        assert isinstance(store.aliases, list)


def test_store_catalog_has_no_duplicate_ids() -> None:
    ids = [store.id for store in load_stores()]

    assert len(ids) == len(set(ids))


def test_store_catalog_postal_codes_match_spanish_format() -> None:
    pattern = re.compile(r"^\d{5}$")

    for store in load_stores():
        assert pattern.fullmatch(store.postal_code), store.postal_code
