from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

from grocery_agent import (
    CatalogProduct,
    compare_ingredients,
    load_ingredient_sheet,
    load_product_catalog,
    parse_recipe_url,
)

st.set_page_config(page_title="Grocery Basket Agent", page_icon="🛒", layout="wide")
st.title("🛒 Grocery Basket Agent")
st.caption("Turn recipes or an ingredient sheet into a price-compared basket. You stay in control; this app never places an order.")

with st.expander("How comparison works", expanded=False):
    st.markdown(
        "Upload a current product catalog from the stores you want to compare. "
        "The app matches product names to ingredients and compares normalized price per kg, litre, or unit. "
        "Recipe quantities are kept as written and may need your review. Availability, delivery fees, promotions, "
        "and substitutions must be checked with the retailer."
    )

st.header("1. Add your shopping needs")
recipe_text = st.text_area("Recipe URLs (one per line)", placeholder="https://example.com/recipe\nhttps://example.com/another-recipe")
ingredient_file = st.file_uploader("Or upload an ingredient Excel/CSV sheet", type=["xlsx", "xls", "csv"], key="ingredients")

st.header("2. Add a product catalog")
catalog_file = st.file_uploader("Upload CSV/Excel with store, product, price, quantity, unit columns", type=["xlsx", "xls", "csv"], key="catalog")

if st.button("Build comparison", type="primary"):
    ingredients: list[dict[str, Any]] = []
    errors: list[str] = []

    if ingredient_file is not None:
        try:
            ingredients.extend(load_ingredient_sheet(ingredient_file.getvalue(), ingredient_file.name))
        except Exception as exc:
            errors.append(f"Could not read ingredient sheet: {exc}")

    urls = [line.strip() for line in recipe_text.splitlines() if line.strip()]
    for url in urls:
        try:
            recipe_name, recipe_ingredients = parse_recipe_url(url)
            ingredients.extend({"ingredient": text, "quantity": None, "unit": None, "notes": f"From: {recipe_name or url}"} for text in recipe_ingredients)
        except Exception as exc:
            errors.append(f"Could not read {url}: {exc}")

    for error in errors:
        st.warning(error)

    if not ingredients:
        st.error("Add at least one recipe URL or upload an ingredient sheet.")
    elif catalog_file is None:
        st.error("Upload a product catalog to compare prices.")
        st.dataframe(pd.DataFrame(ingredients), use_container_width=True, hide_index=True)
    else:
        try:
            products = load_product_catalog(catalog_file.getvalue(), catalog_file.name)
            result = compare_ingredients(ingredients, products)
            st.session_state["comparison"] = result
            st.session_state["ingredients"] = ingredients
        except Exception as exc:
            st.error(f"Could not build comparison: {exc}")

if "comparison" in st.session_state:
    st.header("3. Review the suggested basket")
    results = st.session_state["comparison"]
    if not results:
        st.info("No ingredients to compare.")
    else:
        rows = []
        for item in results:
            product = item.get("best_match")
            rows.append({
                "Need": item["ingredient"],
                "Selected product": product.product if product else "No likely match — review manually",
                "Store": product.store if product else "—",
                "Package": f"{product.quantity:g} {product.unit}" if product else "—",
                "Price": f"€{product.price:.2f}" if product else "—",
                "Comparable price": f"€{product.comparable_price:.2f}/{product.comparable_unit}" if product else "—",
                "Product link": product.url if product and product.url else "",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, column_config={"Product link": st.column_config.LinkColumn()})

        matched = [item["best_match"] for item in results if item.get("best_match")]
        if matched:
            st.metric("Sum of selected package prices (not including delivery)", f"€{sum(product.price for product in matched):.2f}")
        st.warning("Please verify every match, package size, stock, price, and delivery fee at the retailer. This is not an order.")
        confirmed = st.checkbox("I have reviewed this suggested basket and it meets my needs")
        if confirmed:
            output = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
            st.download_button("Download reviewed basket CSV", data=output, file_name="reviewed_grocery_basket.csv", mime="text/csv")
            st.success("Basket review recorded for this session. No order has been placed.")

st.divider()
st.caption("Local-first prototype • No automatic checkout • Keep retailer price lists current")
