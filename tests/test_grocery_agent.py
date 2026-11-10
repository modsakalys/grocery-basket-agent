from grocery_agent import CatalogProduct, _comparable, compare_ingredients, load_ingredient_sheet, load_product_catalog


def test_normalizes_price_per_kg_and_litre():
    assert _comparable(1.50, 500, "g") == (3.0, "kg")
    assert _comparable(2.0, 2, "l") == (1.0, "l")


def test_selects_lowest_comparable_price_for_matching_name():
    products = [
        CatalogProduct("Barbora", "Tomatoes", 2.5, 1, "kg", comparable_price=2.5, comparable_unit="kg"),
        CatalogProduct("Rimi", "Tomatoes", 1.0, 500, "g", comparable_price=2.0, comparable_unit="kg"),
    ]
    result = compare_ingredients([{"ingredient": "Tomatoes"}], products)
    assert result[0]["best_match"].store == "Rimi"


def test_loads_flat_csv_ingredient_list():
    rows = load_ingredient_sheet(b"ingredient,quantity,unit\nTomatoes,500,g\n", "list.csv")
    assert rows[0]["ingredient"] == "Tomatoes"
    assert rows[0]["quantity"] == 500


def test_catalog_reader_calculates_unit_price():
    products = load_product_catalog(
        b"store,product,price,quantity,unit\nRimi,Milk,1.5,1,l\n", "catalog.csv"
    )
    assert products[0].comparable_price == 1.5
    assert products[0].comparable_unit == "l"
