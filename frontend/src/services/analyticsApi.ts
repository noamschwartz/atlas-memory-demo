/**
 * Analytics API client - ES|QL powered search analytics.
 * 
 * Connects to the backend /api/analytics endpoints.
 * Provides metrics derived from OpenTelemetry trace data.
 */

// =============================================================================
// Types
// =============================================================================

/** Time range options for analytics queries */
export type TimeRange = '15m' | '1h' | '24h' | 'all';

/** Time range display labels */
export const TIME_RANGE_LABELS: Record<TimeRange, string> = {
  '15m': 'Last 15 minutes',
  '1h': 'Last 1 hour',
  '24h': 'Last 24 hours',
  'all': 'All time',
};

/** Click-through rate metrics */
export interface CTRMetrics {
  total_searches: number;
  total_clicks: number;
  ctr: number;
  time_range: string;
  esql_query?: string;
}

/** Mean Reciprocal Rank metrics */
export interface MRRMetrics {
  total_clicks: number;
  mrr: number;
  avg_click_position: number;
  time_range: string;
  esql_query?: string;
}

/** Zero results rate metrics */
export interface ZeroResultsMetrics {
  total_searches: number;
  zero_result_searches: number;
  zero_results_rate: number;
  time_range: string;
  esql_query?: string;
}

/** Combined analytics overview */
export interface AnalyticsOverview {
  ctr: CTRMetrics;
  mrr: MRRMetrics;
  zero_results: ZeroResultsMetrics;
  time_range: string;
}

/** Single top query entry */
export interface TopQuery {
  user_query: string;
  search_count: number;
  avg_result_count: number;
  had_clicks: number;
}

/** Top queries response */
export interface TopQueriesResponse {
  queries: TopQuery[];
  time_range: string;
}

/** Click position distribution entry */
export interface ClickPosition {
  position: number;
  clicks: number;
  percentage: number;
}

/** Click distribution response */
export interface ClickDistributionResponse {
  distribution: ClickPosition[];
  time_range: string;
}

/** Zero result query entry */
export interface ZeroResultQuery {
  user_query: string;
  occurrences: number;
}

/** Zero result queries response */
export interface ZeroResultQueriesResponse {
  queries: ZeroResultQuery[];
  time_range: string;
}

/** Analytics health status */
export interface AnalyticsHealth {
  status: 'healthy' | 'no_data' | 'not_configured' | 'error';
  has_data: boolean;
  trace_count: number;
  message: string;
  /** Whether monitoring cluster is configured */
  monitoring_configured?: boolean;
  /** Whether OTel tracing is configured */
  otel_configured?: boolean;
  /** Setup hint for troubleshooting */
  setup_hint?: string;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Check analytics data availability.
 */
export async function checkAnalyticsHealth(): Promise<AnalyticsHealth> {
  const response = await fetch(`/api/analytics/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get all key metrics in one call.
 * 
 * @param range - Time range (default: 24h)
 */
export async function getAnalyticsOverview(
  range: TimeRange = '24h'
): Promise<AnalyticsOverview> {
  const response = await fetch(`/api/analytics/overview?range=${range}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch overview' }));
    throw new Error(error.detail || `Overview failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get Click-Through Rate metrics.
 * 
 * @param range - Time range (default: 24h)
 */
export async function getCTR(range: TimeRange = '24h'): Promise<CTRMetrics> {
  const response = await fetch(`/api/analytics/ctr?range=${range}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch CTR' }));
    throw new Error(error.detail || `CTR failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get Mean Reciprocal Rank metrics.
 * 
 * @param range - Time range (default: 24h)
 */
export async function getMRR(range: TimeRange = '24h'): Promise<MRRMetrics> {
  const response = await fetch(`/api/analytics/mrr?range=${range}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch MRR' }));
    throw new Error(error.detail || `MRR failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get zero results rate metrics.
 * 
 * @param range - Time range (default: 24h)
 */
export async function getZeroResultsRate(
  range: TimeRange = '24h'
): Promise<ZeroResultsMetrics> {
  const response = await fetch(`/api/analytics/zero-results?range=${range}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch zero results' }));
    throw new Error(error.detail || `Zero results failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get top queries by volume.
 * 
 * @param range - Time range (default: 24h)
 * @param limit - Number of queries to return (default: 20)
 */
export async function getTopQueries(
  range: TimeRange = '24h',
  limit: number = 20
): Promise<TopQueriesResponse> {
  const params = new URLSearchParams({
    range,
    limit: String(limit),
  });
  
  const response = await fetch(`/api/analytics/top-queries?${params}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch top queries' }));
    throw new Error(error.detail || `Top queries failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get click position distribution.
 * 
 * @param range - Time range (default: 24h)
 * @param limit - Number of positions to return (default: 10)
 */
export async function getClickDistribution(
  range: TimeRange = '24h',
  limit: number = 10
): Promise<ClickDistributionResponse> {
  const params = new URLSearchParams({
    range,
    limit: String(limit),
  });
  
  const response = await fetch(`/api/analytics/click-distribution?${params}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch click distribution' }));
    throw new Error(error.detail || `Click distribution failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get queries that returned zero results.
 * 
 * @param range - Time range (default: 24h)
 * @param limit - Number of queries to return (default: 20)
 */
export async function getZeroResultQueries(
  range: TimeRange = '24h',
  limit: number = 20
): Promise<ZeroResultQueriesResponse> {
  const params = new URLSearchParams({
    range,
    limit: String(limit),
  });
  
  const response = await fetch(`/api/analytics/zero-result-queries?${params}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch zero result queries' }));
    throw new Error(error.detail || `Zero result queries failed: ${response.status}`);
  }
  return response.json();
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Format CTR as a percentage string.
 */
export function formatCTR(ctr: number): string {
  return `${ctr.toFixed(1)}%`;
}

/**
 * Format MRR with interpretation.
 * 
 * @returns Object with value and interpretation
 */
export function formatMRR(mrr: number): { value: string; interpretation: string } {
  const value = mrr.toFixed(3);
  
  let interpretation: string;
  if (mrr >= 0.9) {
    interpretation = 'Excellent - most clicks on position 1';
  } else if (mrr >= 0.7) {
    interpretation = 'Good - clicks mostly in top 2';
  } else if (mrr >= 0.5) {
    interpretation = 'Average - clicks around position 2';
  } else if (mrr >= 0.33) {
    interpretation = 'Below average - clicks around position 3';
  } else if (mrr > 0) {
    interpretation = 'Poor - clicks far down in results';
  } else {
    interpretation = 'No click data';
  }
  
  return { value, interpretation };
}

/**
 * Calculate CTR from a top query entry.
 */
export function calculateQueryCTR(query: TopQuery): number {
  if (query.search_count === 0) return 0;
  return (query.had_clicks / query.search_count) * 100;
}

/**
 * Get color status based on CTR value.
 */
export function getCTRStatus(ctr: number): 'success' | 'warning' | 'danger' | 'subdued' {
  if (ctr >= 30) return 'success';
  if (ctr >= 15) return 'warning';
  if (ctr > 0) return 'danger';
  return 'subdued';
}

/**
 * Get color status based on zero results rate.
 */
export function getZeroResultsStatus(rate: number): 'success' | 'warning' | 'danger' | 'subdued' {
  if (rate === 0) return 'subdued';
  if (rate <= 5) return 'success';
  if (rate <= 15) return 'warning';
  return 'danger';
}

// =============================================================================
// Query-Specific Judgment Lists
// =============================================================================

/** Document in a query judgment list */
export interface QueryJudgmentDocument {
  doc_id: string;
  title?: string;
  brand?: string;
  image_url?: string;
  clicks: number;
  avg_position: number;
  min_position: number;
  max_position: number;
  grade: number;  // 0-4
}

/** Query judgments response */
export interface QueryJudgmentsResponse {
  query: string;
  time_range: string;
  total_clicks: number;
  documents: QueryJudgmentDocument[];
}

/** Query with click data (for picker) */
export interface QueryWithClicks {
  query: string;
  click_count: number;
  unique_docs: number;
}

/** Queries with clicks response */
export interface QueriesWithClicksResponse {
  queries: QueryWithClicks[];
  time_range: string;
}

/**
 * Get queries that have click data (for the query picker).
 */
export async function getQueriesWithClicks(
  range: TimeRange = '24h',
  limit: number = 20
): Promise<QueriesWithClicksResponse> {
  const params = new URLSearchParams({
    range,
    limit: String(limit),
  });
  
  const url = `/api/analytics/queries-with-clicks?${params}`;
  console.log('[analyticsApi] Fetching queries with clicks:', url);
  
  const response = await fetch(url);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch queries' }));
    console.error('[analyticsApi] Failed to fetch queries:', response.status, error);
    throw new Error(error.detail || `Queries with clicks failed: ${response.status}`);
  }
  
  const data = await response.json();
  console.log('[analyticsApi] Received queries:', data);
  return data;
}

/**
 * Get query-specific judgment list for LTR training.
 */
export async function getQueryJudgments(
  query: string,
  range: TimeRange = '24h',
  enrich: boolean = true
): Promise<QueryJudgmentsResponse> {
  const params = new URLSearchParams({
    query,
    range,
    enrich: String(enrich),
  });
  
  const url = `/api/analytics/query-judgments?${params}`;
  console.log('[analyticsApi] Fetching query judgments:', url);
  
  const response = await fetch(url);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch judgments' }));
    console.error('[analyticsApi] Failed to fetch judgments:', response.status, error);
    throw new Error(error.detail || `Query judgments failed: ${response.status}`);
  }
  
  const data = await response.json();
  console.log('[analyticsApi] Received judgments:', data);
  return data;
}

/**
 * Get grade label for display.
 */
export function getGradeLabel(grade: number): string {
  switch (grade) {
    case 4: return 'Excellent';
    case 3: return 'Good';
    case 2: return 'Average';
    case 1: return 'Below Avg';
    case 0: return 'Poor';
    default: return 'Unknown';
  }
}

/**
 * Get grade color for EUI badges.
 */
export function getGradeColor(grade: number): string {
  switch (grade) {
    case 4: return 'success';
    case 3: return 'primary';
    case 2: return 'default';
    case 1: return 'warning';
    case 0: return 'danger';
    default: return 'default';
  }
}

