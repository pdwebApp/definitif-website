# AI Coding Agent Instructions for Definitif Investments Website

## Project Overview
A Flask-based investment calculator web application that computes portfolio growth projections with systematic investment plans (SIP), visualization, and PDF export capabilities.

## Architecture

### Backend Stack
- **Framework:** Flask (serves routes, renders Jinja2 templates)
- **Key Entry Point:** `app.py` - defines all routes and request handling
- **Calculation Engine:** `investment_logic.py` - contains `investmentGrowth_calci()` function
- **Data Layer:** Pandas DataFrames, JSON serialization for charts
- **Visualization:** Plotly Express for interactive line charts
- **PDF Generation:** ReportLab for exporting results

### Frontend Stack
- **Templates:** Jinja2 HTML files in `/templates` folder
- **Static Assets:** CSS, images in `/static` folder
- **Dynamic Loading:** JavaScript fetch-based component loading for header/footer (`header.html`, `footer.html`)
- **Styling:** Single `style.css` file with responsive design and mobile menu toggle

## Critical Data Flow Patterns

### Investment Calculator Route (`/investment`)
1. **GET Request:** Renders empty `investment.html` template
2. **POST Request:** 
   - Receives form parameters: equity/debt returns (%), allocations, one-time amount, SIP amount, tenure months, increment type
   - Calls `investment_logic.investmentGrowth_calci()` 
   - Stores result in global `last_table` variable (for PDF download)
   - Converts Pandas DataFrame to HTML string via `.to_html(classes="table table-striped")`
   - Serializes Plotly figure to JSON via `plotly.utils.PlotlyJSONEncoder`
   - Renders with variables: `table_html`, `graph_json`

### PDF Download Route (`/download_pdf`)
- Uses global `last_table` variable stored from last investment calculation
- Converts table to HTML within PDF using ReportLab
- Returns BytesIO buffer as downloadable file

**⚠️ Design Issue:** Global variable `last_table` couples state between routes - consider refactoring to session storage if concurrent users added.

## Calculation Logic (`investment_logic.py`)

### Function Signature
```python
investmentGrowth_calci(equity_return, debt_return, equity_allocation, onetime_amount, 
                       sip_amount, tenure_months, annual_SIP_increment_in, sip_increment=0)
```

### Key Assumptions
- Returns inputs are in percentages (converted to decimals: `/ 100`)
- Allocation inputs totals 100% (debt calculated as `100 - equity_allocation`)
- Monthly return derived from annual via: `(annual_return + 1)^(1/12) - 1`
- **SIP Increment Modes:**
  - `'Nil'`: Flat amount each month
  - `'Amount'`: Linear increase by fixed amount annually
  - `'Percentage'`: Compound growth rate applied annually
  
### Output
Returns tuple: `(growth_data_df, plotly_figure)`
- DataFrame columns: `['Date', 'Invested Amount', 'Expected Value']`
- Date range: From today for `tenure_months` forward
- Values rounded to nearest integer

## Project Conventions

### File Organization
- Core business logic: `investment_logic.py` (pure functions, no state)
- Request handling: `app.py` (routes, form parsing, templating)
- HTML component reuse: Separate `header.html`, `footer.html` loaded dynamically
- CSS centralized: Single `style.css` file

### Form Data Handling Pattern
```python
# Route receives form data as strings, explicitly converts to integers
equity_return = int(request.form["field_name"])
# Forms in templates use name attributes matching these keys
```

### Template Rendering
- Conditional rendering of results: `table_html` and `graph_json` default to `None`
- Chart embedding: Plotly JSON passed as string, requires JavaScript `Plotly.newPlot()`
- No template inheritance structure currently - each template is standalone with component loading

## Common Development Workflows

### Running Locally
```bash
python app.py  # Flask dev server runs on http://0.0.0.0:5000 with debug=True
```

### Adding New Calculator Pages
1. Create HTML form in `templates/{name}.html` using same form pattern as `investment.html`
2. Add route in `app.py`: `@app.route("/{path}", methods=["GET","POST"])`
3. Create calculation function in `investment_logic.py` (match naming pattern: `{name}_calci()`)
4. Import and call function, pass results to template

### Modifying Investment Calculation
- Edit logic in `investmentGrowth_calci()` - changes automatically reflect in calculator
- All calculations based on monthly compounding
- Ensure return inputs stay in percentage format (handled in route via `/ 100`)

## Integration Points & Dependencies

### External APIs/Services
- None currently - all computation is local

### Python Package Dependencies
- `flask` - web framework
- `pandas` - data frames, HTML export
- `plotly` - charting library
- `reportlab` - PDF generation
- `python-dateutil` - date manipulation for tenure calculations

## Important Notes

### Design Patterns to Preserve
- Separation of calculation logic (investment_logic.py) from request handling (app.py)
- Explicit integer conversion from form inputs (prevents type errors)
- Composite portfolio return calculation using weighted average

### Known Limitations
1. **State Management:** Global `last_table` variable - not thread-safe for concurrent users
2. **No Input Validation:** Form values assumed valid integers; no range checks
3. **No Data Persistence:** All calculations are ephemeral (no database)
4. **Component Loading:** Dynamic header/footer loading requires JavaScript; no server-side includes

### Testing Opportunities
- Unit tests for `investmentGrowth_calci()` function with various increment modes
- Integration tests for calculator route with POST data
- PDF generation verification
