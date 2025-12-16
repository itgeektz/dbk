# -*- coding: utf-8 -*-
# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
"""
Fixed Report Script for ERPNext v15 - No imports needed
This script runs in a restricted execution environment where frappe and common
functions are already available in the global scope.
"""

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    """Define report columns"""
    return [
         {
            "label": _("Select"),
            "fieldname": "select_row",
            "fieldtype": "Check",
            "width": 50
        },
        {
            "label": _("Material Request"),
            "fieldname": "material_request",
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 150
        },
        {
            "label": _("Transaction Date"),
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 110
        },
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Quantity"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("UOM"),
            "fieldname": "uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "label": _("Purchase UOM"),
            "fieldname": "purchase_uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 110
        },
        {
            "label": _("Conversion Factor"),
            "fieldname": "conversion_factor",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": _("Qty in Purchase UOM"),
            "fieldname": "qty_in_purchase_uom",
            "fieldtype": "Float",
            "width": 140
        },
        {
            "label": _("Required Date"),
            "fieldname": "schedule_date",
            "fieldtype": "Date",
            "width": 110
        },
        {
            "label": _("Target Warehouse"),
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "label": _("Approval Status"),
            "fieldname": "workflow_state",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Rate"),
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        }
    ]


def get_data(filters):
    """Fetch and process material request items"""
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are mandatory"))
    
    # Query to get material request items
    data = frappe.db.sql("""
        SELECT
            mr.name AS material_request,
            mr.transaction_date,
            mri.item_code,
            mri.item_name,
            mri.qty,
            mri.uom,
            mri.schedule_date,
            mri.warehouse,
            mr.workflow_state,
            mri.rate,
            mri.amount,
            mri.name as mr_item_name
        FROM
            `tabMaterial Request` mr
        JOIN
            `tabMaterial Request Item` mri
            ON mri.parent = mr.name
        WHERE
            mr.docstatus < 2 
            AND mri.custom_purchase = 1 
            AND mr.transaction_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY
            mr.transaction_date DESC, mr.name DESC
    """, filters, as_dict=1)
    
    # Process each row to add UOM conversion data
    for row in data:
        row.select_row = 0
        # Get item details including purchase UOM
        item = frappe.get_doc("Item", row.item_code)
        
        # Get purchase UOM from item master
        purchase_uom = None
        #conversion_factor = 1.0
        
        # Check if item has a purchase UOM defined
        if hasattr(item, 'purchase_uom') and item.purchase_uom:
            purchase_uom = item.purchase_uom
        else:
            # Fall back to stock UOM
            purchase_uom = item.stock_uom
        
        row.purchase_uom = purchase_uom
        #conversion_factor = 1.0
        # If purchase UOM is different from current UOM, get conversion factor
        if row.uom != purchase_uom:
            conversion_factor = get_uom_conversion_factor(
                row.item_code, 
                row.uom, 
                purchase_uom
            )
        else:
            conversion_factor = 1.0
        row.conversion_factor = conversion_factor
        row.qty_in_purchase_uom = flt(row.qty * conversion_factor, 2)
    
    
    return data


def get_uom_conversion_factor(item_code, from_uom, to_uom):
    """Get conversion factor between two UOMs for an item"""
    if from_uom == to_uom:
        return 1.0
    
    # Try to find conversion factor in UOM Conversion Detail
    conversion = frappe.db.get_value(
        "UOM Conversion Detail",
        {
            "parent": item_code,
            "uom": from_uom
        },
        "conversion_factor"
    )
    
    if conversion:
        return flt(conversion)
    """ 
    # Try reverse conversion
    reverse_conversion = frappe.db.get_value(
        "UOM Conversion Detail",
        {
            "parent": item_code,
            "uom": from_uom
        },
        "conversion_factor"
    )
    
    if reverse_conversion and flt(reverse_conversion) != 0:
        return flt(1.0 / reverse_conversion)
    """
    # If no conversion found, return 1
    return 1.0

@frappe.whitelist()
def create_rfq(items):
    items = frappe.parse_json(items)

    selected_items = [i for i in items if i.get("select_row")]

    if not selected_items:
        frappe.throw(_("Please select at least one item to convert to RFQ"))

    # continue with RFQ creation
