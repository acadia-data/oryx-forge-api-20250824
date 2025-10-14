# IOService Guide for AI Agents

This guide explains how to use `IOService` methods directly in generated Python code for data analysis and visualization workflows.

## Overview

### What is IOService?

`IOService` is the service class for saving and loading:
- **DataFrames** as parquet files
- **Plotly charts** as interactive HTML files
- **Markdown documents** as .md files

All with automatic dataset/sheet metadata management in the database.

### Exploration vs Tasks

**Use IOService directly for:**
- Ad-hoc exploratory data analysis (EDA)
- Interactive analysis and visualization
- Quick experiments and prototypes
- Reports and documentation

**Use d6tflow tasks for:**
- Production data pipelines
- Repeatable transformations
- Scheduled workflows
- Data with complex dependencies

### Dataset.Sheet Notation

All IOService operations use `dataset.sheet` notation:
```python
name_python = "exploration.HpiAnalysis"
#              ^^^^^^^^^    ^^^^^^^^^^^
#              dataset      sheet
```

- Dataset: `exploration` (default for ad-hoc work)
- Sheet: Your chosen name (converted to PascalCase automatically)

## Setup

### Initialize IOService

```python
from oryxforge.services.io_service import IOService

# Uses profile from .oryxforge configuration automatically
io = IOService()

# Or specify explicitly (rarely needed)
io = IOService(project_id="...", user_id="...")
```

No manual configuration needed - credentials are read from the `.oryxforge` profile in your working directory.

## DataFrame Operations

### Save DataFrame

Save analysis results, filtered data, or any pandas DataFrame:

```python
import pandas as pd
from oryxforge.services.io_service import IOService

io = IOService()

# Your analysis
df = pd.read_csv('raw_data.csv')
df_clean = df.dropna().query('value > 0')

# Save with automatic metadata tracking (saves to Exploration by default)
result = io.save_df_pd(df_clean, "Cleaned Data")

print(result)
# {
#     'message': 'DataFrame saved successfully',
#     'dataset_id': '...',
#     'dataset_name_python': 'exploration',
#     'sheet_id': '...',
#     'sheet_name_python': 'CleanedData',  # PascalCase
#     'path': './data/exploration/CleanedData.parquet',
#     'shape': (1000, 5)
# }
```

**Key Points:**
- Sheet name is converted to PascalCase automatically
- Saves to `Exploration` dataset by default
- File saved as parquet for efficiency
- Metadata tracked in database for discovery

### Load DataFrame

```python
# Load using dataset.sheet notation
df = io.load_df_pd("exploration.CleanedData")

# Now work with the DataFrame
print(df.head())
print(df.describe())
```

**Loading from d6tflow tasks:**
```python
# Automatically executes task if needed
df = io.load_df_pd("sources.HpiMasterCsv")
```

## Chart Operations

### Save Plotly Chart

Save interactive visualizations as HTML files:

```python
import plotly.express as px
from oryxforge.services.io_service import IOService

io = IOService()

# Create visualization
df = io.load_df_pd("exploration.CleanedData")
fig = px.line(df, x='date', y='value', title='Trend Analysis')

# Save chart
result = io.save_chart_plotly(fig, "Trend Chart")

print(result)
# {
#     'message': 'Chart saved successfully',
#     'dataset_id': '...',
#     'dataset_name_python': 'exploration',
#     'sheet_id': '...',
#     'sheet_name_python': 'TrendChart',
#     'path': './data/exploration/TrendChart.html'
# }
```

### Load Chart

```python
# Get path only (for opening in browser)
chart_path = io.load_chart_plotly("exploration.TrendChart")
print(f"Open chart: {chart_path}")

# Get path AND HTML content (for embedding)
chart_data = io.load_chart_plotly("exploration.TrendChart", return_html=True)
print(chart_data['path'])
print(chart_data['html_content'][:100])  # First 100 chars
```

## Markdown Operations

### Save Markdown

Save analysis reports, documentation, or notes:

```python
from oryxforge.services.io_service import IOService

io = IOService()

# Generate report
markdown_content = f"""
# Analysis Report: Cleaned Data

## Summary
- Total rows: {len(df)}
- Date range: {df['date'].min()} to {df['date'].max()}
- Average value: {df['value'].mean():.2f}

## Key Findings
1. Strong upward trend observed
2. Seasonal patterns detected
3. Outliers removed during cleaning

## Visualizations
See [Trend Chart](exploration.TrendChart)

## Recommendations
- Monitor for continued growth
- Review seasonal adjustments quarterly
"""

# Save report
result = io.save_markdown(markdown_content, "Analysis Report")

print(result)
# {
#     'message': 'Markdown saved successfully',
#     'dataset_id': '...',
#     'dataset_name_python': 'exploration',
#     'sheet_id': '...',
#     'sheet_name_python': 'AnalysisReport',
#     'path': './data/exploration/AnalysisReport.md',
#     'length': 456
# }
```

### Load Markdown

```python
# Load report content
report = io.load_markdown("exploration.AnalysisReport")
print(report)

# Use in further processing
with open('final_report.md', 'w') as f:
    f.write(report)
```

## Best Practices

### 1. Descriptive Sheet Names

**Good:**
```python
io.save_df_pd(df, "Customer Churn Analysis")
io.save_chart_plotly(fig, "Monthly Revenue Trend")
io.save_markdown(report, "Q4 Performance Summary")
```

**Avoid:**
```python
io.save_df_pd(df, "data1")
io.save_chart_plotly(fig, "chart")
io.save_markdown(report, "notes")
```

### 2. Error Handling

```python
try:
    df = io.load_df_pd("exploration.CustomerAnalysis")
except ValueError as e:
    if "not found" in str(e):
        print("Analysis not found. Run analysis first.")
    else:
        raise
```

## Common Patterns

### Pattern 1: Complete EDA Workflow

```python
from oryxforge.services.io_service import IOService
import pandas as pd
import plotly.express as px

io = IOService()

# 1. Load source data
df_raw = pd.read_csv('customer_data.csv')

# 2. Clean and analyze
df_clean = df_raw.dropna()
df_clean['revenue'] = df_clean['price'] * df_clean['quantity']

# 3. Save cleaned data
io.save_df_pd(df_clean, "Customer Data Cleaned")

# 4. Create visualizations
fig_revenue = px.bar(df_clean, x='category', y='revenue',
                     title='Revenue by Category')
io.save_chart_plotly(fig_revenue, "Revenue by Category")

fig_trend = px.line(df_clean, x='date', y='revenue',
                    title='Revenue Trend')
io.save_chart_plotly(fig_trend, "Revenue Trend")

# 5. Generate report
report = f"""
# Customer Data Analysis

## Overview
- Total customers: {len(df_clean)}
- Total revenue: ${df_clean['revenue'].sum():,.2f}
- Date range: {df_clean['date'].min()} to {df_clean['date'].max()}

## Key Metrics
- Average order value: ${df_clean['revenue'].mean():.2f}
- Top category: {df_clean.groupby('category')['revenue'].sum().idxmax()}

## Visualizations
- [Revenue by Category](exploration.RevenueByCategory)
- [Revenue Trend](exploration.RevenueTrend)

## Recommendations
Based on the analysis, we recommend:
1. Focus marketing on top-performing categories
2. Investigate declining trend in Q3
3. Implement customer retention program
"""

io.save_markdown(report, "Customer Analysis Report")

print("Analysis complete!")
print("- Data: exploration.CustomerDataCleaned")
print("- Charts: exploration.RevenueByCategory, exploration.RevenueTrend")
print("- Report: exploration.CustomerAnalysisReport")
```

### Pattern 2: Iterative Analysis

```python
from oryxforge.services.io_service import IOService
import pandas as pd

io = IOService()

# Load previous analysis results
df_initial = io.load_df_pd("exploration.CustomerMetrics")

# Refine analysis with normalization
df_normalized = df_initial.copy()
df_normalized['normalized_value'] = (df_normalized['value'] - df_normalized['value'].mean()) / df_normalized['value'].std()

# Save updated version with descriptive name
io.save_df_pd(df_normalized, "Customer Metrics Normalized")
```

### Pattern 3: Multi-Sheet Analysis

```python
from oryxforge.services.io_service import IOService
import pandas as pd

io = IOService()

# Load multiple related datasets
df_sales = io.load_df_pd("exploration.SalesData")
df_customers = io.load_df_pd("exploration.CustomerData")
df_products = io.load_df_pd("exploration.ProductData")

# Merge and analyze
df_combined = df_sales.merge(df_customers, on='customer_id') \
                      .merge(df_products, on='product_id')

df_analysis = df_combined.groupby(['customer_segment', 'product_category']) \
                         .agg({'revenue': 'sum', 'quantity': 'sum'}) \
                         .reset_index()

# Save combined analysis
io.save_df_pd(df_analysis, "Segment Product Analysis")
```

### Pattern 4: Report Generation

```python
from oryxforge.services.io_service import IOService
import pandas as pd
import plotly.express as px
from datetime import datetime

io = IOService()

# Load all analysis artifacts
df = io.load_df_pd("exploration.FinalAnalysis")
trend_chart_path = io.load_chart_plotly("exploration.TrendChart")
dist_chart_path = io.load_chart_plotly("exploration.Distribution")

# Generate comprehensive report
report = f"""
# Monthly Analysis Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Executive Summary
{df['metric'].describe().to_markdown()}

## Detailed Analysis
### Trend Analysis
![Trend Chart]({trend_chart_path})

Key observations:
- Metric shows {df['metric'].iloc[-1] / df['metric'].iloc[0] - 1:.1%} change
- Peak occurred on {df.loc[df['metric'].idxmax(), 'date']}

### Distribution Analysis
![Distribution]({dist_chart_path})

Statistical properties:
- Mean: {df['metric'].mean():.2f}
- Median: {df['metric'].median():.2f}
- Std Dev: {df['metric'].std():.2f}

## Data Sources
- Analysis: exploration.FinalAnalysis
- Trend Chart: exploration.TrendChart
- Distribution: exploration.Distribution

## Next Steps
1. Review anomalies in detail
2. Compare with historical baseline
3. Update forecasting model
"""

io.save_markdown(report, f"Monthly Report {datetime.now().strftime('%Y-%m')}")
```

## Troubleshooting

### Error: "Cannot save to dataset 'MyDataset'"

**Cause:** Only 'Exploration' dataset can be saved directly.

**Solution:** Save using the simple form (saves to Exploration automatically):
```python
io.save_df_pd(df, "My Sheet")
io.save_chart_plotly(fig, "My Chart")
io.save_markdown(report, "My Report")
```

### Error: "Dataset-sheet combination not found"

**Cause:** Trying to load a sheet that doesn't exist.

**Solution:** Check available sheets:
```python
from oryxforge.services.project_service import ProjectService
ps = ProjectService()
available = ps.ds_sheet_list(format='df')
print(available)
```

### Error: "Parquet file not found"

**Cause:** File was deleted or moved outside of IOService.

**Solution:** Re-save the data or check file system:
```python
# Check if sheet exists in database
result = ps.ds_sheet_get("exploration.MySheet")
print(result['sheet']['uri'])  # Check expected path
```

### Error: "Cannot save empty DataFrame"

**Cause:** DataFrame has no rows.

**Solution:** Validate before saving:
```python
if not df.empty:
    io.save_df_pd(df, "My Analysis")
else:
    print("No data to save")
```

## API Reference Quick Guide

### IOService Methods

```python
# DataFrame operations
save_df_pd(df: pd.DataFrame, sheet_name: str, dataset_name: str = 'Exploration') -> dict
load_df_pd(name_python: str) -> pd.DataFrame

# Chart operations
save_chart_plotly(fig, sheet_name: str, dataset_name: str = 'Exploration') -> dict
load_chart_plotly(name_python: str, return_html: bool = False) -> Union[str, dict]

# Markdown operations
save_markdown(content: str, sheet_name: str, dataset_name: str = 'Exploration') -> dict
load_markdown(name_python: str) -> str
```

### Return Values

**Save methods return:**
```python
{
    'message': str,
    'dataset_id': str,
    'dataset_name_python': str,
    'sheet_id': str,
    'sheet_name_python': str,
    'path': str,
    'shape': tuple,  # DataFrame only
    'length': int    # Markdown only
}
```

## Additional Resources

- **WorkflowService Guide:** For d6tflow task-based workflows
- **ProjectService Guide:** For dataset/sheet management
- **MCP Tools Reference:** For Claude Code integration
- **API Reference:** Full method documentation
