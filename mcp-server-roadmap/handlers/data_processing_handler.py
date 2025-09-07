"""
Handles data processing operations.
Provides tools for data analysis and transformation suggestions.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from mcp.types import Tool, TextContent

class DataProcessingHandler:
    """Handles data processing and analysis operations."""
    
    def __init__(self, data_directory: str = "data"):
        self.data_directory = Path(data_directory)
    
    def get_tools(self) -> List[Tool]:
        """Returns the tools this handler provides."""
        return [
            Tool(
                name="analyze_data",
                description="Analyze a data file and provide comprehensive insights",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the data file to analyze"
                        }
                    },
                    "required": ["filename"]
                }
            ),
            Tool(
                name="suggest_transformations",
                description="Suggest data transformations based on file content and structure",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the data file to analyze"
                        }
                    },
                    "required": ["filename"]
                }
            ),
            Tool(
                name="detect_data_issues",
                description="Detect common data quality issues in a file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the data file to analyze"
                        }
                    },
                    "required": ["filename"]
                }
            ),
            Tool(
                name="generate_data_summary",
                description="Generate a comprehensive data summary report",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the data file to summarize"
                        }
                    },
                    "required": ["filename"]
                }
            )
        ]
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls for data processing."""
        
        if tool_name == "analyze_data":
            return await self._analyze_data(arguments["filename"])
        elif tool_name == "suggest_transformations":
            return await self._suggest_transformations(arguments["filename"])
        elif tool_name == "detect_data_issues":
            return await self._detect_data_issues(arguments["filename"])
        elif tool_name == "generate_data_summary":
            return await self._generate_data_summary(arguments["filename"])
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _analyze_data(self, filename: str) -> List[TextContent]:
        """Analyze a data file and provide comprehensive insights."""
        try:
            file_path = self.data_directory / filename
            
            if not file_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: File '{filename}' not found"
                )]
            
            # Load data
            df = self._load_dataframe(file_path)
            if df is None:
                return [TextContent(
                    type="text",
                    text=f"Error: Could not load file '{filename}'"
                )]
            
            analysis = self._perform_data_analysis(df, filename)
            return [TextContent(type="text", text=analysis)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error analyzing data '{filename}': {str(e)}"
            )]
    
    async def _suggest_transformations(self, filename: str) -> List[TextContent]:
        """Suggest data transformations based on file content."""
        try:
            file_path = self.data_directory / filename
            
            if not file_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: File '{filename}' not found"
                )]
            
            df = self._load_dataframe(file_path)
            if df is None:
                return [TextContent(
                    type="text",
                    text=f"Error: Could not load file '{filename}'"
                )]
            
            suggestions = self._generate_transformation_suggestions(df, filename)
            return [TextContent(type="text", text=suggestions)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error suggesting transformations for '{filename}': {str(e)}"
            )]
    
    async def _detect_data_issues(self, filename: str) -> List[TextContent]:
        """Detect common data quality issues."""
        try:
            file_path = self.data_directory / filename
            
            if not file_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: File '{filename}' not found"
                )]
            
            df = self._load_dataframe(file_path)
            if df is None:
                return [TextContent(
                    type="text",
                    text=f"Error: Could not load file '{filename}'"
                )]
            
            issues = self._detect_quality_issues(df, filename)
            return [TextContent(type="text", text=issues)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error detecting issues in '{filename}': {str(e)}"
            )]
    
    async def _generate_data_summary(self, filename: str) -> List[TextContent]:
        """Generate a comprehensive data summary report."""
        try:
            file_path = self.data_directory / filename
            
            if not file_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: File '{filename}' not found"
                )]
            
            df = self._load_dataframe(file_path)
            if df is None:
                return [TextContent(
                    type="text",
                    text=f"Error: Could not load file '{filename}'"
                )]
            
            summary = self._generate_summary_report(df, filename)
            return [TextContent(type="text", text=summary)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error generating summary for '{filename}': {str(e)}"
            )]
    
    def _load_dataframe(self, file_path: Path) -> pd.DataFrame:
        """Load a dataframe from various file formats."""
        try:
            if file_path.suffix == '.csv':
                return pd.read_csv(file_path)
            elif file_path.suffix in ['.xlsx', '.xls']:
                return pd.read_excel(file_path)
            elif file_path.suffix == '.parquet':
                return pd.read_parquet(file_path)
            else:
                return None
        except Exception:
            return None
    
    def _perform_data_analysis(self, df: pd.DataFrame, filename: str) -> str:
        """Perform comprehensive data analysis."""
        analysis = f"# Data Analysis Report: {filename}\n\n"
        
        # Basic info
        analysis += f"**Shape:** {df.shape[0]:,} rows × {df.shape[1]} columns\n"
        analysis += f"**Memory Usage:** {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB\n\n"
        
        # Data types
        analysis += "## Data Types\n"
        for col, dtype in df.dtypes.items():
            analysis += f"- {col}: {dtype}\n"
        analysis += "\n"
        
        # Missing values
        missing = df.isnull().sum()
        if missing.sum() > 0:
            analysis += "## Missing Values\n"
            for col, count in missing[missing > 0].items():
                pct = (count / len(df)) * 100
                analysis += f"- {col}: {count:,} ({pct:.1f}%)\n"
            analysis += "\n"
        
        # Numeric columns analysis
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            analysis += "## Numeric Columns Summary\n"
            numeric_summary = df[numeric_cols].describe()
            analysis += numeric_summary.to_string()
            analysis += "\n\n"
        
        # Categorical columns analysis
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        if len(categorical_cols) > 0:
            analysis += "## Categorical Columns Summary\n"
            for col in categorical_cols:
                unique_count = df[col].nunique()
                analysis += f"- {col}: {unique_count} unique values\n"
                if unique_count <= 10:
                    value_counts = df[col].value_counts()
                    analysis += f"  Top values: {dict(value_counts.head(3))}\n"
            analysis += "\n"
        
        return analysis
    
    def _generate_transformation_suggestions(self, df: pd.DataFrame, filename: str) -> str:
        """Generate transformation suggestions based on data analysis."""
        suggestions = f"# Transformation Suggestions for {filename}\n\n"
        
        # Missing value suggestions
        missing = df.isnull().sum()
        if missing.sum() > 0:
            suggestions += "## Missing Value Handling\n"
            for col, count in missing[missing > 0].items():
                pct = (count / len(df)) * 100
                if pct > 50:
                    suggestions += f"- **{col}**: Consider dropping (missing {pct:.1f}%)\n"
                elif pct > 10:
                    suggestions += f"- **{col}**: Consider imputation or flagging (missing {pct:.1f}%)\n"
                else:
                    suggestions += f"- **{col}**: Safe to impute (missing {pct:.1f}%)\n"
            suggestions += "\n"
        
        # Data type suggestions
        suggestions += "## Data Type Optimizations\n"
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if it's actually numeric
                if df[col].str.replace('.', '').str.replace('-', '').str.isnumeric().all():
                    suggestions += f"- **{col}**: Convert to numeric type\n"
                # Check if it's datetime
                elif df[col].str.contains(r'\d{4}-\d{2}-\d{2}').any():
                    suggestions += f"- **{col}**: Convert to datetime type\n"
                # Check if it's categorical
                elif df[col].nunique() / len(df) < 0.1:
                    suggestions += f"- **{col}**: Convert to categorical type\n"
        
        # Numeric column suggestions
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            suggestions += "\n## Numeric Column Transformations\n"
            for col in numeric_cols:
                if df[col].min() < 0 and df[col].max() > 0:
                    suggestions += f"- **{col}**: Consider log transformation (has negative values)\n"
                elif df[col].skew() > 2:
                    suggestions += f"- **{col}**: Consider log transformation (high skewness: {df[col].skew():.2f})\n"
                elif df[col].std() / df[col].mean() > 1:
                    suggestions += f"- **{col}**: Consider standardization (high coefficient of variation)\n"
        
        return suggestions
    
    def _detect_quality_issues(self, df: pd.DataFrame, filename: str) -> str:
        """Detect data quality issues."""
        issues = f"# Data Quality Issues in {filename}\n\n"
        
        issue_count = 0
        
        # Missing values
        missing = df.isnull().sum()
        if missing.sum() > 0:
            issues += "## Missing Values\n"
            for col, count in missing[missing > 0].items():
                pct = (count / len(df)) * 100
                issues += f"⚠️ **{col}**: {count:,} missing values ({pct:.1f}%)\n"
                issue_count += 1
            issues += "\n"
        
        # Duplicate rows
        duplicates = df.duplicated().sum()
        if duplicates > 0:
            issues += f"## Duplicate Rows\n"
            issues += f"⚠️ {duplicates:,} duplicate rows found\n"
            issue_count += 1
        
        # Outliers in numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            outliers = df[(df[col] < Q1 - 1.5 * IQR) | (df[col] > Q3 + 1.5 * IQR)]
            if len(outliers) > 0:
                if issue_count == 0:
                    issues += "## Outliers\n"
                issues += f"⚠️ **{col}**: {len(outliers)} outliers detected\n"
                issue_count += 1
        
        # Inconsistent data types
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check for mixed types
                non_null_values = df[col].dropna()
                if len(non_null_values) > 0:
                    first_type = type(non_null_values.iloc[0])
                    inconsistent = not all(isinstance(x, first_type) for x in non_null_values)
                    if inconsistent:
                        if issue_count == 0:
                            issues += "## Data Type Issues\n"
                        issues += f"⚠️ **{col}**: Mixed data types detected\n"
                        issue_count += 1
        
        if issue_count == 0:
            issues += "✅ No major data quality issues detected!\n"
        
        return issues
    
    def _generate_summary_report(self, df: pd.DataFrame, filename: str) -> str:
        """Generate a comprehensive summary report."""
        summary = f"# Data Summary Report: {filename}\n\n"
        
        # File info
        summary += f"**File:** {filename}\n"
        summary += f"**Shape:** {df.shape[0]:,} rows × {df.shape[1]} columns\n"
        summary += f"**Memory Usage:** {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB\n\n"
        
        # Quick stats
        summary += "## Quick Statistics\n"
        summary += f"- **Total Cells:** {df.size:,}\n"
        summary += f"- **Missing Values:** {df.isnull().sum().sum():,}\n"
        summary += f"- **Duplicate Rows:** {df.duplicated().sum():,}\n"
        summary += f"- **Numeric Columns:** {len(df.select_dtypes(include=[np.number]).columns)}\n"
        summary += f"- **Text Columns:** {len(df.select_dtypes(include=['object']).columns)}\n\n"
        
        # Column overview
        summary += "## Column Overview\n"
        for col in df.columns:
            dtype = str(df[col].dtype)
            null_count = df[col].isnull().sum()
            null_pct = (null_count / len(df)) * 100
            unique_count = df[col].nunique()
            
            summary += f"- **{col}** ({dtype}): {null_count} nulls ({null_pct:.1f}%), {unique_count} unique values\n"
        
        return summary
