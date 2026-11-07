-- Atomically fail an unpaid order and restore its reserved stock once.

CREATE OR REPLACE FUNCTION public.fail_unpaid_order_and_restore_stock(
    p_order_id uuid
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_status text;
    v_item_count bigint;
    v_product_count bigint;
    v_updated_count bigint;
BEGIN
    -- Serialize attempts to process the same order.
    SELECT status
    INTO v_status
    FROM public.orders
    WHERE id = p_order_id
    FOR UPDATE;

    -- Missing or already processed orders cannot restore stock again.
    IF NOT FOUND OR v_status <> 'pending' THEN
        RETURN false;
    END IF;

    -- Require at least one valid order item.
    SELECT COUNT(*), COUNT(DISTINCT product_id)
    INTO v_item_count, v_product_count
    FROM public.order_items
    WHERE order_id = p_order_id;

    IF v_item_count = 0 THEN
        RAISE EXCEPTION 'Cannot fail order %: no order items found', p_order_id;
    END IF;

    -- Refuse to proceed if any item cannot be restored safely.
    IF EXISTS (
        SELECT 1
        FROM public.order_items AS oi
        LEFT JOIN public.products AS p ON p.id = oi.product_id
        WHERE oi.order_id = p_order_id
          AND (
              oi.product_id IS NULL
              OR oi.quantity IS NULL
              OR oi.quantity <= 0
              OR p.id IS NULL
              OR p.stock IS NULL
          )
    ) THEN
        RAISE EXCEPTION
            'Cannot restore stock for order %: invalid item or missing product',
            p_order_id;
    END IF;

    -- Restore stock, aggregating repeated product lines.
    UPDATE public.products AS p
    SET stock = p.stock + item_totals.total_quantity
    FROM (
        SELECT
            product_id,
            SUM(quantity)::integer AS total_quantity
        FROM public.order_items
        WHERE order_id = p_order_id
        GROUP BY product_id
    ) AS item_totals
    WHERE p.id = item_totals.product_id;

    GET DIAGNOSTICS v_updated_count = ROW_COUNT;

    -- Any incomplete restoration must roll back the entire function.
    IF v_updated_count <> v_product_count THEN
        RAISE EXCEPTION
            'Stock restoration incomplete for order %: expected %, updated %',
            p_order_id, v_product_count, v_updated_count;
    END IF;

    -- Change status only after stock restoration succeeds.
    UPDATE public.orders
    SET status = 'payment_failed'
    WHERE id = p_order_id;

    RETURN true;
END;
$$;

-- Restrict execution to the backend service role.
REVOKE ALL ON FUNCTION public.fail_unpaid_order_and_restore_stock(uuid)
FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.fail_unpaid_order_and_restore_stock(uuid)
TO service_role;
