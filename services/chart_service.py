import logging
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

COLOR_PALETTE = [
    "#4f46e5", "#06b6d4", "#10b981", "#f59e0b",
    "#ec4899", "#8b5cf6", "#3b82f6", "#14b8a6"
]


def apply_theme(fig):
    """
    Apply a professional, clean PowerBI-inspired styling theme to Plotly figures.
    """
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=45, r=25, t=55, b=45),
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
            size=12,
            color="#334155"
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        colorway=COLOR_PALETTE,
        hoverlabel=dict(
            bgcolor="#1e293b",
            font_size=12,
            font_color="#ffffff",
            font_family="Inter, sans-serif"
        ),
        title=dict(
            font=dict(size=15, color="#0f172a", family="Inter, sans-serif"),
            x=0.02,
            xanchor="left"
        )
    )
    fig.update_xaxes(
        gridcolor="#f1f5f9",
        zerolinecolor="#e2e8f0",
        tickfont=dict(size=11, color="#64748b")
    )
    fig.update_yaxes(
        gridcolor="#f1f5f9",
        zerolinecolor="#e2e8f0",
        tickfont=dict(size=11, color="#64748b")
    )
    return fig


def create_charts(df: pd.DataFrame, column_types: dict) -> list:
    """
    Automatically generate professional charts based on detected dataset attributes.
    """
    charts = []
    if df.empty:
        return charts

    numeric_columns = column_types.get("numeric", [])
    categorical_columns = column_types.get("categorical", [])
    date_columns = column_types.get("date", [])

    # Filter out pure ID columns if possible from categorical list
    valid_categories = [c for c in categorical_columns if c in df.columns]
    valid_numerics = [c for c in numeric_columns if c in df.columns]

    # 1. CATEGORY + NUMERIC -> BAR CHART
    if valid_categories and valid_numerics:
        category = valid_categories[0]
        numeric = valid_numerics[0]
        try:
            grouped = (
                df.groupby(category, dropna=False)[numeric]
                .sum()
                .reset_index()
                .sort_values(numeric, ascending=False)
                .head(15)
            )
            grouped[category] = grouped[category].fillna("Unknown").astype(str)

            fig = px.bar(
                grouped,
                x=category,
                y=numeric,
                title=f"{numeric} by {category}",
                color_discrete_sequence=[COLOR_PALETTE[0]]
            )
            apply_theme(fig)
            charts.append({
                "title": f"{numeric} by {category}",
                "figure": fig.to_json(),
                "type": "bar"
            })
        except Exception as error:
            logger.error("Error creating bar chart for %s and %s: %s", category, numeric, error)

    # 2. CATEGORY -> DONUT CHART (TOP 8 + OTHER)
    if valid_categories:
        category = valid_categories[0]
        try:
            counts = df[category].fillna("Unknown").astype(str).value_counts()
            if len(counts) > 8:
                top_counts = counts.head(7)
                other_sum = counts.iloc[7:].sum()
                donut_df = pd.DataFrame({
                    category: list(top_counts.index) + ["Other"],
                    "Count": list(top_counts.values) + [other_sum]
                })
            else:
                donut_df = counts.reset_index()
                donut_df.columns = [category, "Count"]

            fig = px.pie(
                donut_df,
                names=category,
                values="Count",
                hole=0.6,
                title=f"{category} Distribution"
            )
            apply_theme(fig)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            charts.append({
                "title": f"{category} Distribution",
                "figure": fig.to_json(),
                "type": "donut"
            })
        except Exception as error:
            logger.error("Error creating donut chart for %s: %s", category, error)

    # 3. DATE + NUMERIC -> MONTHLY TREND LINE
    if date_columns and valid_numerics:
        date_column = date_columns[0]
        numeric = valid_numerics[0]
        try:
            temp_df = df[[date_column, numeric]].dropna().copy()
            if not temp_df.empty:
                temp_df[date_column] = pd.to_datetime(temp_df[date_column], errors="coerce")
                temp_df = temp_df.dropna(subset=[date_column])

                if not temp_df.empty:
                    trend = (
                        temp_df.set_index(date_column)
                        .resample("ME")[numeric]
                        .sum()
                        .reset_index()
                    )
                    if len(trend) > 1:
                        fig = px.line(
                            trend,
                            x=date_column,
                            y=numeric,
                            markers=True,
                            title=f"{numeric} Trend Over Time",
                            color_discrete_sequence=[COLOR_PALETTE[1]]
                        )
                        apply_theme(fig)
                        charts.append({
                            "title": f"{numeric} Trend Over Time",
                            "figure": fig.to_json(),
                            "type": "line"
                        })
        except Exception as error:
            logger.error("Error creating trend line chart: %s", error)

    # 4. NUMERIC -> HISTOGRAM / DISTRIBUTION
    if valid_numerics:
        numeric = valid_numerics[0]
        try:
            fig = px.histogram(
                df,
                x=numeric,
                nbins=30,
                marginal="box",
                title=f"{numeric} Distribution & Spread",
                color_discrete_sequence=[COLOR_PALETTE[2]]
            )
            apply_theme(fig)
            charts.append({
                "title": f"{numeric} Distribution & Spread",
                "figure": fig.to_json(),
                "type": "histogram"
            })
        except Exception as error:
            logger.error("Error creating histogram for %s: %s", numeric, error)

    # 5. TWO NUMERICS -> SCATTER PLOT
    if len(valid_numerics) >= 2:
        x_col = valid_numerics[0]
        y_col = valid_numerics[1]
        try:
            color_col = valid_categories[0] if valid_categories else None
            fig = px.scatter(
                df.head(2000),  # Limit scatter to 2000 points for browser performance
                x=x_col,
                y=y_col,
                color=color_col,
                title=f"{x_col} vs {y_col}",
                color_discrete_sequence=COLOR_PALETTE
            )
            apply_theme(fig)
            charts.append({
                "title": f"{x_col} vs {y_col}",
                "figure": fig.to_json(),
                "type": "scatter"
            })
        except Exception as error:
            logger.error("Error creating scatter plot: %s", error)

    # 6. SECOND CATEGORY -> AVERAGE BAR CHART
    if len(valid_categories) >= 2 and valid_numerics:
        category2 = valid_categories[1]
        numeric = valid_numerics[0]
        try:
            grouped2 = (
                df.groupby(category2, dropna=False)[numeric]
                .mean()
                .reset_index()
                .sort_values(numeric, ascending=False)
                .head(15)
            )
            grouped2[category2] = grouped2[category2].fillna("Unknown").astype(str)

            fig = px.bar(
                grouped2,
                x=category2,
                y=numeric,
                title=f"Average {numeric} by {category2}",
                color_discrete_sequence=[COLOR_PALETTE[3]]
            )
            apply_theme(fig)
            charts.append({
                "title": f"Average {numeric} by {category2}",
                "figure": fig.to_json(),
                "type": "bar"
            })
        except Exception as error:
            logger.error("Error creating average bar chart: %s", error)

    # 7. CORRELATION HEATMAP
    if len(valid_numerics) >= 2:
        try:
            corr_df = df[valid_numerics[:8]].corr().round(2)
            fig = px.imshow(
                corr_df,
                text_auto=True,
                aspect="auto",
                color_continuous_scale="RdBu_r",
                title="Correlation Heatmap Matrix"
            )
            apply_theme(fig)
            charts.append({
                "title": "Correlation Heatmap Matrix",
                "figure": fig.to_json(),
                "type": "heatmap"
            })
        except Exception as error:
            logger.error("Error creating correlation matrix: %s", error)

    return charts
