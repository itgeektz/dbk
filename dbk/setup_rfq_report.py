# -*- coding: utf-8 -*-
# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Setup script to install the Enhanced RFQ Report from Material Request

Run this from bench console:
bench --site your-site-name console
>>> from dbk.setup_rfq_report import setup_report
>>> setup_report()
"""

import frappe
from frappe import _

def setup_report():
    """Create or update the RFQ Items from Material Request Enhanced report"""
    
    report_name = "RFQ Items from Material Request Enhanced"
    
    # Check if report already exists
    if frappe.db.exists("Report", report_name):
        print(f"Report '{report_name}' already exists. Updating...")
        report = frappe.get_doc("Report", report_name)
    else:
        print(f"Creating new report '{report_name}'...")
        report = frappe.new_doc("Report")
        report.report_name = report_name
        report.ref_doctype = "Material Request"
        report.is_standard = "No"
        report.module = "Stock"
    
    # Set report properties
    report.report_type = "Script Report"
    report.disabled = 0
    
    # Set the report script (Python code)
    report.report_script = get_report_script()
    
    # Clear existing roles and add new ones
    report.roles = []
    roles = [
        "Purchase Manager",
        "Purchase User", 
        "Stock User",
        "Stock Manager",
        "Procurement Officer",
        "Store Manager",
        "Principal",
        "DBK User",
        "Accounts Manager",
        "Projects Manager",
        "System Manager",
        "DBK Admin"
    ]
    
    for role in roles:
        report.append("roles", {"role": role})
    
    # Save the report
    report.save(ignore_permissions=True)
    frappe.db.commit()
    
    print(f"✓ Report '{report_name}' saved successfully!")
    print(f"✓ Report ID: {report.name}")
    
    # Create the server-side methods file
    create_utils_file()
    
    # JavaScript setup instructions
    print_js_instructions(report_name)
    
    print("\n" + "="*60)
    print("Installation Complete!")
    print("="*60)
    print(f"\nNext steps:")
    print(f"1. Copy rfq_utils.py to apps/dbk/dbk/")
    print(f"2. Add JavaScript as shown above")
    print(f"3. Clear cache: bench --site {frappe.local.site} clear-cache")
    print(f"4. Rebuild: bench build --app dbk")
    print(f"5. Restart: bench restart")
    print(f"6. Navigate to: Stock → Reports → {report_name}")
    print("\n")
    
    return report


def get_report_script():
    """Return the Python script for the report - No imports in restricted execution"""
    return """def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Material Request"), "fieldname": "material_request", "fieldtype": "Link", "options": "Material Request", "width": 150},
        {"label": _("Transaction Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 110},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": _("Purchase UOM"), "fieldname": "purchase_uom", "fieldtype": "Link", "options": "UOM", "width": 110},
        {"label": _("Conversion Factor"), "fieldname": "conversion_factor", "fieldtype": "Float", "width": 120},
        {"label": _("Qty in Purchase UOM"), "fieldname": "qty_in_purchase_uom", "fieldtype": "Float", "width": 140},
        {"label": _("Required Date"), "fieldname": "schedule_date", "fieldtype": "Date", "width": 110},
        {"label": _("Target Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"label": _("Approval Status"), "fieldname": "workflow_state", "fieldtype": "Data", "width": 120},
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120}
    ]


def get_data(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are mandatory"))
    
    data = frappe.db.sql(\"\"\"
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
    \"\"\", filters, as_dict=1)
    
    for row in data:
        item = frappe.get_cached_doc("Item", row.item_code)
        
        purchase_uom = None
        conversion_factor = 1.0
        
        if hasattr(item, 'purchase_uom') and item.purchase_uom:
            purchase_uom = item.purchase_uom
        else:
            purchase_uom = item.stock_uom
        
        row.purchase_uom = purchase_uom
        
        if row.uom != purchase_uom:
            conversion_factor = get_uom_conversion_factor(
                row.item_code, 
                row.uom, 
                purchase_uom
            )
        
        row.conversion_factor = conversion_factor
        row.qty_in_purchase_uom = flt(row.qty * conversion_factor, 2)
    
    return data


def get_uom_conversion_factor(item_code, from_uom, to_uom):
    if from_uom == to_uom:
        return 1.0
    
    conversion = frappe.db.get_value(
        "UOM Conversion Detail",
        {
            "parent": item_code,
            "uom": to_uom
        },
        "conversion_factor"
    )
    
    if conversion:
        return flt(conversion)
    
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
    
    return 1.0
"""


def print_js_instructions(report_name):
    """Print instructions for adding JavaScript to the report"""
    print("\n" + "="*60)
    print("JavaScript Setup Instructions")
    print("="*60)
    print("\nFor ERPNext v15, report JavaScript must be added via hooks.py")
    print("\nStep 1: Create the JavaScript file")
    print("-------")
    print("File: apps/dbk/dbk/public/js/rfq_report_actions.js")
    print("\nStep 2: Add to hooks.py")
    print("-------")
    print("In apps/dbk/dbk/hooks.py, add:")
    print("""
# Add this to your existing hooks.py
report_js = {
    "RFQ Items from Material Request Enhanced": "public/js/rfq_report_actions.js"
}
""")
    print("\nStep 3: Build and restart")
    print("-------")
    print("bench build --app dbk")
    print("bench restart")
    print("\n" + "="*60)


def create_utils_file():
    """Instructions for creating the utils file"""
    print("\n" + "="*60)
    print("Server-Side Utils File")
    print("="*60)
    print("\nThe server-side utility functions need to be added to your custom app.")
    print("Copy the provided rfq_utils.py file to:")
    print("  apps/dbk/dbk/rfq_utils.py")
    print("\nThis file contains the @frappe.whitelist() methods for:")
    print("  - create_rfq_from_material_requests()")
    print("  - get_item_uom_details()")
    print("  - validate_material_request_items()")
    print("="*60)


if __name__ == "__main__":
    setup_report()