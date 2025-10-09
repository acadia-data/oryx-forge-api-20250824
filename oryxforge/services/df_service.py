"""DataFrame analysis service for generating detailed reports on pandas DataFrames."""

from typing import Optional
import pandas as pd
from jinja2 import Template


class DFService:
    """Service for analyzing and reporting on pandas DataFrames."""

    DESCRIBE_TEMPLATE = """# DataFrame Analysis Report

## Overview
- **Shape**: {{ shape[0] }} rows � {{ shape[1] }} columns
- **Memory Usage**: {{ memory_usage }}

## Column Information
{{ column_info }}

## Data Preview

### Head (first {{ head_rows }} rows)
{{ head_table }}

### Tail (last {{ tail_rows }} rows)
{{ tail_table }}

## Statistical Summary
{{ describe_table }}

## Missing Values Analysis
{{ nan_table }}
"""

    def __init__(self):
        """Initialize the DFService."""
        pass

    def describe_pd(
        self,
        df: pd.DataFrame,
        head_rows: int = 5,
        tail_rows: int = 5,
        max_col_width: Optional[int] = None
    ) -> str:
        """Generate a comprehensive markdown report for a pandas DataFrame.

        Args:
            df: The pandas DataFrame to analyze
            head_rows: Number of rows to show in head preview (default: 5)
            tail_rows: Number of rows to show in tail preview (default: 5)
            max_col_width: Maximum column width for display (default: None)

        Returns:
            A markdown-formatted string containing the DataFrame analysis report
        """
        # Set pandas display options for better formatting
        with pd.option_context('display.max_colwidth', max_col_width):
            # Basic info
            shape = df.shape
            memory_usage = df.memory_usage(deep=True).sum()
            # Format bytes using pandas' built-in formatting
            for unit in ['bytes', 'KB', 'MB', 'GB']:
                if memory_usage < 1024.0:
                    memory_usage_str = f"{memory_usage:.1f} {unit}"
                    break
                memory_usage /= 1024.0
            else:
                memory_usage_str = f"{memory_usage:.1f} TB"

            # Column information
            column_info = self._get_column_info(df)

            # Head and tail
            head_table = df.head(head_rows).to_markdown(index=True)
            tail_table = df.tail(tail_rows).to_markdown(index=True)

            # Describe
            describe_table = df.describe(include='all').to_markdown()

            # NaN analysis
            nan_table = self._get_nan_analysis(df)

            # Render template
            template = Template(self.DESCRIBE_TEMPLATE)
            report = template.render(
                shape=shape,
                memory_usage=memory_usage_str,
                column_info=column_info,
                head_rows=head_rows,
                head_table=head_table,
                tail_rows=tail_rows,
                tail_table=tail_table,
                describe_table=describe_table,
                nan_table=nan_table
            )

            return report

    def _get_column_info(self, df: pd.DataFrame) -> str:
        """Generate column information table.

        Args:
            df: The pandas DataFrame

        Returns:
            Markdown-formatted table of column information
        """
        col_info = []
        for col in df.columns:
            col_info.append({
                'Column': col,
                'Type': str(df[col].dtype),
                'Non-Null Count': df[col].count(),
                'Null Count': df[col].isna().sum()
            })

        col_df = pd.DataFrame(col_info)
        return col_df.to_markdown(index=False)

    def _get_nan_analysis(self, df: pd.DataFrame) -> str:
        """Generate NaN percentage analysis table.

        Args:
            df: The pandas DataFrame

        Returns:
            Markdown-formatted table of NaN percentages
        """
        nan_data = []
        total_rows = len(df)

        for col in df.columns:
            nan_count = df[col].isna().sum()
            nan_pct = (nan_count / total_rows * 100) if total_rows > 0 else 0

            nan_data.append({
                'Column': col,
                'NaN Count': nan_count,
                'NaN Percentage': f"{nan_pct:.2f}%"
            })

        # Sort by NaN percentage descending
        nan_df = pd.DataFrame(nan_data)
        nan_df = nan_df.sort_values('NaN Count', ascending=False)

        return nan_df.to_markdown(index=False)
