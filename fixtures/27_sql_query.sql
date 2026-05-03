-- Token Count Compare: example analytical SQL.
-- Not intended to run; representative of common analyst workloads
-- with CTEs, window functions, joins, and a few light gotchas.

-- Daily token usage and cost by model and tier, last 30 days.

WITH base AS (
    SELECT
        request_id,
        user_id,
        model_id,
        provider,
        DATE_TRUNC('day', created_at) AS request_day,
        input_tokens,
        output_tokens,
        input_tokens + output_tokens AS total_tokens,
        status_code,
        duration_ms
    FROM analytics.api_requests
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
      AND status_code BETWEEN 200 AND 299
      AND model_id IN ('claude-opus-4-7', 'gpt-5.5')
),
priced AS (
    SELECT
        b.*,
        p.input_price_per_million_usd  AS input_rate,
        p.output_price_per_million_usd AS output_rate,
        (b.input_tokens  / 1e6) * p.input_price_per_million_usd  AS input_cost_usd,
        (b.output_tokens / 1e6) * p.output_price_per_million_usd AS output_cost_usd
    FROM base AS b
    LEFT JOIN billing.model_prices AS p
      ON p.model_id = b.model_id
     AND b.created_at >= p.effective_from
     AND b.created_at <  COALESCE(p.effective_until, '9999-12-31'::timestamptz)
),
ranked AS (
    SELECT
        p.*,
        NTILE(4) OVER (
            PARTITION BY p.model_id
            ORDER BY p.input_tokens
        ) AS input_quartile,
        ROW_NUMBER() OVER (
            PARTITION BY p.user_id, p.request_day
            ORDER BY p.created_at DESC
        ) AS rn_within_day,
        SUM(p.input_tokens) OVER (
            PARTITION BY p.user_id
            ORDER BY p.created_at
            ROWS BETWEEN 99 PRECEDING AND CURRENT ROW
        ) AS rolling_100_input_tokens
    FROM priced AS p
)
SELECT
    request_day,
    model_id,
    CASE
        WHEN input_tokens < 300                    THEN 'probe'
        WHEN input_tokens BETWEEN 300 AND 3999     THEN 'signal'
        WHEN input_tokens >= 4000                  THEN 'scaling'
        ELSE 'unknown'
    END AS size_tier,
    COUNT(*)                              AS request_count,
    SUM(input_tokens)                     AS input_tokens_total,
    SUM(output_tokens)                    AS output_tokens_total,
    AVG(input_tokens)::numeric(12,2)      AS input_tokens_avg,
    PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY input_tokens) AS input_tokens_p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY input_tokens) AS input_tokens_p95,
    SUM(input_cost_usd  + output_cost_usd)::numeric(12,4) AS cost_usd
FROM ranked
WHERE rolling_100_input_tokens IS NOT NULL
GROUP BY request_day, model_id, size_tier
HAVING COUNT(*) >= 10
ORDER BY request_day DESC, model_id ASC, size_tier ASC
LIMIT 500;

-- Top users by token spend over the same 30-day window.
SELECT
    u.user_id,
    u.email,
    SUM(r.input_tokens)  AS input_tokens_total,
    SUM(r.output_tokens) AS output_tokens_total,
    SUM(r.input_tokens) + SUM(r.output_tokens) AS total_tokens,
    SUM(
        (r.input_tokens  / 1e6) * COALESCE(p.input_price_per_million_usd,  0) +
        (r.output_tokens / 1e6) * COALESCE(p.output_price_per_million_usd, 0)
    )::numeric(12,4) AS total_cost_usd
FROM analytics.api_requests AS r
INNER JOIN identity.users AS u
       ON u.user_id = r.user_id
LEFT  JOIN billing.model_prices AS p
       ON p.model_id = r.model_id
      AND r.created_at >= p.effective_from
      AND r.created_at <  COALESCE(p.effective_until, '9999-12-31'::timestamptz)
WHERE r.created_at >= CURRENT_DATE - INTERVAL '30 days'
  AND r.status_code BETWEEN 200 AND 299
GROUP BY u.user_id, u.email
ORDER BY total_cost_usd DESC NULLS LAST
LIMIT 25;

-- Sanity check: sessions where reported usage diverges from count_tokens.
-- Use a small tolerance to avoid noise from off-by-one differences.
SELECT
    r.request_id,
    r.created_at,
    r.model_id,
    r.input_tokens                     AS reported_input_tokens,
    c.counted_input_tokens             AS counted_input_tokens,
    r.input_tokens - c.counted_input_tokens AS delta
FROM analytics.api_requests AS r
INNER JOIN analytics.count_tokens_calls AS c
       ON c.request_id = r.request_id
WHERE r.created_at >= CURRENT_DATE - INTERVAL '7 days'
  AND ABS(r.input_tokens - c.counted_input_tokens) > 2
ORDER BY ABS(r.input_tokens - c.counted_input_tokens) DESC
LIMIT 100;
