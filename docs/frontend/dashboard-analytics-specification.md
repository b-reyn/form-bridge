# Form-Bridge Dashboard Analytics Specification

## 1. Key Metrics to Display

### Primary KPIs for Multi-Tenant Form Platform

#### North Star Metrics
- **Daily Successful Submissions**: Total successful form submissions across all sites
- **Processing Success Rate**: (Successful submissions / Total submissions) * 100
- **End-to-End Delivery Rate**: (Successfully delivered / Total processed) * 100
- **Average Processing Time**: P50/P95/P99 latency from ingestion to delivery

#### Leading Indicators
- **Submission Volume Trend**: 24h, 7d, 30d growth rates
- **Active Sites**: Sites with submissions in last 24h/7d
- **Destination Health**: Success rates per destination type
- **Error Rate by Component**: API Gateway, Lambda, EventBridge, Destinations

#### Business Metrics
- **Tenant Activity**: Active tenants, submissions per tenant
- **Site Performance**: Top/bottom performing sites by volume and success rate
- **Feature Adoption**: Usage of advanced routing, custom fields, etc.
- **Cost Per Submission**: AWS costs / total successful submissions

### Real-time vs Historical Data Strategy

#### Real-time (< 30 seconds)
```json
{
  "metrics": [
    "current_submission_rate",
    "active_processing_jobs",
    "error_alerts",
    "destination_status",
    "system_health"
  ],
  "update_frequency": "15 seconds",
  "data_source": "EventBridge + Kinesis Data Streams"
}
```

#### Near Real-time (1-5 minutes)
```json
{
  "metrics": [
    "hourly_volume_trends",
    "success_rate_changes",
    "destination_performance",
    "recent_errors"
  ],
  "update_frequency": "1 minute",
  "data_source": "DynamoDB GSI queries"
}
```

#### Historical (5+ minutes)
```json
{
  "metrics": [
    "daily_summaries",
    "weekly_trends",
    "monthly_reports",
    "year_over_year_comparisons"
  ],
  "update_frequency": "5 minutes",
  "data_source": "Pre-aggregated DynamoDB records"
}
```

### Per-Site vs Aggregate Views

#### Aggregate Dashboard (Default)
- Tenant-level overview across all sites
- Industry benchmarking context
- Cost and performance summaries
- High-level health indicators

#### Site-Level Drill-Down
- Individual site performance metrics
- Form-specific success rates
- Destination-specific delivery status
- Historical performance trends

## 2. Dashboard Widgets

### Core Widget Library

#### 1. Submission Volume Chart
```javascript
{
  "widget_type": "time_series_chart",
  "title": "Form Submissions",
  "metrics": ["successful_submissions", "failed_submissions", "total_submissions"],
  "time_ranges": ["1h", "24h", "7d", "30d"],
  "chart_type": "line_with_area",
  "real_time": true,
  "drill_down": "site_level"
}
```

#### 2. Success/Failure Rate Gauge
```javascript
{
  "widget_type": "gauge_chart",
  "title": "Processing Success Rate",
  "metric": "success_rate_percentage",
  "thresholds": {
    "green": "> 98%",
    "yellow": "95-98%",
    "red": "< 95%"
  },
  "comparison": "previous_period"
}
```

#### 3. Destination Performance Matrix
```javascript
{
  "widget_type": "heat_map",
  "title": "Destination Health Matrix",
  "dimensions": ["destination_type", "site_id"],
  "metric": "delivery_success_rate",
  "color_coding": "red_yellow_green",
  "click_action": "drill_down_destination"
}
```

#### 4. Site Health Overview
```javascript
{
  "widget_type": "data_table",
  "title": "Site Performance Summary",
  "columns": [
    "site_name",
    "24h_submissions",
    "success_rate",
    "avg_processing_time",
    "last_submission",
    "status"
  ],
  "sortable": true,
  "filterable": true,
  "row_limit": 10
}
```

#### 5. Recent Activity Feed
```javascript
{
  "widget_type": "activity_feed",
  "title": "Recent Submissions",
  "events": [
    "successful_submission",
    "failed_submission",
    "destination_failure",
    "system_alert"
  ],
  "time_window": "1h",
  "max_items": 20,
  "real_time": true
}
```

#### 6. Processing Time Distribution
```javascript
{
  "widget_type": "histogram",
  "title": "Response Time Distribution",
  "metric": "processing_time_ms",
  "percentiles": ["P50", "P95", "P99"],
  "time_range": "24h",
  "benchmark_line": "2000ms"
}
```

#### 7. Error Rate Breakdown
```javascript
{
  "widget_type": "stacked_bar_chart",
  "title": "Errors by Component",
  "dimensions": ["api_gateway", "lambda", "eventbridge", "destinations"],
  "metric": "error_count",
  "time_range": "24h",
  "stacking": "normalized"
}
```

#### 8. Cost Tracking Widget
```javascript
{
  "widget_type": "metric_cards",
  "title": "Cost Metrics",
  "cards": [
    {
      "title": "Cost per 1K Submissions",
      "value": "$0.045",
      "trend": "-5%",
      "target": "$0.05"
    },
    {
      "title": "Monthly AWS Spend",
      "value": "$127",
      "trend": "+12%",
      "budget": "$150"
    }
  ]
}
```

## 3. Filtering & Segmentation

### Multi-Dimensional Filter System

#### Time-Based Filtering
```json
{
  "time_filters": {
    "quick_select": ["Last Hour", "Last 24h", "Last 7d", "Last 30d"],
    "custom_range": {
      "start_date": "datetime",
      "end_date": "datetime",
      "timezone": "user_preference"
    },
    "comparison_mode": ["none", "previous_period", "year_over_year"]
  }
}
```

#### Hierarchical Site Filtering
```json
{
  "site_filters": {
    "all_sites": "default",
    "site_groups": [
      {
        "group_name": "E-commerce Sites",
        "sites": ["site1.com", "site2.com"]
      },
      {
        "group_name": "Lead Generation",
        "sites": ["leadgen1.com", "leadgen2.com"]
      }
    ],
    "individual_sites": "searchable_dropdown",
    "multi_select": true
  }
}
```

#### Destination-Based Filtering
```json
{
  "destination_filters": {
    "by_type": ["webhook", "slack", "teams", "email", "salesforce"],
    "by_status": ["active", "failed", "disabled"],
    "by_performance": ["high", "medium", "low"]
  }
}
```

#### Form Type Segmentation
```json
{
  "form_filters": {
    "contact_forms": "Contact Us, Get Quote",
    "lead_generation": "Newsletter, Download",
    "support": "Bug Report, Feature Request",
    "custom": "user_defined_categories"
  }
}
```

#### Status-Based Filtering
```json
{
  "status_filters": {
    "processing_status": ["pending", "processing", "completed", "failed"],
    "delivery_status": ["delivered", "failed", "retrying", "abandoned"],
    "system_status": ["healthy", "degraded", "critical"]
  }
}
```

### Advanced Segmentation Features
- **Saved Filter Sets**: Users can save complex filter combinations
- **Filter Persistence**: Maintain filters across page refreshes
- **Filter Sharing**: Share filtered views with team members
- **Smart Suggestions**: AI-powered filter recommendations based on patterns

## 4. Alerting & Notifications

### Alert Trigger Categories

#### Critical System Alerts
```json
{
  "system_down": {
    "trigger": "success_rate < 50% for 5 minutes",
    "severity": "critical",
    "escalation": "immediate",
    "channels": ["email", "sms", "slack", "webhook"]
  },
  "high_error_rate": {
    "trigger": "error_rate > 5% for 10 minutes",
    "severity": "high",
    "escalation": "5 minutes",
    "channels": ["email", "slack"]
  }
}
```

#### Performance Degradation
```json
{
  "slow_processing": {
    "trigger": "p95_latency > 5s for 15 minutes",
    "severity": "medium",
    "escalation": "15 minutes",
    "channels": ["email", "dashboard_notification"]
  },
  "throughput_drop": {
    "trigger": "submission_rate < 50% of baseline for 30 minutes",
    "severity": "medium",
    "escalation": "30 minutes",
    "channels": ["email"]
  }
}
```

#### Business Impact Alerts
```json
{
  "destination_failure": {
    "trigger": "destination_success_rate < 90% for 20 minutes",
    "severity": "high",
    "escalation": "10 minutes",
    "channels": ["email", "slack"]
  },
  "unusual_volume": {
    "trigger": "submission_volume > 200% of baseline OR < 20% of baseline",
    "severity": "low",
    "escalation": "none",
    "channels": ["dashboard_notification"]
  }
}
```

### Delivery Mechanisms

#### Multi-Channel Notification System
```json
{
  "channels": {
    "email": {
      "template": "html_rich",
      "batch_frequency": "immediate",
      "unsubscribe_option": true
    },
    "slack": {
      "integration": "webhook_url",
      "channel_mapping": "per_tenant",
      "threading": "alert_type"
    },
    "teams": {
      "integration": "webhook_url",
      "card_format": "adaptive_card",
      "action_buttons": true
    },
    "sms": {
      "provider": "aws_sns",
      "rate_limit": "1_per_hour",
      "critical_only": true
    },
    "webhook": {
      "custom_endpoints": true,
      "retry_policy": "exponential_backoff",
      "authentication": "api_key"
    }
  }
}
```

### Threshold Configuration System

#### Dynamic Baseline Calculation
```python
def calculate_dynamic_threshold(metric_name, time_window):
    """
    Calculate intelligent thresholds based on historical patterns
    """
    baseline = get_historical_average(metric_name, days=30)
    volatility = get_standard_deviation(metric_name, days=30)
    
    thresholds = {
        "warning": baseline - (2 * volatility),
        "critical": baseline - (3 * volatility),
        "upper_warning": baseline + (2 * volatility),
        "upper_critical": baseline + (3 * volatility)
    }
    
    return thresholds
```

#### User-Configurable Alerts
```json
{
  "alert_builder": {
    "metric_selection": "dropdown_with_search",
    "condition_operators": ["<", ">", "=", "!=", "% change"],
    "threshold_input": "numeric_with_units",
    "time_window": ["5m", "10m", "30m", "1h", "4h"],
    "severity_level": ["low", "medium", "high", "critical"],
    "notification_channels": "multi_select"
  }
}
```

### Alert Fatigue Prevention

#### Intelligent Alert Grouping
- **Similar Alerts**: Group related alerts within 10-minute windows
- **Root Cause Analysis**: Suppress downstream alerts when root cause is identified
- **Escalation Patterns**: Gradually increase severity rather than immediate critical alerts
- **Alert Correlation**: Link related system components in alert context

#### Snooze and Acknowledgment
```json
{
  "alert_management": {
    "snooze_options": ["15m", "1h", "4h", "24h", "until_resolved"],
    "acknowledgment": {
      "required_for": ["high", "critical"],
      "timeout": "4 hours",
      "escalation_on_timeout": true
    },
    "resolution_tracking": {
      "auto_resolve": "condition_cleared_for_5m",
      "manual_resolve": "with_required_comment"
    }
  }
}
```

## 5. Reporting & Export

### Standard Report Library

#### Executive Summary Report
```json
{
  "report_name": "Executive Dashboard",
  "frequency": "weekly",
  "sections": [
    {
      "title": "Key Performance Indicators",
      "widgets": ["success_rate_gauge", "volume_trend", "cost_metrics"]
    },
    {
      "title": "System Health",
      "widgets": ["uptime_summary", "error_rate_trend", "performance_metrics"]
    },
    {
      "title": "Business Impact",
      "widgets": ["top_performing_sites", "destination_analysis", "growth_metrics"]
    }
  ],
  "export_formats": ["pdf", "email"]
}
```

#### Technical Operations Report
```json
{
  "report_name": "Technical Operations",
  "frequency": "daily",
  "sections": [
    {
      "title": "System Performance",
      "data": ["response_times", "error_rates", "throughput_metrics"]
    },
    {
      "title": "Resource Utilization",
      "data": ["lambda_invocations", "dynamodb_consumption", "eventbridge_events"]
    },
    {
      "title": "Alerts and Incidents",
      "data": ["alert_summary", "resolution_times", "recurring_issues"]
    }
  ],
  "export_formats": ["csv", "json", "excel"]
}
```

#### Site Performance Analysis
```json
{
  "report_name": "Site Performance Analysis",
  "frequency": "monthly",
  "parameters": {
    "site_selection": "all_or_filtered",
    "comparison_period": "month_over_month",
    "include_benchmarks": true
  },
  "sections": [
    "submission_volume_trends",
    "success_rate_analysis",
    "processing_time_distribution",
    "destination_performance_breakdown",
    "cost_per_submission_analysis"
  ]
}
```

### Custom Report Builder

#### Visual Report Builder Interface
```json
{
  "report_builder": {
    "drag_drop_interface": true,
    "widget_library": [
      "charts", "tables", "metrics_cards", "heat_maps", "gauges"
    ],
    "data_sources": [
      "submissions", "processing_metrics", "destination_status", "system_health"
    ],
    "filter_builder": {
      "visual_filter_designer": true,
      "filter_preview": true,
      "saved_filters": true
    },
    "layout_options": [
      "single_page", "multi_page", "dashboard_style", "document_style"
    ]
  }
}
```

#### Advanced Analytics Features
```json
{
  "analytics_features": {
    "cohort_analysis": {
      "grouping": ["site", "form_type", "destination"],
      "metrics": ["retention", "success_rate", "volume_trends"],
      "time_periods": ["daily", "weekly", "monthly"]
    },
    "correlation_analysis": {
      "metrics_pairing": "any_two_metrics",
      "statistical_tests": ["pearson", "spearman"],
      "visualization": "scatter_plot_with_trend_line"
    },
    "forecasting": {
      "algorithms": ["linear_regression", "seasonal_arima"],
      "confidence_intervals": "95%",
      "forecast_horizon": "30_days"
    }
  }
}
```

### Export Formats and Options

#### File Format Support
```json
{
  "export_formats": {
    "pdf": {
      "use_cases": ["executive_reports", "presentations"],
      "customization": ["header_footer", "branding", "page_breaks"]
    },
    "excel": {
      "use_cases": ["detailed_analysis", "further_processing"],
      "features": ["multiple_sheets", "charts", "pivot_tables"]
    },
    "csv": {
      "use_cases": ["raw_data_export", "integration"],
      "options": ["delimiter_choice", "encoding", "headers"]
    },
    "json": {
      "use_cases": ["api_integration", "automated_processing"],
      "structure": ["flat", "nested", "time_series"]
    },
    "png_svg": {
      "use_cases": ["chart_export", "presentations"],
      "options": ["resolution", "transparent_background"]
    }
  }
}
```

### Scheduling System

#### Automated Report Delivery
```json
{
  "scheduling_options": {
    "frequencies": [
      "real_time", "hourly", "daily", "weekly", "monthly", "quarterly"
    ],
    "delivery_time": {
      "timezone_aware": true,
      "business_hours_only": false,
      "weekend_skip": "configurable"
    },
    "delivery_methods": [
      "email", "slack", "teams", "ftp", "s3_bucket", "webhook"
    ],
    "conditional_delivery": {
      "threshold_based": "only_send_if_anomaly_detected",
      "change_based": "only_send_if_significant_change"
    }
  }
}
```

## 6. Performance Requirements

### Dashboard Load Time Targets

#### Initial Page Load Performance
```json
{
  "performance_targets": {
    "first_contentful_paint": "< 800ms",
    "largest_contentful_paint": "< 1.2s",
    "time_to_interactive": "< 1.5s",
    "cumulative_layout_shift": "< 0.1"
  },
  "optimization_strategies": [
    "code_splitting",
    "lazy_loading_widgets",
    "cdn_asset_delivery",
    "compression_gzip_brotli"
  ]
}
```

#### Widget Refresh Performance
```json
{
  "widget_performance": {
    "real_time_widgets": "< 100ms update latency",
    "chart_rendering": "< 300ms for 1000+ data points",
    "table_pagination": "< 200ms per page",
    "filter_application": "< 500ms for complex filters"
  }
}
```

### Data Freshness Requirements

#### Tiered Data Freshness Strategy
```json
{
  "data_freshness_tiers": {
    "tier_1_critical": {
      "metrics": ["system_health", "active_alerts", "current_processing"],
      "freshness": "< 10 seconds",
      "implementation": "websocket_push"
    },
    "tier_2_operational": {
      "metrics": ["hourly_volumes", "success_rates", "recent_errors"],
      "freshness": "< 1 minute",
      "implementation": "polling_every_30s"
    },
    "tier_3_analytical": {
      "metrics": ["daily_summaries", "trends", "reports"],
      "freshness": "< 5 minutes",
      "implementation": "scheduled_aggregation"
    }
  }
}
```

### Query Optimization for DynamoDB Single-Table Design

#### Access Pattern Optimization
```python
# Primary metrics table structure
METRICS_TABLE_DESIGN = {
    "PK": "TENANT#{tenant_id}#METRIC#{metric_type}",
    "SK": "DATE#{date}#HOUR#{hour}#SITE#{site_id}",
    "GSI1_PK": "METRIC#{metric_type}#DATE#{date}",
    "GSI1_SK": "TENANT#{tenant_id}#SITE#{site_id}",
    "GSI2_PK": "TENANT#{tenant_id}#DATE#{date}",
    "GSI2_SK": "METRIC#{metric_type}#VALUE#{value}"
}

# Query patterns for dashboard widgets
OPTIMIZED_QUERIES = {
    "tenant_overview": {
        "pattern": "PK = TENANT#123#METRIC#SUMMARY",
        "filter": "SK begins_with DATE#2025-08-26",
        "performance": "< 50ms"
    },
    "site_drill_down": {
        "pattern": "GSI1_PK = METRIC#SUBMISSIONS#DATE#2025-08-26",
        "filter": "GSI1_SK begins_with TENANT#123#SITE#site123",
        "performance": "< 100ms"
    },
    "time_series_data": {
        "pattern": "PK = TENANT#123#METRIC#HOURLY_VOLUME",
        "sort": "SK between DATE#2025-08-20 and DATE#2025-08-26",
        "performance": "< 200ms for 7-day range"
    }
}
```

#### Caching Strategy
```json
{
  "caching_layers": {
    "browser_cache": {
      "static_assets": "1 year",
      "api_responses": "5 minutes",
      "user_preferences": "session"
    },
    "cloudfront_cache": {
      "dashboard_api": "1 minute",
      "static_reports": "1 hour",
      "real_time_data": "no_cache"
    },
    "application_cache": {
      "redis_cluster": {
        "aggregated_metrics": "5 minutes TTL",
        "frequently_accessed": "1 minute TTL",
        "user_sessions": "30 minutes TTL"
      }
    }
  }
}
```

### Scalability Architecture

#### Auto-Scaling Configuration
```json
{
  "lambda_functions": {
    "dashboard_api": {
      "provisioned_concurrency": 10,
      "max_concurrency": 100,
      "scaling_trigger": "cpu_utilization > 70%"
    },
    "metric_aggregation": {
      "reserved_concurrency": 50,
      "batch_size": 100,
      "scaling_trigger": "queue_depth > 1000"
    }
  },
  "dynamodb_tables": {
    "billing_mode": "ON_DEMAND",
    "auto_scaling": {
      "read_capacity": "10-4000 RCU",
      "write_capacity": "10-4000 WCU",
      "target_utilization": "70%"
    }
  }
}
```

This comprehensive dashboard analytics specification provides a robust framework for the Form-Bridge platform, balancing real-time performance requirements with cost-effective implementation using the EventBridge and DynamoDB architecture.