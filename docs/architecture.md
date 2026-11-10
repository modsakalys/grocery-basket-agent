# Architecture and integration notes

## Data flow

1. The Streamlit UI accepts public recipe URLs, a flat ingredient sheet, and a product catalog.
2. `parse_recipe_url` fetches HTML and extracts `recipeIngredient` from Schema.org JSON-LD. It does not execute page JavaScript or log in.
3. `load_ingredient_sheet` keeps user-provided quantities and units as supplied. Recipe ingredient phrases remain intact for review rather than being guessed into exact quantities.
4. `load_product_catalog` validates package price/size and computes comparable price per kg, litre, or package unit.
5. `compare_ingredients` uses conservative token overlap to propose a likely match and lowest comparable price. The matcher is deliberately simple; treat results as suggestions, not authoritative product equivalence.
6. The app displays a basket proposal and can export a CSV only after the user checks the review box. No retailer cart or checkout is submitted.

## Retailer data integration

Retailer price, inventory, and delivery data are not bundled because site structures and access rules can change. A future adapter should use an officially supported API, licensed feed, or user-authorized export; respect site terms and rate limits; and normalize its output into `CatalogProduct`. Do not add login/session scraping or checkout automation. Always identify price freshness and availability, and preserve a final human review before any order.

## Future improvements

- Locale-aware Lithuanian ingredient/product matching and synonyms.
- Explicit recipe yield and servings scaling.
- Duplicate ingredient consolidation with unit conversions and user confirmation.
- Store-specific import adapters and product availability timestamps.
- Basket optimization that accounts for separate delivery fees and minimum basket totals.
- Better user-facing match confidence and unmatched-item workflow.
