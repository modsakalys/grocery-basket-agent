# Architecture and integration notes

## Supported shops

The app's configured destinations are [Barbora](https://barbora.lt), [Rimi e-parduotuvė](https://www.rimi.lt/e-parduotuve), and [IKI via LastMile](https://www.lastmile.lt/chain/IKI). Catalog store names are normalized to Barbora, Rimi, and IKI.

## Current data flow

1. The Streamlit UI accepts public recipe URLs, a flat ingredient sheet, and a product catalog.
2. `parse_recipe_url` fetches HTML and extracts `recipeIngredient` from Schema.org JSON-LD. It does not execute page JavaScript or log in.
3. `load_ingredient_sheet` keeps user-provided quantities and units as supplied. Recipe ingredient phrases remain intact for review rather than being guessed into exact quantities.
4. `load_product_catalog` validates package price/size and computes comparable price per kg, litre, or package unit.
5. `compare_ingredients` uses conservative token overlap to propose a likely match and lowest comparable price. The matcher is deliberately simple; treat results as suggestions, not authoritative product equivalence.
6. The app displays a basket proposal and can export a CSV only after the user checks the review box. No retailer cart or checkout is submitted.

## Retailer data integration

The MVP does **not** scrape or retrieve live stock and prices from the configured shops. The comparison uses a catalog supplied by the user. Retailer price, inventory, and delivery data can change and may require a selected delivery area or account. A future adapter should use an officially supported API, licensed feed, or user-authorized export; respect site terms and rate limits; and normalize its output into `CatalogProduct`. Do not add login/session scraping or checkout automation. Always identify price freshness and availability, and preserve a final human review before any order.

## Future improvements

- Authorized data adapters for Barbora, Rimi, and IKI/LastMile with transparent price timestamps.
- Lithuanian ingredient/product matching and synonyms.
- Explicit recipe yield and servings scaling.
- Duplicate ingredient consolidation with unit conversions and user confirmation.
- Product availability, delivery fees, and basket minimums in total cost optimization.
- Better user-facing match confidence and unmatched-item workflow.
