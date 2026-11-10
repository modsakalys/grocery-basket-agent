from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

MAX_PAGE_BYTES = 2_000_000
REQUEST_TIMEOUT_SECONDS = 12
ALLOWED_UNITS = {"g", "kg", "ml", "l", "unit", "units", "pc", "pcs", "piece", "pieces"}
STORE_URLS = {
    "Barbora": "https://barbora.lt",
    "Rimi": "https://www.rimi.lt/e-parduotuve",
    "IKI": "https://www.lastmile.lt/chain/IKI",
}
_STORE_NAMES = {name.casefold(): name for name in STORE_URLS}
_STORE_NAMES.update({"iki lastmile": "IKI", "lastmile/iki": "IKI", "rimi e-parduotuve": "Rimi"})


def _normalize_store(value: Any) -> str:
    raw = str(value).strip()
    canonical = _STORE_NAMES.get(raw.casefold())
    if not canonical:
        raise ValueError(f"Unsupported store '{raw}'. Use one of: {', '.join(STORE_URLS)}.")
    return canonical


@dataclass(frozen=True)
class CatalogProduct:
    store: str
    product: str
    price: float
    quantity: float
    unit: str
    url: str = ""
    notes: str = ""
    comparable_price: float = 0.0
    comparable_unit: str = "unit"


def _read_table(data: bytes, filename: str) -> pd.DataFrame:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "csv":
        return pd.read_csv(io.BytesIO(data))
    if suffix in {"xlsx", "xls"}:
        return pd.read_excel(io.BytesIO(data))
    raise ValueError("File must be CSV, XLSX, or XLS.")


def load_ingredient_sheet(data: bytes, filename: str) -> list[dict[str, Any]]:
    frame = _read_table(data, filename)
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    if "ingredient" not in frame.columns:
        raise ValueError("Ingredient sheet must include an 'ingredient' column.")
    for column in ("quantity", "unit", "notes"):
        if column not in frame.columns:
            frame[column] = None
    frame = frame.dropna(subset=["ingredient"])
    return [
        {
            "ingredient": str(row["ingredient"]).strip(),
            "quantity": None if pd.isna(row["quantity"]) else row["quantity"],
            "unit": None if pd.isna(row["unit"]) else str(row["unit"]).strip(),
            "notes": "" if pd.isna(row["notes"]) else str(row["notes"]).strip(),
        }
        for _, row in frame.iterrows()
        if str(row["ingredient"]).strip()
    ]


def _comparable(price: float, quantity: float, unit: str) -> tuple[float, str]:
    unit = unit.strip().lower()
    if unit not in ALLOWED_UNITS:
        raise ValueError(f"Unsupported catalog unit '{unit}'. Use g, kg, ml, l, or unit/pcs.")
    if unit in {"g", "kg"}:
        quantity_kg = quantity / 1000 if unit == "g" else quantity
        return price / quantity_kg, "kg"
    if unit in {"ml", "l"}:
        quantity_l = quantity / 1000 if unit == "ml" else quantity
        return price / quantity_l, "l"
    return price / quantity, "unit"


def load_product_catalog(data: bytes, filename: str) -> list[CatalogProduct]:
    frame = _read_table(data, filename)
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    required = {"store", "product", "price", "quantity", "unit"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Catalog is missing required columns: {', '.join(sorted(missing))}.")
    for column in ("url", "notes"):
        if column not in frame.columns:
            frame[column] = ""
    products = []
    for index, row in frame.iterrows():
        try:
            price, quantity = float(row["price"]), float(row["quantity"])
            if price < 0 or quantity <= 0:
                raise ValueError("price must be non-negative and quantity must be positive")
            unit = str(row["unit"]).strip().lower()
            normalized_price, normalized_unit = _comparable(price, quantity, unit)
            products.append(CatalogProduct(
                store=_normalize_store(row["store"]),
                product=str(row["product"]).strip(),
                price=price,
                quantity=quantity,
                unit=unit,
                url="" if pd.isna(row["url"]) else str(row["url"]).strip(),
                notes="" if pd.isna(row["notes"]) else str(row["notes"]).strip(),
                comparable_price=normalized_price,
                comparable_unit=normalized_unit,
            ))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid catalog row {index + 2}: {exc}") from exc
    return products


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[\w-]+", text.lower()) if len(token) > 1}


def _match_score(ingredient: str, product: str) -> float:
    left, right = _tokens(ingredient), _tokens(product)
    if not left or not right:
        return 0
    overlap = left & right
    return len(overlap) / len(left | right)


def compare_ingredients(ingredients: list[dict[str, Any]], products: list[CatalogProduct]) -> list[dict[str, Any]]:
    """Find the cheapest plausible product per ingredient in a comparable unit family.

    Product-name matching is conservative token overlap. Alternatives are restricted to the
    strongest comparable measure family so that €/kg is never compared directly with €/unit.
    Review suggestions because name similarity cannot guarantee culinary equivalence.
    """
    output = []
    for entry in ingredients:
        ingredient = str(entry.get("ingredient", "")).strip()
        candidates = [
            (score, product)
            for product in products
            if (score := _match_score(ingredient, product.product)) >= 0.25
        ]
        best = None
        alternatives: list[CatalogProduct] = []
        if candidates:
            # Select the measure family with the strongest name match. Compare all shops' items
            # within that family, ranking by normalized unit price, then match quality.
            family_quality: dict[str, float] = {}
            for score, product in candidates:
                family_quality[product.comparable_unit] = max(family_quality.get(product.comparable_unit, 0), score)
            selected_family = max(family_quality, key=family_quality.get)
            family = [(score, product) for score, product in candidates if product.comparable_unit == selected_family]
            alternatives = [product for _, product in sorted(family, key=lambda pair: (pair[1].comparable_price, -pair[0]))]
            best = alternatives[0]
        output.append({"ingredient": ingredient, "best_match": best, "alternatives": alternatives})
    return output


def _recipe_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_recipe_objects(item))
        return found
    if isinstance(value, dict):
        typ = value.get("@type", [])
        types = typ if isinstance(typ, list) else [typ]
        found = [value] if "Recipe" in types else []
        graph = value.get("@graph")
        if graph is not None:
            found.extend(_recipe_objects(graph))
        return found
    return []


def parse_recipe_url(url: str) -> tuple[str, list[str]]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a complete HTTP(S) recipe URL.")
    headers = {"User-Agent": "GroceryBasketAgent/0.1 (recipe ingredient extraction)"}
    with requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, stream=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            raise ValueError("The recipe URL did not return an HTML page.")
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            total += len(chunk)
            if total > MAX_PAGE_BYTES:
                raise ValueError("Recipe page is larger than the 2 MB limit.")
            chunks.append(chunk)
    soup = BeautifulSoup(b"".join(chunks), "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        for recipe in _recipe_objects(data):
            raw = recipe.get("recipeIngredient", [])
            if isinstance(raw, str):
                raw = [raw]
            ingredients = [str(item).strip() for item in raw if str(item).strip()]
            if ingredients:
                name = recipe.get("name", "")
                return (str(name), ingredients)
    raise ValueError("No readable Schema.org recipe ingredients found. Add ingredients to the Excel sheet instead.")
