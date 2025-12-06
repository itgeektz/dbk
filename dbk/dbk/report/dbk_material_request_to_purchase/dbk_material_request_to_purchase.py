# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "quantity",
            "label": _("Required Qty"),
            "fieldtype": "Float",
            "width": 120
        },
        {
            "fieldname": "stock_uom",
            "label": _("UOM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "fieldname": "current_stock",
            "label": _("Current Stock (Main Store)"),
            "fieldtype": "Float",
            "width": 150
        },
        {
            "fieldname": "material_request",
            "label": _("Material Request"),
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 150
        },
        {
            "fieldname": "material_request_date",
            "label": _("MR Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "schedule_date",
            "label": _("Required By"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "warehouse",
            "label": _("Target Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    # Fetch material request items
    data = frappe.db.sql("""
        SELECT 
            mri.item_code,
            mri.item_name,
            SUM(mri.qty - mri.ordered_qty) as quantity,
            mri.stock_uom,
            mr.name as material_request,
            mr.transaction_date as material_request_date,
            mr.status,
            mri.schedule_date,
            mri.warehouse
        FROM 
            `tabMaterial Request Item` mri
        INNER JOIN 
            `tabMaterial Request` mr ON mri.parent = mr.name
        WHERE 
            mr.docstatus = 1
            AND mr.status != 'Stopped'
            AND mr.material_request_type = 'Purchase'
            AND (mri.qty - mri.ordered_qty) > 0
            {conditions}
        GROUP BY 
            mri.item_code, mr.name, mri.warehouse, mri.schedule_date
        ORDER BY 
            mri.item_code, mr.transaction_date
    """.format(conditions=conditions), filters, as_dict=1)
    
    # Get current stock for main store and its children
    if filters.get("source_warehouse"):
        source_warehouse = filters.get("source_warehouse")
        child_warehouses = get_child_warehouses(source_warehouse)
        warehouse_list = [source_warehouse] + child_warehouses
        
        # Get stock levels
        stock_dict = get_stock_levels(warehouse_list)
        
        for row in data:
            row['current_stock'] = stock_dict.get(row['item_code'], 0)
    
    # Handle duplicate items based on toggle
    if filters.get("remove_duplicates"):
        data = consolidate_items(data)
    
    return data

def get_conditions(filters):
    conditions = []
    
    if filters.get("from_date"):
        conditions.append("mr.transaction_date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("mr.transaction_date <= %(to_date)s")
    
    if filters.get("company"):
        conditions.append("mr.company = %(company)s")
    
    if filters.get("purpose"):
        conditions.append("mr.material_request_type = %(purpose)s")
    
    if filters.get("target_warehouse"):
        conditions.append("mri.warehouse = %(target_warehouse)s")
    
    if filters.get("source_warehouse"):
        conditions.append("mr.set_warehouse = %(source_warehouse)s")
    
    return " AND " + " AND ".join(conditions) if conditions else ""

def get_child_warehouses(parent_warehouse):
    """Get all child warehouses of a parent warehouse"""
    lft, rgt = frappe.db.get_value("Warehouse", parent_warehouse, ["lft", "rgt"])
    
    child_warehouses = frappe.db.sql_list("""
        SELECT name 
        FROM `tabWarehouse`
        WHERE lft > %s AND rgt < %s
        AND is_group = 0
    """, (lft, rgt))
    
    return child_warehouses

def get_stock_levels(warehouses):
    """Get current stock levels for items in specified warehouses"""
    if not warehouses:
        return {}
    
    stock_data = frappe.db.sql("""
        SELECT 
            item_code,
            SUM(actual_qty) as total_qty
        FROM 
            `tabBin`
        WHERE 
            warehouse IN ({warehouses})
        GROUP BY 
            item_code
    """.format(warehouses=', '.join(['%s'] * len(warehouses))), tuple(warehouses), as_dict=1)
    
    return {row['item_code']: flt(row['total_qty']) for row in stock_data}

def consolidate_items(data):
    """Consolidate duplicate items - keep only one entry with total quantity"""
    consolidated = {}
    
    for row in data:
        item_code = row['item_code']
        
        if item_code not in consolidated:
            consolidated[item_code] = row
        else:
            # Add quantity to existing entry
            consolidated[item_code]['quantity'] += row['quantity']
            # Keep the earliest schedule date
            if row['schedule_date'] and (not consolidated[item_code]['schedule_date'] or 
                row['schedule_date'] < consolidated[item_code]['schedule_date']):
                consolidated[item_code]['schedule_date'] = row['schedule_date']
            # Append material request numbers
            consolidated[item_code]['material_request'] += ", " + row['material_request']
    
    return list(consolidated.values())

@frappe.whitelist()
def create_rfq_from_report(items, suppliers):
    """Create Request for Quotation from report items"""
    import json
    
    if isinstance(items, str):
        items = json.loads(items)
    
    if isinstance(suppliers, str):
        suppliers = json.loads(suppliers)
    
    if not items:
        frappe.throw(_("Please select items to create RFQ"))
    
    if not suppliers:
        frappe.throw(_("Please select at least one supplier"))
    
    # Create RFQ
    rfq = frappe.new_doc("Request for Quotation")
    rfq.transaction_date = getdate()
    rfq.company = items[0].get('company') or frappe.defaults.get_user_default("Company")
    
    # Add suppliers
    for supplier in suppliers:
        rfq.append("suppliers", {
            "supplier": supplier
        })
    
    # Add items
    for item in items:
        rfq.append("items", {
            "item_code": item.get("item_code"),
            "qty": item.get("quantity"),
            "schedule_date": item.get("schedule_date"),
            "warehouse": item.get("warehouse"),
            "material_request": item.get("material_request").split(",")[0].strip() if item.get("material_request") else None,
            "material_request_item": None  # This would need to be tracked if needed
        })
    
    rfq.save()
    frappe.db.commit()
    
    return rfq.name