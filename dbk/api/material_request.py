# apps/dbk/dbk/api/material_request.py
import frappe
from frappe.utils import flt

# import _get_bin_qty from stock.py to reuse logic
from dbk.api.stock import _get_bin_qty

def sync_item_bin_qtys(doc, method=None):
    """
    Called in Material Request.before_save (via hooks).
    Fill each child row:
      - custom_actual_qty (source/from_warehouse)
      - actual_qty_target (target/warehouse)
    """
    if not getattr(doc, "items", None):
        return

    for row in doc.items:
        # defensively set default values
        row.custom_actual_qty = 0.0
        row.actual_qty_target = 0.0

        item = row.get("item_code")
        source_wh = row.get("from_warehouse")
        target_wh = row.get("warehouse")

        if item and source_wh:
            row.custom_actual_qty = _get_bin_qty(item, source_wh)

        if item and target_wh:
            row.actual_qty_target = _get_bin_qty(item, target_wh)
