# FEAT-022: Performance Monitoring Dashboard

## TODO Reference
- TODO.md: "Performance monitoring dashboard"
  - Real-time metrics visualization
  - Alerting for performance degradation
  - Capacity planning tools

## Objective
Create a comprehensive performance monitoring dashboard that provides real-time metrics visualization, automated alerting, and capacity planning capabilities.

## Current State
Strong foundation already exists:
- `src/monitoring/metrics_collector.py` - Collects metrics and stores in SQLite
- `src/monitoring/alert_engine.py` - Alert evaluation and threshold management
- `src/monitoring/health_reporter.py` - Health scoring and trend analysis
- `src/cli/health_dashboard_command.py` - Rich CLI dashboard for health metrics
- `src/cli/analytics_command.py` - Token usage analytics

**What's Missing:**
1. MCP tools to expose monitoring capabilities to Claude
2. Capacity planning module for predictive analytics
3. Integration layer to tie all monitoring components together
4. Real-time monitoring capabilities (not just point-in-time snapshots)

## Implementation Plan

### Phase 1: Capacity Planning Module (NEW)
Create `src/monitoring/capacity_planner.py` with:
- [ ] Database size forecasting (project to N days out)
- [ ] Memory capacity prediction (when will we hit limits)
- [ ] Project capacity analysis (how many more projects can be indexed)
- [ ] Resource usage projections (disk, memory, compute)
- [ ] Recommendations for scaling/optimization

**Key Classes:**
```python
class CapacityPlanner:
    def __init__(self, metrics_collector: MetricsCollector)

    async def forecast_database_growth(self, days_ahead: int = 30) -> DatabaseGrowthForecast
    async def analyze_memory_capacity(self) -> MemoryCapacityAnalysis
    async def calculate_project_capacity(self) -> ProjectCapacityReport
    async def get_capacity_recommendations(self) -> List[CapacityRecommendation]
```

### Phase 2: MCP Tool Integration
Add MCP tools in `src/mcp_server.py`:
- [ ] `get_performance_metrics` - Get current performance snapshot
- [ ] `get_active_alerts` - Get active alerts with recommendations
- [ ] `get_health_score` - Get overall health score and breakdown
- [ ] `get_capacity_forecast` - Get capacity planning forecast
- [ ] `resolve_alert` - Mark an alert as resolved
- [ ] `get_weekly_report` - Get comprehensive weekly health report

**Models** (add to `src/core/models.py`):
```python
class GetPerformanceMetricsRequest(BaseModel)
class GetPerformanceMetricsResponse(BaseModel)
class GetActiveAlertsRequest(BaseModel)
class GetActiveAlertsResponse(BaseModel)
class GetHealthScoreRequest(BaseModel)
class GetHealthScoreResponse(BaseModel)
class GetCapacityForecastRequest(BaseModel)
class GetCapacityForecastResponse(BaseModel)
class ResolveAlertRequest(BaseModel)
class ResolveAlertResponse(BaseModel)
class GetWeeklyReportRequest(BaseModel)
class GetWeeklyReportResponse(BaseModel)
```

### Phase 3: Server Integration
Integrate monitoring into `src/core/server.py`:
- [ ] Initialize MetricsCollector on startup
- [ ] Initialize AlertEngine on startup
- [ ] Initialize HealthReporter on startup
- [ ] Initialize CapacityPlanner on startup
- [ ] Add background task to collect metrics periodically (every 5 minutes)
- [ ] Add background task to evaluate alerts periodically (every 5 minutes)
- [ ] Store collector, alert engine, and reporter as server instance variables

### Phase 4: CLI Enhancement (Optional)
Add CLI command for monitoring:
- [ ] `src/cli/monitor_command.py` - Live monitoring dashboard
- [ ] Update `src/cli/__init__.py` to register monitor command

**Features:**
- Live updating dashboard (refreshes every 30 seconds)
- Shows current metrics, active alerts, health score
- Shows capacity forecast
- Color-coded warnings/alerts

## Design Decisions

### 1. Capacity Planning Algorithm
Use linear regression on historical metrics to forecast:
- Database growth rate (MB/day)
- Memory creation rate (memories/day)
- Query volume growth (queries/day)
- Project addition rate (projects/week)

**Thresholds for recommendations:**
- Database: Warn if projected to exceed 2GB in 30 days
- Memories: Warn if projected to exceed 50k in 30 days
- Projects: Warn if projected to exceed 20 active in 30 days

### 2. Metrics Collection Frequency
- Background collection: Every 5 minutes
- Alert evaluation: Every 5 minutes (after metrics collection)
- Metrics retention: 90 days (configurable)
- Alert retention: 90 days for resolved alerts

### 3. MCP Tool Design
Keep tools simple and focused:
- Each tool does ONE thing well
- Provide both summary and detailed views
- Include actionable recommendations in responses
- Format output for easy human reading (Rich formatting where appropriate)

### 4. Real-Time Monitoring
Don't implement WebSocket or streaming:
- MCP is request/response based
- Claude can poll for updates if needed
- CLI dashboard can use Rich Live display for updates
- Background collection provides "near real-time" data (5-minute granularity)

## Implementation Steps

### Step 1: Create Capacity Planner (Est: 2 hours)
1. Create `src/monitoring/capacity_planner.py`
2. Implement database growth forecasting
3. Implement memory capacity analysis
4. Implement project capacity calculations
5. Add recommendation generation

### Step 2: Add Pydantic Models (Est: 1 hour)
1. Add request/response models to `src/core/models.py`
2. Use proper Field descriptions for Claude
3. Include example values in docstrings

### Step 3: Integrate into Server (Est: 2 hours)
1. Initialize monitoring components in `src/core/server.py`
2. Add background collection task
3. Add background alert evaluation task
4. Add MCP tool methods to server
5. Wire up metrics collection to search operations

### Step 4: Register MCP Tools (Est: 1 hour)
1. Add tool definitions to `src/mcp_server.py`
2. Add tool handlers with proper formatting
3. Test tool invocation

### Step 5: Testing (Est: 2 hours)
1. Create `tests/unit/test_capacity_planner.py`
2. Create `tests/unit/test_monitoring_integration.py`
3. Test MCP tools
4. Test background tasks

### Step 6: Documentation (Est: 1 hour)
1. Update `docs/API.md` with new tools
2. Update `CHANGELOG.md`
3. Update `CLAUDE.md` metrics if needed

## Test Cases

### Capacity Planner Tests
- [x] Test database growth forecasting with linear trend
- [x] Test database growth with no historical data
- [x] Test memory capacity analysis
- [x] Test project capacity calculation
- [x] Test capacity recommendations generation
- [x] Test edge cases (zero growth, negative growth)

### Integration Tests
- [x] Test metrics collection integration
- [x] Test alert evaluation integration
- [x] Test MCP tool responses
- [x] Test background task execution
- [x] Test metrics storage and retrieval

### MCP Tool Tests
- [x] Test get_performance_metrics
- [x] Test get_active_alerts
- [x] Test get_health_score
- [x] Test get_capacity_forecast
- [x] Test resolve_alert
- [x] Test get_weekly_report

## Progress Tracking

- [x] Created CapacityPlanner class
- [x] Implemented database growth forecasting
- [x] Implemented memory capacity analysis
- [x] Implemented project capacity calculation
- [x] Added Pydantic models to server
- [x] Integrated monitoring into server initialization
- [ ] Added background collection task (DEFERRED - can be added later)
- [x] Added MCP tools to server (6 methods added)
- [ ] Registered MCP tools in mcp_server.py (REMAINING)
- [ ] Created comprehensive tests (REMAINING)
- [ ] Updated documentation (REMAINING)

## Notes & Decisions

### Decision: Use SQLite for Metrics Storage
- Pros: Simple, no external dependencies, good enough performance
- Cons: Not ideal for very high-frequency metrics
- Decision: Use SQLite with 5-minute collection frequency

### Decision: Linear Regression for Forecasting
- Pros: Simple, explainable, fast
- Cons: Doesn't handle seasonality or non-linear growth
- Decision: Use simple linear regression for MVP, can enhance later

### Decision: 5-Minute Collection Frequency
- Pros: Low overhead, sufficient granularity
- Cons: Not "real-time"
- Decision: 5 minutes is good balance for now

### Decision: No Streaming/WebSocket
- Pros: Keeps implementation simple, MCP doesn't support streaming
- Cons: Claude can't get instant updates
- Decision: Poll-based approach is sufficient

## Code Snippets

### Example Capacity Forecast Response
```python
{
    "forecast_days": 30,
    "database_growth": {
        "current_size_mb": 245.3,
        "projected_size_mb": 312.7,
        "growth_rate_mb_per_day": 2.24,
        "days_until_limit": 731,  # Days until 2GB limit
        "status": "HEALTHY"
    },
    "memory_capacity": {
        "current_memories": 12453,
        "projected_memories": 15234,
        "creation_rate_per_day": 92.7,
        "days_until_limit": 405,  # Days until 50k limit
        "status": "HEALTHY"
    },
    "recommendations": [
        "Database growth is steady - no action needed",
        "Consider archiving projects older than 180 days to optimize"
    ]
}
```

### Example Health Score Response
```python
{
    "overall_score": 87,
    "status": "GOOD",
    "performance_score": 92,
    "quality_score": 85,
    "database_health_score": 88,
    "usage_efficiency_score": 79,
    "total_alerts": 2,
    "critical_alerts": 0,
    "warning_alerts": 2
}
```

## Completion Criteria
- [ ] All tests passing (aim for >85% coverage on new code)
- [ ] MCP tools callable from Claude
- [ ] Background tasks running without errors
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Code committed following CLAUDE.md protocol

## Estimated Time
- Total: ~9 hours
- Capacity Planner: 2 hours
- Models: 1 hour
- Server Integration: 2 hours
- MCP Tools: 1 hour
- Testing: 2 hours
- Documentation: 1 hour

## Completion Summary

**Status:** ⚠️ Core Implementation Complete (MCP Integration Pending)
**Date:** 2025-11-18
**Implementation Time:** ~3 hours (core foundation)

### What Was Built

**1. Capacity Planning Module** (`src/monitoring/capacity_planner.py`)
   - Linear regression-based forecasting for database growth, memory capacity, and project count
   - Predictive analytics with WARNING/CRITICAL status thresholds
   - Actionable recommendations for capacity management
   - ~600 lines of production code

**2. Pydantic Models** (`src/core/models.py`)
   - 15 new models for monitoring MCP tools
   - Request/response schemas for all 6 tools
   - Comprehensive field descriptions for Claude

**3. Server Integration** (`src/core/server.py`)
   - Initialized MetricsCollector, AlertEngine, HealthReporter, CapacityPlanner
   - 6 async MCP tool methods:
     - `get_performance_metrics()` - Current performance snapshot
     - `get_active_alerts()` - System alerts with recommendations
     - `get_health_score()` - Overall health with component breakdown
     - `get_capacity_forecast()` - Capacity planning predictions
     - `resolve_alert()` - Mark alerts as resolved
     - `get_weekly_report()` - Comprehensive weekly health report
   - ~290 lines of new server code

### What's Remaining

**Critical (Required for Functionality):**
1. **MCP Tool Registration** (`src/mcp_server.py`)
   - Add 6 tool definitions to tools list
   - Add 6 handlers in call_tool method
   - Estimated: 1 hour

**Important (Required for Quality):**
2. **Comprehensive Tests** (`tests/unit/test_capacity_planner.py`, `tests/unit/test_monitoring_integration.py`)
   - Test CapacityPlanner forecasting logic
   - Test server MCP tool methods
   - Test edge cases and error handling
   - Estimated: 2 hours

3. **Documentation Updates**
   - Update `docs/API.md` with 6 new tools
   - Update `CHANGELOG.md` with FEAT-022 entry
   - Estimated: 30 minutes

### Technical Decisions

1. **No Background Collection Task**: Deferred periodic metrics collection to keep implementation focused. Can be added later as enhancement.
2. **Linear Regression**: Used simple linear regression for forecasting - sufficient for MVP, can enhance with more sophisticated models later.
3. **Monitoring DB Path**: Stored monitoring.db in same directory as sqlite memory.db for logical grouping.

### Files Changed

**Created:**
- `src/monitoring/capacity_planner.py` (600 lines)
- `planning_docs/FEAT-022_performance_monitoring_dashboard.md`

**Modified:**
- `src/core/models.py` (+235 lines - 15 new models)
- `src/core/server.py` (+295 lines - initialization + 6 methods)

### Next Steps

1. Register MCP tools in `src/mcp_server.py` (CRITICAL)
2. Create comprehensive tests (IMPORTANT)
3. Update documentation (IMPORTANT)
4. Consider background collection task for automatic metrics gathering (ENHANCEMENT)
5. Consider CLI command for live monitoring dashboard (ENHANCEMENT)
