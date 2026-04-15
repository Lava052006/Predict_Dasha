import pandas as pd
import numpy as np
import os
from datetime import timedelta

# Resolve the path to the CSV file — strictly prioritizes root folder dataset
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_csv_in_root = os.path.join(os.path.dirname(BASE_DIR), "processed_marketing_data.csv")
_csv_in_backend = os.path.join(BASE_DIR, "processed_marketing_data.csv")

# Use root CSV if it exists, otherwise fall back to backend one (for safety)
CSV_PATH = _csv_in_root if os.path.exists(_csv_in_root) else _csv_in_backend

# Load data once at service initialization
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    # Filter out invalid dates if any
    df = df[df['date'].notna()]
else:
    # Fallback to empty dataframe with expected columns to prevent server crash
    cols = ['date','campaign_type','region','channel_used','customer_segment','revenue','acquisition_cost','conversions','roas','cac']
    df = pd.DataFrame(columns=cols)

def _apply_filters(df_to_filter, days=None, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = df_to_filter.copy()
    
    if days:
        latest_date = filtered_df['date'].max()
        cutoff_date = latest_date - pd.Timedelta(days=int(days))
        filtered_df = filtered_df[filtered_df['date'] > cutoff_date]
        
    if campaign_type and campaign_type != "All":
        filtered_df = filtered_df[filtered_df['campaign_type'] == campaign_type]
        
    if region and region != "Global":
        filtered_df = filtered_df[filtered_df['region'] == region]
        
    if channel and channel != "All":
        filtered_df = filtered_df[filtered_df['channel_used'] == channel]
        
    if segment and segment != "All":
        filtered_df = filtered_df[filtered_df['customer_segment'] == segment]
        
    return filtered_df

def generate_kpis(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, None, campaign_type, region, channel, segment)
    
    latest_date = filtered_df['date'].max()
    period_delta = pd.Timedelta(days=int(days))
    
    current_df = filtered_df[filtered_df['date'] > (latest_date - period_delta)]
    prev_df = filtered_df[(filtered_df['date'] <= (latest_date - period_delta)) & 
                          (filtered_df['date'] > (latest_date - 2 * period_delta))]
    
    def get_kpi_data(metric_col, is_sum=True):
        if current_df.empty: return {"value": "0", "change": 0.0, "isPositive": True}
        curr_val = current_df[metric_col].sum() if is_sum else current_df[metric_col].mean()
        prev_val = prev_df[metric_col].sum() if is_sum else prev_df[metric_col].mean()
        
        change = ((curr_val - prev_val) / prev_val * 100) if prev_val != 0 else 0.0
        
        if metric_col == 'revenue' or metric_col == 'acquisition_cost':
            val_str = f"${float(curr_val)/1000:,.1f}K"
        elif metric_col == 'cac':
            val_str = f"${float(curr_val):,.2f}"
        elif metric_col == 'roas':
            val_str = f"{float(curr_val):,.2f}x"
        else:
            val_str = str(round(float(curr_val), 2))
            
        is_positive = change > 0
        if metric_col == 'cac':
            is_positive = change < 0
            
        return {"value": val_str, "change": round(float(change), 1), "isPositive": is_positive}

    top_performer = "N/A"
    if not current_df.empty:
        best = current_df.groupby('campaign_type')['roas'].mean().idxmax()
        top_performer = str(best)

    return {
        "revenue": get_kpi_data("revenue"),
        "spend": get_kpi_data("acquisition_cost"),
        "cac": get_kpi_data("cac", is_sum=False),
        "roas": get_kpi_data("roas", is_sum=False),
        "top_performer": top_performer
    }

def generate_performance_data(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    
    daily_stats = filtered_df.groupby('date').agg({
        'revenue': 'sum',
        'acquisition_cost': 'sum'
    }).reset_index()
    
    daily = daily_stats.sort_values('date')
    
    data = []
    for _, row in daily.iterrows():
        data.append({
            "date": row['date'].strftime("%Y-%m-%d"),
            "revenue": round(float(row['revenue']), 2),
            "spend": round(float(row['acquisition_cost']), 2)
        })
    return {"data": data}

def generate_campaign_revenue(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    if filtered_df.empty: return []
    
    stats = filtered_df.groupby('campaign_type')['revenue'].sum().reset_index()
    stats = stats.sort_values('revenue', ascending=False)
    
    return [{"campaign": row['campaign_type'], "revenue": round(float(row['revenue']), 2)} for _, row in stats.iterrows()]

def generate_channel_contribution(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    if filtered_df.empty: return []
    
    # Group by campaign and channel
    stats = filtered_df.groupby(['campaign_type', 'channel_used'])['revenue'].sum().unstack(fill_value=0).reset_index()
    
    results = []
    for _, row in stats.iterrows():
        item = {"campaign": row['campaign_type']}
        for col in stats.columns:
            if col != 'campaign_type':
                item[col] = round(float(row[col]), 2)
        results.append(item)
    return results

def generate_segment_contribution(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    if filtered_df.empty: return []
    
    stats = filtered_df.groupby('customer_segment')['revenue'].sum().reset_index()
    return [{"segment": row['customer_segment'], "revenue": round(float(row['revenue']), 2)} for _, row in stats.iterrows()]

def generate_campaign_roi(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    if filtered_df.empty: return []
    
    stats = filtered_df.groupby('campaign_type')['roas'].mean().reset_index()
    stats = stats.sort_values('roas', ascending=False)
    
    return [{"campaign": row['campaign_type'], "roas": round(float(row['roas']), 2)} for _, row in stats.iterrows()]

def generate_campaign_performance(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    
    if filtered_df.empty:
        return []

    # Aggregated View as per requirement
    perf = filtered_df.groupby(['campaign_type', 'channel_used', 'customer_segment']).agg({
        'revenue': 'sum',
        'acquisition_cost': 'sum',
        'conversions': 'sum',
        'roas': 'mean',
        'cac': 'mean'
    }).reset_index()
    
    results = []
    for i, row in perf.iterrows():
        results.append({
            "id": f"AGGR-{i}",
            "name": row['campaign_type'],
            "channel": row['channel_used'],
            "segment": row['customer_segment'],
            "revenue": round(float(row['revenue']), 2),
            "spend": round(float(row['acquisition_cost']), 2),
            "conversions": int(row['conversions']),
            "roas": round(float(row['roas']), 2),
            "cac": round(float(row['cac']), 2)
        })
    return results

def generate_revenue_trend(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    if filtered_df.empty: return {"data": [], "campaigns": []}
    
    # We need to return data grouped by date AND potentially campaign for the frontend selector
    daily = filtered_df.groupby(['date', 'campaign_type'])['revenue'].sum().reset_index()
    
    data = []
    for _, row in daily.iterrows():
        data.append({
            "date": row['date'].strftime("%Y-%m-%d"),
            "campaign": row['campaign_type'],
            "revenue": round(float(row['revenue']), 2)
        })
        
    return {
        "data": data,
        "campaigns": sorted(filtered_df['campaign_type'].unique().tolist())
    }

def generate_ai_insights(days=30, campaign_type=None, region=None, channel=None, segment=None):
    kpis = generate_kpis(days, campaign_type, region, channel, segment)
    return {
        "healthScore": 82,
        "kpiInsights": ["Revenue is performing well.", "CAC is stable."],
        "forecastSummary": "Steady growth.",
        "anomalyInsights": "No major anomalies."
    }

def generate_ai_campaign_insights(days=30, campaign_type=None, region=None, channel=None, segment=None):
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    if filtered_df.empty: return {"insights": []}
    
    insights = []
    best_roi = filtered_df.groupby('campaign_type')['roas'].mean().idxmax()
    insights.append({
        "type": "success",
        "title": "Top Performer",
        "description": f"{best_roi} campaigns are delivering the highest ROAS currently.",
        "icon": "TrendingUp"
    })
    
    high_cac_channel = filtered_df.groupby('channel_used')['cac'].mean().idxmax()
    insights.append({
        "type": "warning",
        "title": "High CAC Alert",
        "description": f"Customer acquisition cost in {high_cac_channel} is trending above target.",
        "icon": "AlertTriangle"
    })
    
    insights.append({
        "type": "info",
        "title": "Budget Optimization",
        "description": "Increase investment in high-performing segments to capture rising demand.",
        "icon": "Target"
    })
    
    return {"insights": insights}
def generate_revenue_forecast(horizon=30, campaign_type=None, region=None, channel=None, segment=None):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    
    try:
        filtered_df = _apply_filters(df, None, campaign_type, region, channel, segment)
    except:
        return {"kpis": None, "data": []}
        
    if filtered_df.empty:
        return {"kpis": None, "data": []}
        
    daily_revenue = filtered_df.groupby('date')['revenue'].sum().reset_index()
    daily_revenue = daily_revenue.sort_values('date')
    
    if len(daily_revenue) < 14: # Need enough data points
        return {"kpis": None, "data": []}
    
    # Simple Exponential Smoothing (Holt-Winters Lite)
    model = ExponentialSmoothing(
        daily_revenue['revenue'], 
        seasonal='add', 
        seasonal_periods=7
    ).fit()
    
    forecast_values = model.forecast(int(horizon))
    
    # Prepare historical + forecast data
    data_points = []
    for _, row in daily_revenue.iterrows():
        data_points.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "actual": round(float(row['revenue']), 2),
            "forecast": None,
            "lower": None,
            "upper": None
        })
    
    last_date = daily_revenue['date'].max()
    for i, val in enumerate(forecast_values):
        curr_date = last_date + timedelta(days=i+1)
        data_points.append({
            "date": curr_date.strftime('%Y-%m-%d'),
            "actual": None,
            "forecast": round(float(val), 2),
            "lower": round(float(val * 0.9), 2),
            "upper": round(float(val * 1.1), 2)
        })
    
    total_predicted = sum(forecast_values)
    avg_daily = total_predicted / horizon
    
    last_30_actual = daily_revenue.tail(30)['revenue'].sum()
    growth = ((total_predicted - last_30_actual) / last_30_actual * 100) if last_30_actual > 0 else 0
    
    def format_large_currency(val):
        if val >= 1_000_000_000: return f"${val/1_000_000_000:,.2f}B"
        elif val >= 1_000_000: return f"${val/1_000_000:,.2f}M"
        return f"${val/1_000:,.1f}K"

    kpis = {
        "totalPredictedRevenue": format_large_currency(total_predicted),
        "expectedGrowth": round(float(growth), 1),
        "avgDailyForecast": format_large_currency(avg_daily),
        "peakDay": "N/A",
        "troughDay": "N/A",
        "trendStatus": "stable" if abs(growth) < 5 else ("growth" if growth > 0 else "decline")
    }
    
    return {"kpis": kpis, "data": data_points}

def generate_forecast_components(horizon=30, campaign_type=None, region=None, channel=None, segment=None):
    # Simplified components for lightweight model
    filtered_df = _apply_filters(df, None, campaign_type, region, channel, segment)
    if filtered_df.empty: return {"components": None}
    
    daily_revenue = filtered_df.groupby('date')['revenue'].sum().reset_index()
    
    trend_data = []
    for _, row in daily_revenue.iterrows():
        trend_data.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "forecast": round(float(row['revenue']), 2)
        })
        
    return {
        "components": {
            "trend": trend_data,
            "weekly": [],
            "yearly": None
        }
    }

def generate_ai_forecast_insights(horizon=30, campaign_type=None, region=None, channel=None, segment=None):
    return {"insights": [{"title": "Data Processing", "description": "Analyzing historical trends using local light-weight engine.", "type": "info"}]}

def generate_forecast(days=30, campaign_type=None, region=None, channel=None, segment=None):
    res = generate_revenue_forecast(days, campaign_type, region, channel, segment)
    return {
        "projectedGrowth": res['kpis']['expectedGrowth'] if res['kpis'] else 0,
        "next30DaysRevenue": 0,
        "data": res['data']
    }

def generate_anomalies(days=30, campaign_type=None, region=None, channel=None, segment=None):
    from sklearn.ensemble import IsolationForest
    
    filtered_df = _apply_filters(df, days, campaign_type, region, channel, segment)
    if filtered_df.empty: return []
    
    # Prepare features for anomaly detection
    daily = filtered_df.groupby('date').agg({'revenue': 'sum', 'acquisition_cost': 'sum'}).reset_index()
    if len(daily) < 5: return []
    
    model = IsolationForest(contamination=0.05, random_state=42)
    daily['anomaly'] = model.fit_predict(daily[['revenue', 'acquisition_cost']])
    
    anomalies = daily[daily['anomaly'] == -1]
    
    results = []
    for _, row in anomalies.iterrows():
        results.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "metric": "Revenue/Spend",
            "value": round(float(row['revenue']), 2),
            "expected": round(float(daily['revenue'].mean()), 2),
            "severity": "High",
            "description": "Significant deviation from historical baseline detected by AI."
        })
    return results

