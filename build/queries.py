"""SQL for the KK Rakhi SKU tracker.

Uses the validated item-level `price_share` revenue pipeline (see
Curefoods memory `feedback_sku_revenue_formula`): reconstructs each
order_item's true listing price (unit_price + variant/addon option
prices), prorates the order's discount/charges across items by that
weight, and excludes Cancelled/Rejected/customer_cancelled orders via
`orders_state_transitions` (joined on order_id, single-brand query so
no brand_id collision risk).
"""

BRAND_ID = 95469015  # Krispy Kreme (incl. NCR sub-brand)

# Exact substrings, matched via ILIKE — verified 2026-08-27 against
# menu_items that all 6 exist on the KK menu under these exact names.
# Deliberately does NOT match decoy items on the same menu, e.g.
# "Rakhi Delight Donut Hamper", "Rakhi Lovebox Trio Donut Hamper",
# "Rakhi Half Dozen Box Sleeve" (an offline packaging line, not a SKU).
SKUS = [
    "Rakhi Special Gift Hamper",
    "Rakhi Special Doughnut Box of 3",
    "Rakhi Special Doughnut Box of 6",
    "Rakhi Sunshine Doughnut",
    "Choco Caramel Luxe Doughnut",
    "Nutty Stars Doughnut",
]


def build_sku_query(date_ist):
    sku_clause = " OR ".join(f"r.item_name ILIKE '%{s}%'" for s in SKUS)
    return f"""
WITH
filtered_orders AS (
    SELECT id AS order_id, channel, city,
           sub_total_amount, discount, aggregator_discount, charges
    FROM orders
    WHERE brand_id = {BRAND_ID}
      AND toDate(created_at_ist) = '{date_ist}'
),
filtered_order_items AS (
    SELECT oi.order_id, oi.id AS oi_id, oi.order_item_seq_id, oi.item_name,
           oi.unit_price, oi.quantity
    FROM order_items oi
    INNER JOIN filtered_orders fo ON fo.order_id = oi.order_id
    WHERE oi.brand_id = {BRAND_ID}
),
opts AS (
    SELECT io.order_id, io.item_id, io.order_item_seq_id, sum(io.option_price) AS opt_price
    FROM item_options io
    WHERE io.brand_id = {BRAND_ID}
    GROUP BY io.order_id, io.item_id, io.order_item_seq_id
),
base_data AS (
    SELECT foi.order_id, foi.item_name, foi.quantity,
           (foi.unit_price + COALESCE(o.opt_price, 0)) AS item_price
    FROM filtered_order_items foi
    LEFT JOIN opts o
        ON o.order_id = foi.order_id AND o.item_id = foi.oi_id AND o.order_item_seq_id = foi.order_item_seq_id
),
resolved AS (
    SELECT bd.order_id, bd.item_name, bd.quantity,
           (bd.item_price * bd.quantity) / SUM(bd.item_price * bd.quantity) OVER (PARTITION BY bd.order_id) AS price_share,
           fo.sub_total_amount, fo.discount, fo.aggregator_discount, fo.charges,
           fo.channel, fo.city
    FROM base_data bd
    INNER JOIN filtered_orders fo ON fo.order_id = bd.order_id
),
latest_state AS (
    SELECT order_id, argMax(to_status, status_changed_at_ist) AS final_status
    FROM orders_state_transitions
    WHERE brand_id = {BRAND_ID}
    GROUP BY order_id
)
SELECT
    r.item_name AS item_name,
    r.channel AS channel,
    r.city AS city,
    sum(r.quantity) AS qty,
    sum(r.price_share * (r.sub_total_amount - (r.discount - r.aggregator_discount) + r.charges)) AS revenue
FROM resolved r
LEFT JOIN latest_state ls ON ls.order_id = r.order_id
WHERE (ls.final_status IS NULL OR ls.final_status NOT IN ('Cancelled','Rejected','customer_cancelled'))
  AND ({sku_clause})
GROUP BY r.item_name, r.channel, r.city
FORMAT TabSeparatedWithNames
"""


def build_total_revenue_query(date_ist):
    """Whole-brand order-level revenue (ALL items, not just the 6 Rakhi
    SKUs) per channel/city, for today. Denominator for the "share of the
    day's total revenue" table — order-level, no item_options explosion
    needed since nothing here is being split across items."""
    return f"""
WITH
filtered_orders AS (
    SELECT id AS order_id, channel, city,
           sub_total_amount, discount, aggregator_discount, charges
    FROM orders
    WHERE brand_id = {BRAND_ID}
      AND toDate(created_at_ist) = '{date_ist}'
),
latest_state AS (
    SELECT order_id, argMax(to_status, status_changed_at_ist) AS final_status
    FROM orders_state_transitions
    WHERE brand_id = {BRAND_ID}
    GROUP BY order_id
)
SELECT
    fo.channel AS channel,
    fo.city AS city,
    sum(fo.sub_total_amount - (fo.discount - fo.aggregator_discount) + fo.charges) AS revenue
FROM filtered_orders fo
LEFT JOIN latest_state ls ON ls.order_id = fo.order_id
WHERE (ls.final_status IS NULL OR ls.final_status NOT IN ('Cancelled','Rejected','customer_cancelled'))
GROUP BY fo.channel, fo.city
FORMAT TabSeparatedWithNames
"""
