from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from grocery_agent import (
    STORE_URLS,
    compare_ingredients,
    load_ingredient_sheet,
    load_product_catalog,
    merge_ingredient_entries,
    optimize_basket,
    parse_recipe_url,
)

st.set_page_config(page_title="Grocery Basket Agent", page_icon="🛒", layout="wide")
st.title("🛒 Grocery Basket Agent")
st.caption("Choose any recipe links and/or enter ingredients. The app identifies the cheapest comparable catalog option and prepares an editable basket suggestion; it never places an order.")
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

st.header("2. Add shopping preferences")
preferred_brands = st.text_area("Preferred brands (optional, one per line)", placeholder="Rimi\nKraft\nApetit")
max_budget = st.number_input("Maximum basket budget in € (optional)", min_value=0.0, step=1.0, value=0.0)
max_delivery = st.number_input("Maximum delivery fee in € (optional)", min_value=0.0, step=0.5, value=0.0)

st.header("3. Compare prices from your shops")
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

    ingredients = merge_ingredient_entries(ingredients)
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
            preferred = [line.strip() for line in preferred_brands.splitlines() if line.strip()]
            base_result = compare_ingredients(ingredients, products, preferred_brands=preferred)
            optimized = optimize_basket(base_result, budget_limit=float(max_budget) if max_budget > 0 else None, delivery_limit=float(max_delivery) if max_delivery > 0 else None)
            st.session_state["comparison"] = base_result
            st.session_state["optimized_selection"] = optimized
            st.session_state["basket_draft"] = pd.DataFrame([
                {
                    "Your ingredient": item["ingredient"],
                    "Product": item["selected"].product if item.get("selected") else "",
                    "Shop": item["selected"].store if item.get("selected") else "",
                    "Pack size": f"{item['selected'].quantity:g} {item['selected'].unit}" if item.get("selected") else "",
                    "Pack price (€)": float(item["selected"].price) if item.get("selected") else None,
                    "Price per kg/litre/unit": f"€{item['selected'].comparable_price:.2f}/{item['selected'].comparable_unit}" if item.get("selected") else "",
                    "Product/shop link": (item["selected"].url or STORE_URLS.get(item["selected"].store, "")) if item.get("selected") else "",
                }
                for item in optimized
            ], columns=["Your ingredient", "Product", "Shop", "Pack size", "Pack price (€)", "Price per kg/litre/unit", "Product/shop link"])
            st.session_state["ingredient_count"] = len(ingredients)
            st.session_state["budget_limit"] = float(max_budget)
            st.session_state["delivery_limit"] = float(max_delivery)
        except Exception as exc:
            st.error(f"Could not build comparison: {exc}")

if "basket_draft" in st.session_state:
    st.header("4. Edit your basket")
    st.write("Change any cell, add rows using the blank row at the bottom, or remove rows with the row controls. For an item without a catalog match, add its product, shop, and price yourself.")
    edited_basket = st.data_editor(
        st.session_state["basket_draft"],
        key="editable_basket",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Your ingredient": st.column_config.TextColumn("Your ingredient"),
            "Product": st.column_config.TextColumn("Product"),
            "Shop": st.column_config.TextColumn("Shop"),
            "Pack size": st.column_config.TextColumn("Pack size"),
            "Pack price (€)": st.column_config.NumberColumn("Pack price (€)", min_value=0.0, step=0.01, format="€%.2f"),
            "Price per kg/litre/unit": st.column_config.TextColumn("Price per kg/litre/unit"),
            "Product/shop link": st.column_config.LinkColumn("Product/shop link"),
        },
    )
    st.session_state["basket_draft"] = edited_basket

    export_basket = edited_basket.copy()
    export_basket["Pack price (€)"] = pd.to_numeric(export_basket["Pack price (€)"], errors="coerce")
    has_content = export_basket["Your ingredient"].fillna("").astype(str).str.strip().ne("") | export_basket["Product"].fillna("").astype(str).str.strip().ne("")
    export_basket = export_basket.loc[has_content].copy()
    st.header("5. Review and export")
    total = export_basket["Pack price (€)"].sum(min_count=1)
    if pd.notna(total):
        st.metric("Total of entered pack prices (excludes delivery)", f"€{total:.2f}")
        budget_limit = float(st.session_state.get("budget_limit", 0.0))
        delivery_limit = float(st.session_state.get("delivery_limit", 0.0))
        if budget_limit > 0:
            if total > budget_limit:
                st.warning(f"Selected basket is above your budget by €{total - budget_limit:.2f}. Consider removing items or choosing cheaper alternatives.")
            else:
                st.success(f"Selected basket is within your budget. You have €{budget_limit - total:.2f} remaining before delivery.")
        if delivery_limit > 0 and budget_limit > 0:
            if total + delivery_limit > budget_limit:
                st.warning(f"Delivery fee plus basket total exceeds your budget by €{total + delivery_limit - budget_limit:.2f}.")
    st.warning("Prices come from the uploaded catalog or your edits—not live shop data. Verify products, availability, and delivery costs. This app does not add items to a retailer cart or place an order.")
    confirmed = st.checkbox("I have reviewed this basket and it meets my needs")
    if confirmed:
        output = export_basket.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download my reviewed basket CSV", data=output, file_name="reviewed_grocery_basket.csv", mime="text/csv")
        st.success("Basket review recorded for this session. Use the product links to shop and place any order yourself.")

st.divider()
st.caption("Local-first prototype • Any recipe links or ingredients • Editable basket • Budget-aware optimized recommendations • No automatic checkout")
