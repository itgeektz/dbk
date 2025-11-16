import frappe
from erpnext.stock.stock_ledger import get_previous_sle


def _get_sle_qty(item_code, warehouse, posting_date, posting_time):
    sle = get_previous_sle(
        {
            "item_code": item_code,
            "warehouse": warehouse,
            "posting_date": posting_date,
            "posting_time": posting_time,
            "sle": None,
        }
    )
    return sle.get("qty_after_transaction", 0) if sle else 0


@frappe.whitelist()
def get_actual_qty(item_code, warehouse):
    """
    Get actual qty (qty_after_transaction) for item & warehouse.
    Handles group warehouses (summing children).
    """

    if not warehouse:
        return 0

    # Check if group
    is_group = frappe.db.get_value("Warehouse", warehouse, "is_group")

    today = frappe.utils.today()
    now_time = frappe.utils.nowtime()

    # Not group → direct qty
    if not is_group:
        return _get_sle_qty(item_code, warehouse, today, now_time)

    # Group warehouse → sum child warehouses
    wh = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"], as_dict=True)

    child_warehouses = frappe.db.get_all(
        "Warehouse",
        filters={
            "lft": (">", wh.lft),
            "rgt": ("<", wh.rgt),
            "is_group": 0,
        },
        pluck="name"
    )

    total = 0
    for wh_name in child_warehouses:
        total += _get_sle_qty(item_code, wh_name, today, now_time)

    return total
