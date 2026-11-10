# Grocery Basket Agent

A local-first MVP for turning recipe links or a flat Excel ingredient list into a consolidated shopping list, comparing a product catalog from Barbora, Rimi, and IKI by normalized price per kg/litre/unit, and preparing a basket for your review.

**It does not place orders or access account-only content.** The app stops at a review/export step and never submits a checkout. Retailer websites can change or restrict automated access, so this version uses a user-provided product catalog (CSV/XLSX, such as a catalog or price list you are permitted to download). The comparison engine and retailer-adapter interface are ready to extend when permitted data sources are available.

## Run locally

Requires Python 3.10+.

```bash
git clone https://github.com/modsakalys/grocery-basket-agent.git
cd grocery-basket-agent
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL (usually http://localhost:8501). The app runs on your computer; recipe pages are fetched when you submit their URLs.

## Inputs

### Recipe links
Paste one URL per line. The parser looks for Schema.org `Recipe` structured data (`recipeIngredient`) in public page HTML. If a site does not provide readable structured data, add those ingredients using the Excel template instead.

### Excel ingredient sheet
Use the included [`examples/ingredients_template.csv`](examples/ingredients_template.csv) (Excel can open CSV), or upload `.xlsx`/`.xls` with these columns:

| ingredient | quantity | unit | notes |
|---|---:|---|---|
| tomatoes | 500 | g | fresh |

`ingredient` is required; quantity, unit, and notes are optional. Recipe ingredient text is retained as written, since interpreting culinary quantities and conversions can require human judgment.

### Product catalog
Upload a CSV or Excel file with columns `store`, `product`, `price`, `quantity`, and `unit`. Optional columns: `url`, `notes`. Store values can be Barbora, Rimi, or IKI. `quantity` is the package quantity and `unit` is `g`, `kg`, `ml`, `l`, or `unit`/`pcs`. The app calculates price per kg, litre, or package unit as appropriate and chooses the lowest comparable price among likely name matches.

The catalog is only as current as the file you provide. Check product size, availability, delivery charges, promotions, and substitutions on the retailer site before ordering.

## Safety and privacy

- Basket creation is a recommendation only. There is no checkout or payment automation.
- Recipe URLs are fetched with a timeout and response-size limit; only HTTP(S) URLs are accepted.
- Uploaded files are processed in memory by the local app and are not intentionally sent to a hosted service.
- Review ingredient interpretations and the final basket before shopping.

## Development

```bash
pytest
```

See `docs/architecture.md` for the data model and integration notes.
