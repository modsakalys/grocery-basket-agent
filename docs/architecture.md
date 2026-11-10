# Architecture and integration notes

## Supported shops

The app's configured destinations are [Barbora](https://barbora.lt), [Rimi e-parduotuvė](https://www.rimi.lt/e-parduotuve), and [IKI via LastMile](https://www.lastmile.lt/chain/IKI).

## Current data flow

1. The Streamlit UI accepts any public recipe URL, manually typed ingredients, a flat ingredient sheet, and a product catalog.
2. `parse_recipe_url` fetches HTML and extracts `recipeIngredient` from Schema.org JSON-LD. It does not execute page JavaScript or log in.
3. Ingredient phrases are kept intact for review rather than being guessed into exact quantities.
4. `load_product_catalog` validates package price/size and computes comparable price per kg, litre, or package unit.
5. `merge_ingredient_entries` normalizes and merges duplicate items to reduce redundant entries.
6. `compare_ingredients` uses conservative token overlap on normalized names and can rank candidates by preferred brands before selecting the cheapest option in the family.
7. The app creates an editable basket proposal. Users can change cells, add rows, and remove rows before downloading the reviewed basket as CSV.
8. The UI also surfaces budget and delivery warnings to help users stay under their constraints.
9. No retailer cart or checkout is submitted. The CSV and product links are used to shop manually.

## Retailer data integration

The MVP does **not** retrieve live stock and prices from the configured shops. Comparison uses the catalog supplied by the user. Retailer data may require a selected delivery area or account and changes frequently. A future adapter should use an officially supported API, licensed feed, or user-authorized export; respect site terms and rate limits; and normalize its output into `CatalogProduct`. Do not add login/session scraping or checkout automation. Always identify price freshness and preserve a final human review.
