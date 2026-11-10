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
ALLOWED_UNITS = {"g", "kg", "ml", "l", "unit", "units", "pc", "pcs", "piece", "pieces", "vnt"}
STORE_URLS = {
    "Barbora": "https://barbora.lt",
    "Rimi": "https://www.rimi.lt/e-parduotuve",
    "IKI": "https://www.lastmile.lt/chain/IKI",
}
_STORE_NAMES = {name.casefold(): name for name in STORE_URLS}
_STORE_NAMES.update({"iki lastmile": "IKI", "lastmile/iki": "IKI", "rimi e-parduotuve": "Rimi"})

_INGREDIENT_SYNONYMS = {
    "tomato": {"tomato", "tomatoes", "pomidoras", "pomidorai", "pomidoro", "pomidoru", "pomidorui"},
    "onion": {"onion", "onions", "svogunas", "svogunai", "svoguno", "svogunu", "svogunui"},
    "garlic": {"garlic", "garlics", "cesnakas", "cesnako", "cesnakinis", "cesnakai"},
    "milk": {"milk", "milkshake", "pienas", "pieno", "pienui", "pienas"},
    "butter": {"butter", "butterblock", "sviestas", "sviesto", "sviestui"},
    "bread": {"bread", "breads", "duona", "duonos", "duonai"},
    "egg": {"egg", "eggs", "kiaušinis", "kiaušiniai", "kiaušinio", "kiaušiniui"},
    "salmon": {"salmon", "salmonfish", "lašiša", "lašišos", "lašišai", "lašišą"},
    "pasta": {"pasta", "macaronai", "makaronai", "makaronų", "makaronui", "makaronas"},
    "pepper": {"pepper", "peppers", "pipirai", "pipiras", "pipiro", "paprika"},
    "potato": {"potato", "potatoes", "bulvė", "bulvės", "bulvėms", "bulvėmis", "bulve"},
    "carrot": {"carrot", "carrots", "morka", "morkos", "morkai", "morkos"},
    "cucumber": {"cucumber", "cucumbers", "agurkas", "agurkai", "agurko", "agurkui"},
    "chicken": {"chicken", "chickens", "vištiena", "vištienos", "vištienai"},
    "beef": {"beef", "veal", "juniena", "junienos", "junienai"},
    "apple": {"apple", "apples", "obuolys", "obuoliai", "obuolio"},
    "banana": {"banana", "bananas", "bananas", "bananai", "banano"},
    "lemon": {"lemon", "lemons", "citrina", "citrinos", "citrinai"},
    "parsley": {"parsley", "petražolės", "petražole", "petražolė"},
    "spinach": {"spinach", "spenat", "spenatas", "spenato", "shpinat"},
}


def _normalize_store(value: Any) -> str:
    raw = str(value).strip()
    canonical = _STORE_NAMES.get(raw.casefold())
    if not canonical:
        raise ValueError(f"Unsupported store '{raw}'. Use one of: {', '.join(STORE_URLS)}.")
    return canonical


def _normalize_lithuanian_text(value: str) -> str:
    text = str(value).lower().strip()
    mapping = {
        "ą": "a",
        "č": "c",
        "ę": "e",
        "ė": "e",
        "į": "i",
        "š": "s",
        "ų": "u",
        "ū": "u",
        "ž": "z",
    }
    for old, new in mapping.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_ingredient_name(value: str) -> str:
    base = _normalize_lithuanian_text(value)
    if not base:
        return ""
    for canonical, aliases in _INGREDIENT_SYNONYMS.items():
        variant_set = {_normalize_lithuanian_text(item) for item in aliases}
        variant_set.add(canonical)
        if base in variant_set:
            return canonical
    return base


def canonicalize_unit(value: Any) -> str:
    unit = str(value).strip().lower()
    aliases = {
        "kg": "kg",
        "kilogram": "kg",
        "kilogramas": "kg",
        "kilo": "kg",
        "g": "g",
        "gr": "g",
        "gram": "g",
        "gramas": "g",
        "grams": "g",
        "l": "l",
        "liter": "l",
        "litras": "l",
        "ml": "ml",
        "milliliter": "ml",
        "millilitras": "ml",
        "vnt": "unit",
        "pcs": "unit",
        "pc": "unit",
        "piece": "unit",
        "pieces": "unit",
        "unit": "unit",
        "units": "unit",
    }
    return aliases.get(unit, unit)


def merge_ingredient_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for entry in entries:
        ingredient = str(entry.get("ingredient", "")).strip()
        if not ingredient:
            continue
        key = normalize_ingredient_name(ingredient)
        if key not in merged:
            merged[key] = {
                "ingredient": ingredient,
                "quantity": entry.get("quantity"),
                "unit": canonicalize_unit(entry.get("unit")) if entry.get("unit") is not None else None,
                "notes": entry.get("notes", "") or "",
            }
            continue

        existing = merged[key]
        incoming_quantity = entry.get("quantity")
        existing_quantity = existing.get("quantity")
        if incoming_quantity is None or existing_quantity is None:
            if incoming_quantity is not None and existing_quantity is None:
                existing["quantity"] = incoming_quantity
            continue

        current_unit = canonicalize_unit(existing.get("unit")) if existing.get("unit") is not None else None
        incoming_unit = canonicalize_unit(entry.get("unit")) if entry.get("unit") is not None else None
        if current_unit == incoming_unit:
            existing["quantity"] = float(existing_quantity) + float(incoming_quantity)
            if not existing.get("notes") and entry.get("notes"):
                existing["notes"] = entry.get("notes")
        else:
            if current_unit in {"g", "kg"} and incoming_unit in {"g", "kg"}:
                current_g = float(existing_quantity) * 1000 if current_unit == "kg" else float(existing_quantity)
                incoming_g = float(incoming_quantity) * 1000 if incoming_unit == "kg" else float(incoming_quantity)
                existing["quantity"] = round((current_g + incoming_g) / 1000, 4)
                existing["unit"] = "kg"
            elif current_unit in {"ml", "l"} and incoming_unit in {"ml", "l"}:
                current_ml = float(existing_quantity) * 1000 if current_unit == "l" else float(existing_quantity)
                incoming_ml = float(incoming_quantity) * 1000 if incoming_unit == "l" else float(incoming_quantity)
                existing["quantity"] = round((current_ml + incoming_ml) / 1000, 4)
                existing["unit"] = "l"
            elif existing.get("unit") is None:
                existing["unit"] = incoming_unit
                existing["quantity"] = incoming_quantity
            if not existing.get("notes") and entry.get("notes"):
                existing["notes"] = entry.get("notes")

    cleaned = []
    for item in merged.values():
        if item.get("quantity") is not None and item.get("unit") is None:
            item["unit"] = "unit"
        item["ingredient"] = item["ingredient"].strip()
        cleaned.append(item)
    return cleaned


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
    values = [
        {
            "ingredient": str(row["ingredient"]).strip(),
            "quantity": None if pd.isna(row["quantity"]) else row["quantity"],
            "unit": None if pd.isna(row["unit"]) else str(row["unit"]).strip(),
            "notes": "" if pd.isna(row["notes"]) else str(row["notes"]).strip(),
        }
        for _, row in frame.iterrows()
        if str(row["ingredient"]).strip()
    ]
    return merge_ingredient_entries(values)


def _comparable(price: float, quantity: float, unit: str) -> tuple[float, str]:
    unit = canonicalize_unit(unit)
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
            unit = canonicalize_unit(row["unit"])
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


def _brand_match_score(product_name: str, preferred_brands: list[str]) -> int:
    if not preferred_brands:
        return 1
    product_norm = _normalize_lithuanian_text(product_name)
    for brand in preferred_brands:
        brand_norm = _normalize_lithuanian_text(brand)
        if not brand_norm:
            continue
        if brand_norm in product_norm or product_norm in brand_norm:
            return 2
        if brand_norm.split() and all(part in product_norm.split() for part in brand_norm.split()):
            return 2
    return 0


def _normalized_match_score(ingredient: str, product: str) -> float:
    left = normalize_ingredient_name(ingredient)
    right = normalize_ingredient_name(product)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.9
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    return len(overlap) / len(left_tokens | right_tokens)


def compare_ingredients(ingredients: list[dict[str, Any]], products: list[CatalogProduct], preferred_brands: list[str] | None = None) -> list[dict[str, Any]]:
    """Return the cheapest plausible product match for each requested ingredient.

    Matching is smarter than raw string equality: it normalizes Lithuanian names and aliases,
    then compares within the same comparable-unit family. If preferred brands are specified,
    they are used as a ranking preference, while still preserving the cheapest option logic.
    """
    output = []
    preferred_lower = [_normalize_lithuanian_text(item) for item in (preferred_brands or []) if _normalize_lithuanian_text(item)]
    for entry in ingredients:
        ingredient = str(entry.get("ingredient", "")).strip()
        if not ingredient:
            continue
        candidates: list[tuple[float, CatalogProduct]] = []
        for product in products:
            score = _normalized_match_score(ingredient, product.product)
            if score >= 0.25:
                candidates.append((score, product))
        best = None
        alternatives: list[CatalogProduct] = []
        if candidates:
            if preferred_lower:
                preferred_candidates = [
                    (score, product)
                    for score, product in candidates
                    if _brand_match_score(product.product, preferred_lower) > 0
                ]
                if preferred_candidates:
                    candidates = preferred_candidates
            best_family = max(candidates, key=lambda pair: pair[0])[1].comparable_unit
            family = [(score, product) for score, product in candidates if product.comparable_unit == best_family]
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
