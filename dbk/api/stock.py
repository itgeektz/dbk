# apps/dbk/dbk/api/stock.py
import frappe
from frappe.utils import flt

def _get_child_warehouses(parent_warehouse):
    """Return all leaf warehouses under a warehouse group, including itself if not group."""
    if not parent_warehouse:
        return []

    # Get warehouse doc (will raise if not exists)
    wh = frappe.get_doc("Warehouse", parent_warehouse)

    # if leaf
    if wh.is_group == 0:
        return [parent_warehouse]

    # if group -> get all leaf children beneath it (non-group)
    children = frappe.get_all(
        "Warehouse",
        filters={"lft": (">", wh.lft), "rgt": ("<", wh.rgt), "is_group": 0},
        pluck="name",
    )
    return children or []


def _get_bin_qty(item_code, warehouse):
    """
    Sum actual_qty across the warehouse (leaf) or all leaf children of a group warehouse.
    Returns float.
    """
    if not item_code or not warehouse:
        return 0.0

    wh_list = _get_child_warehouses(warehouse)
    if not wh_list:
        return 0.0

    # Use get_all to compute sum
    res = frappe.db.get_all(
        "Bin",
        filters={"item_code": item_code, "warehouse": ("in", wh_list)},
        fields=["sum(actual_qty) as qty"],
    )

    # res[0].qty may be None
    return flt(res[0].qty or 0.0)


# ---------------------------
# Whitelisted APIs for JS
# ---------------------------
@frappe.whitelist()
def get_actual_qty(item_code=None, warehouse=None):
    """
    Single value API for an item + warehouse (group-aware).
    Returns float.
    """
    return _get_bin_qty(item_code, warehouse)


@frappe.whitelist()
def get_both_qty(item_code=None, from_warehouse=None, target_warehouse=None):
    """
    Backwards compatibility for any existing UI code.
    Returns: {"qty_from": <float>, "qty_target": <float>}
    """
    return {
        "qty_from": _get_bin_qty(item_code, from_warehouse) if from_warehouse else 0.0,
        "qty_target": _get_bin_qty(item_code, target_warehouse) if target_warehouse else 0.0,
    }


@frappe.whitelist()
def get_many_rows_qty(items):
    """
    items: JSON string or list of dicts: [{item_code, from_warehouse, target_warehouse}, ...]
    Bulk API: returns a list in same order with keys qty_from, qty_target
    """
    import json

    if isinstance(items, str):
        items = json.loads(items)

    out = []
    # To be efficient we can still call _get_bin_qty per row because _get_bin_qty uses
    # bulk child warehouse lookup but calls Bin sum each time. If you want further optimization
    # we can batch, but this is simple and correct.
    for it in items:
        item = it.get("item_code")
        src = it.get("from_warehouse")
        tgt = it.get("target_warehouse")

        qty_from = _get_bin_qty(item, src) if item and src else 0.0
        qty_target = _get_bin_qty(item, tgt) if item and tgt else 0.0

        out.append({"qty_from": qty_from, "qty_target": qty_target})

    return out
