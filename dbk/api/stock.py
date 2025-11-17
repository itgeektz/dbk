import frappe
from frappe.utils import nowdate, nowtime
from erpnext.stock.stock_ledger import get_previous_sle


def _get_bin_qty(item_code, warehouse):
    """Return actual_qty from Bin table (fast)."""
    return (
        frappe.db.get_value(
            "Bin",
            {"item_code": item_code, "warehouse": warehouse},
            "actual_qty"
        )
        or 0
    )


def _get_sle_qty(item_code, warehouse):
    """Return qty using SLE."""
    sle = get_previous_sle({
        "item_code": item_code,
        "warehouse": warehouse,
        "posting_date": nowdate(),
        "posting_time": nowtime(),
    })

    return sle.get("qty_after_transaction", 0) if sle else 0


@frappe.whitelist()
def get_actual_qty(item_code, warehouse, method="bin"):
    """Public API: returns ONLY a number."""
    if not item_code or not warehouse:
        frappe.throw("Item Code and Warehouse are required.")

    if method == "sle":
        qty = _get_sle_qty(item_code, warehouse)
    else:
        qty = _get_bin_qty(item_code, warehouse)

    return qty
