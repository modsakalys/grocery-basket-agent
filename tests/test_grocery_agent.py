from grocery_agent import CatalogProduct, STORE_URLS, _comparable, compare_ingredients, load_ingredient_sheet, load_product_catalog


def test_normalizes_price_per_kg_and_litre():
    assert _comparable(1.50, 500, "g") == (3.0, "kg")
    assert _comparable(2.0, 2, "l") == (1.0, "l")


def test_finds_cheapest_matching_product_across_stores():
    products = [
        CatalogProduct("Barbora", "Tomatoes", 2.5, 1, "kg", comparable_price=2.5, comparable_unit="kg"),
        CatalogProduct("Rimi", "Tomatoes", 1.0, 500, "g", comparable_price=2.0, comparable_unit="kg"),
        CatalogProduct("IKI", "Tomatoes", 1.2, 500, "g", comparable_price=2.4, comparable_unit="kg"),
    ]
    result = compare_ingredients([{"ingredient": "Tomatoes"}], products)[0]
    assert result["best_match"].store == "Rimi"
    assert [product.store for product in result["alternatives"]] == ["Rimi", "IKI", "Barbora"]


def test_loads_flat_csv_ingredient_list():
    rows = load_ingredient_sheet(b"ingredient,quantity,unit\nTomatoes,500,g\n", "list.csv")
    assert rows[0]["ingredient"] == "Tomatoes"
    assert rows[0]["quantity"] == 500


def test_catalog_reader_calculates_unit_price_and_canonicalizes_store():
    products = load_product_catalog(
        b"store,product,price,quantity,unit\nIKI LastMile,Milk,1.5,1,l\n", "catalog.csv"
    )
    assert products[0].store == "IKI"
    assert products[0].comparable_price == 1.5
    assert products[0].comparable_unit == "l"
    assert STORE_URLS[products[0].store] == "https://www.lastmile.lt/chain/IKI"
