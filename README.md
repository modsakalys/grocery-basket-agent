# Grocery Basket Agent

A local-first app for adding any recipe URLs, manually entered ingredients, or a flat Excel ingredient list. It finds the cheapest comparable product in your uploaded catalog from Barbora, Rimi, and IKI and prepares an editable basket suggestion.

Supported shops:
- [Barbora](https://barbora.lt)
- [Rimi e-parduotuvė](https://www.rimi.lt/e-parduotuve)
- [IKI via LastMile](https://www.lastmile.lt/chain/IKI)

**Price data limitation:** the current version does not fetch live product listings or prices from the shops. Upload a current product catalog CSV/XLSX to compare. Prices are only as current as that catalog. It does not access account-only content, add items to retailer carts, or place orders.

## Run locally

Requires Python 3.10+.

```bash
git clone https://github.com/modsakalys/grocery-basket-agent.git
cd grocery-basket-agent
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL (usually http://localhost:8501).

## Use it

1. Add any number of recipe URLs (one per line), type ingredients manually (one per line), upload an ingredient sheet, or combine those inputs.
2. Upload a current product catalog from the supported shops.
3. Click **Find the cheapest prices**. The app suggests the lowest comparable price per kg, litre, or unit from matching catalog products.
4. Edit the basket: change product details, add your own items in a new row, or remove rows. Add the shop and price for items you enter manually.
5. Review and confirm the basket, then download it as CSV. Use product links to visit the shops and place any order yourself.

### Ingredient sheet

Use `examples/ingredients_template.csv` (Excel can open CSV), or upload `.xlsx`/`.xls` with columns:

| ingredient | quantity | unit | notes |
|---|---:|---|---|
| tomatoes | 500 | g | fresh |

`ingredient` is required; quantity, unit, and notes are optional. Recipe ingredient phrases remain intact for review rather than being guessed into exact quantities.

### Product catalog

Upload CSV or Excel with columns `store`, `product`, `price`, `quantity`, and `unit`. Optional columns: `url`, `notes`. Store values must be Barbora, Rimi, or IKI (also accepts `IKI LastMile` and `Rimi e-parduotuvė`). Units supported: `g`, `kg`, `ml`, `l`, and `unit`/`pcs`. The app calculates price per kg, litre, or item and compares only within a matching measure family.

Example catalog: `examples/product_catalog_example.csv`. Check package equivalence, stock, promotions, and delivery fees on the retailer site.

## Safety and privacy

- Basket creation is a recommendation only; no checkout or payment automation.
- Recipe URLs are fetched with a timeout and response-size limit; only HTTP(S) URLs are accepted.
- Uploaded files are processed in memory by the local app and are not intentionally sent to a hosted service.
- Review recipe extraction and product matches before shopping.

## Development

```bash
pytest
```

See `docs/architecture.md` for integration notes.
