from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from grocery_agent import (
    STORE_URLS,
    compare_ingredients,
    load_ingredient_sheet,
    load_product_catalog,
    parse_recipe_url,
)

st.set_page_config(page_title="Grocery Basket Agent", page_icon="🛒", layout="wide")
st.title("🛒 Grocery Basket Agent")
st.caption("Choose any recipe links and/or enter ingredients. The app identifies the cheapest comparable catalog option and prepares a basket suggestion; it never places an order.")
st.markdown("**Supported shops:** " + " · ".join(f"[{store}]({url})" for store, url in STORE_URLS.items()))

with st.expander("Price and data details", expanded=False):
    st.markdown(
        "The app compares a product catalog that you upload; it does not currently fetch live prices from the shops. "
        "Use a current catalog from Barbora, Rimi, and/or IKI. Prices are compared per kg, litre, or package unit, "
        "and only products in the same measure family are compared. Check product equivalence, stock, price freshness, "
        "delivery fees, promotions, and substitutions on the retailer site."
    )

st.header("1. Add anything you want to buy")
recipe_text = st.text_area("Recipe URLs (one per line; add as many as you like)", placeholder="https://example.com/recipe\nhttps://example.com/another-recipe")
ingredient_file = st.file_uploader("Or upload an ingredient Excel/CSV sheet", type=["xlsx", "xls", "csv"], key="ingredients")
manual_ingredients = st.text_area("Or type ingredients (one per line)", placeholder="tomatoes\npasta\nsalmon")

st.header("2. Compare prices from your shops")
st.caption("Upload a current CSV/Excel product list. Required columns: store, product, price, quantity, unit. Stores: Barbora, Rimi, IKI.")
catalog_file = st.file_uploader("Product catalog (CSV/XLSX)", type=["xlsx", "xls", "csv"], key="catalog")

if st.button("Find the cheapest prices", type="primary"):
    ingredients: list[dict[str, Any]] = []
    errors: list[str] = []

    if ingredient_file is not None:
        try:
            ingredients.extend(load_ingredient_sheet(ingredient_file.getvalue(), ingredient_file.name))
        except Exception as exc:
            errors.append(f"Could not read ingredient sheet: {exc}")

    ingredients.extend(
        {"ingredient": line.strip(), "quantity": None, "unit": None, "notes": "Manually entered"}
        for line in manual_ingredients.splitlines()
        if line.strip()
    )

    urls = [line.strip() for line in recipe_text.splitlines() if line.strip()]
    for url in urls:
        try:
            recipe_name, recipe_ingredients = parse_recipe_url(url)
            ingredients.extend(
                {"ingredient": text, "quantity": None, "unit": None, "notes": f"From: {recipe_name or url}"}
                for text in recipe_ingredients
            )
        except Exception as exc:
            errors.append(f"Could not read {url}: {exc}")

    for error in errors:
        st.warning(error)

    if not ingredients:
        st.error("Add at least one recipe URL, ingredient, or ingredient sheet.")
    elif catalog_file is None:
        st.error("Upload a product catalog to compare prices. Live shop prices are not fetched by this prototype.")
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
    st.header("3. Cheapest matches — review before shopping")
    results = st.session_state["comparison"]
    if not results:
        st.info("No ingredients to compare.")
    else:
        rows = []
        for item in results:
            product = item.get("best_match")
            rows.append({
                "Your ingredient": item["ingredient"],
                "Cheapest matching product": product.product if product else "No likely match — review manually",
                "Shop": product.store if product else "—",
                "Pack size": f"{product.quantity:g} {product.unit}" if product else "—",
                "Pack price": f"€{product.price:.2f}" if product else "—",
                "Price per kg/litre/unit": f"€{product.comparable_price:.2f}/{product.comparable_unit}" if product else "—",
                "Product/shop link": (product.url or STORE_URLS.get(product.store, "")) if product else "",
            })
            alternatives = item.get("alternatives", [])
            if alternatives:
                with st.expander(f"Compare {item['ingredient']} across shops ({len(alternatives)} candidate product(s))"):
                    alternative_rows = [{
                        "Shop": candidate.store,
                        "Product": candidate.product,
                        "Pack": f"{candidate.quantity:g} {candidate.unit}",
                        "Pack price": f"€{candidate.price:.2f}",
                        "Price per kg/litre/unit": f"€{candidate.comparable_price:.2f}/{candidate.comparable_unit}",
                        "Link": candidate.url or STORE_URLS.get(candidate.store, ""),
                    } for candidate in alternatives]
                    st.dataframe(pd.DataFrame(alternative_rows), use_container_width=True, hide_index=True, column_config={"Link": st.column_config.LinkColumn()})

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, column_config={"Product/shop link": st.column_config.LinkColumn()})
        matched = [item["best_match"] for item in results if item.get("best_match")]
        if matched:
            st.metric("Total selected pack prices (excludes delivery)", f"€{sum(product.price for product in matched):.2f}")
        st.warning("This is based only on the uploaded catalog, not live shop prices. Verify matches, availability, and delivery costs. No order has been placed.")
        confirmed = st.checkbox("I have reviewed this basket and it meets my needs")
        if confirmed:
            output = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
            st.download_button("Download reviewed basket CSV", data=output, file_name="reviewed_grocery_basket.csv", mime="text/csv")
            st.success("Review recorded for this session. No order has been placed.")

st.divider()
st.caption("Local-first prototype • Any recipe links or ingredients • Cheapest comparable catalog prices • No automatic checkout")
