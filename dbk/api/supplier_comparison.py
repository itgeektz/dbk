# File: dbk/api/supplier_comparison.py
"""
API endpoints for Supplier Comparison and Purchase Order creation
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def get_comparison_data(rfq):
    """
    Get comprehensive comparison data for an RFQ
    Returns structured data including items, suppliers, and recommendations
    """
    from dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson import execute
    
    columns, data, summary, schedule_date = execute({"request_for_quotation": rfq})
    
    # Analyze and structure the data
    analysis = {
        "rfq": rfq,
        "schedule_date": schedule_date,
        "suppliers": list(summary.keys()),
        "items": [],
        "recommendations": {},
        "summary": summary
    }
    
    for row in data:
        item_info = {
            "item_code": row.get("item_code"),
            "item_name": row.get("item_name"),
            "qty": row.get("qty"),
            "min_rate": row.get("min_rate"),
            "supplier_rates": {}
        }
        
        # Collect all supplier rates
        for supplier in analysis["suppliers"]:
            rate = row.get(f"{supplier}_rate")
            if rate is not None:
                item_info["supplier_rates"][supplier] = {
                    "rate": rate,
                    "is_lowest": abs(rate - row.get("min_rate", float('inf'))) < 0.01 if row.get("min_rate") else False
                }
        
        # Determine recommendation
        lowest_suppliers = [
            s for s, info in item_info["supplier_rates"].items()
            if info["is_lowest"]
        ]
        
        if len(lowest_suppliers) == 1:
            analysis["recommendations"][row.get("item_code")] = {
                "supplier": lowest_suppliers[0],
                "rate": row.get("min_rate"),
                "auto_selected": True
            }
        elif len(lowest_suppliers) > 1:
            analysis["recommendations"][row.get("item_code")] = {
                "suppliers": lowest_suppliers,
                "rate": row.get("min_rate"),
                "requires_selection": True
            }
        
        analysis["items"].append(item_info)
    
    return analysis


@frappe.whitelist()
def create_purchase_orders_smart(rfq, supplier_selections=None):
    """
    Smart PO creation that groups items by supplier
    If supplier_selections is not provided, auto-selects lowest bidders
    """
    if isinstance(supplier_selections, str):
        supplier_selections = json.loads(supplier_selections)
    
    # If no selections provided, get auto-recommendations
    if not supplier_selections:
        analysis = get_comparison_data(rfq)
        supplier_selections = {}
        
        for item_code, rec in analysis["recommendations"].items():
            if rec.get("auto_selected"):
                supplier_selections[item_code] = rec["supplier"]
            elif rec.get("requires_selection"):
                # Skip items that require manual selection
                continue
    
    # Group items by supplier
    supplier_groups = {}
    for item_code, supplier_name in supplier_selections.items():
        if supplier_name not in supplier_groups:
            supplier_groups[supplier_name] = []
        supplier_groups[supplier_name].append(item_code)
    
    # Get RFQ document
    rfq_doc = frappe.get_doc("Request for Quotation", rfq)
    
    created_pos = []
    errors = []
    
    for supplier_name, item_codes in supplier_groups.items():
        try:
            po_name = create_single_purchase_order(
                rfq=rfq,
                rfq_doc=rfq_doc,
                supplier_name=supplier_name,
                item_codes=item_codes
            )
            if po_name:
                created_pos.append(po_name)
        except Exception as e:
            errors.append({
                "supplier": supplier_name,
                "error": str(e)
            })
            frappe.log_error(
                frappe.get_traceback(),
                f"Error creating PO for {supplier_name}"
            )
    
    return {
        "success": len(created_pos) > 0,
        "purchase_orders": created_pos,
        "errors": errors,
        "count": len(created_pos)
    }


def create_single_purchase_order(rfq, rfq_doc, supplier_name, item_codes):
    """
    Create a single Purchase Order for a supplier with specified items
    """
    # Find the supplier quotation - try multiple methods
    sq = None
    
    # Method 1: Try with opportunity field
    sq = frappe.db.get_value(
        "Supplier Quotation",
        {"opportunity": rfq, "supplier_name": supplier_name},
        ["name", "supplier", "supplier_name", "company", "currency"],
        as_dict=True
    )
    
    # Method 2: Search using SQL through items
    if not sq:
        sq_list = frappe.db.sql("""
            SELECT DISTINCT sq.name, sq.supplier, sq.supplier_name, sq.company, sq.currency
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sqi.request_for_quotation = %s 
            AND sq.supplier_name = %s
            LIMIT 1
        """, (rfq, supplier_name), as_dict=True)
        
        if sq_list:
            sq = sq_list[0]
    
    if not sq:
        frappe.throw(_("Supplier Quotation not found for {0}").format(supplier_name))
    
    # Create Purchase Order
    po = frappe.new_doc("Purchase Order")
    po.supplier = sq.supplier
    po.company = sq.company or rfq_doc.company or frappe.defaults.get_user_default("Company")
    po.currency = sq.currency or "KES"
    
    # Set project from RFQ or default to GE
    # Important: Ensure we always have a valid project value
    project_value = None
    if hasattr(rfq_doc, 'project'):
        project_value = rfq_doc.project
    
    # Set project - never allow None or empty string
    if project_value and str(project_value).strip():
        po.project = str(project_value).strip()
    else:
        po.project = "GE"
    
    # Set dates
    if rfq_doc.schedule_date:
        po.schedule_date = rfq_doc.schedule_date
    else:
        po.schedule_date = frappe.utils.today()
    
    po.transaction_date = frappe.utils.today()
    
    # Try to get default tax template
    po.taxes_and_charges = frappe.db.get_value(
        "Purchase Taxes and Charges Template",
        {"company": po.company, "is_default": 1},
        "name"
    )
    
    # Get supplier's tax category
    tax_category = frappe.db.get_value("Supplier", sq.supplier, "tax_category")
    if tax_category:
        po.tax_category = tax_category
    
    # Add items
    items_added = 0
    for item_code in item_codes:
        sq_item = frappe.db.get_value(
            "Supplier Quotation Item",
            {"parent": sq.name, "item_code": item_code},
            ["item_code", "item_name", "qty", "rate", "uom", "warehouse", "description"],
            as_dict=True
        )
        
        if sq_item:
            # Get default warehouse if not set
            warehouse = sq_item.warehouse
            if not warehouse:
                warehouse = get_default_warehouse(po.company)
            
            po.append("items", {
                "item_code": sq_item.item_code,
                "item_name": sq_item.item_name,
                "description": sq_item.description or sq_item.item_name,
                "qty": sq_item.qty,
                "rate": sq_item.rate,
                "uom": sq_item.uom,
                "warehouse": warehouse,
                "schedule_date": po.schedule_date,
                "project": po.project  # Set project at item level
            })
            items_added += 1
    
    if items_added == 0:
        return None
    
    # Calculate taxes if template exists
    if po.taxes_and_charges:
        po.set_missing_values()
    
    # Insert and return
    po.insert()
    frappe.db.commit()
    
    return po.name


def get_default_warehouse(company):
    """Get default warehouse for company"""
    warehouse = frappe.db.get_value(
        "Warehouse",
        {"company": company, "is_group": 0},
        "name"
    )
    return warehouse


@frappe.whitelist()
def get_rfq_summary(rfq):
    """
    Get a summary of an RFQ including total potential savings
    """
    analysis = get_comparison_data(rfq)
    
    total_lowest_amount = 0
    total_highest_amount = 0
    
    for item in analysis["items"]:
        if item["supplier_rates"]:
            rates = [info["rate"] for info in item["supplier_rates"].values()]
            lowest_rate = min(rates)
            highest_rate = max(rates)
            
            qty = item["qty"] or 0
            total_lowest_amount += lowest_rate * qty
            total_highest_amount += highest_rate * qty
    
    potential_savings = total_highest_amount - total_lowest_amount
    savings_percentage = (potential_savings / total_highest_amount * 100) if total_highest_amount > 0 else 0
    
    return {
        "rfq": rfq,
        "total_items": len(analysis["items"]),
        "total_suppliers": len(analysis["suppliers"]),
        "suppliers": analysis["suppliers"],
        "lowest_total": total_lowest_amount,
        "highest_total": total_highest_amount,
        "potential_savings": potential_savings,
        "savings_percentage": savings_percentage,
        "items_requiring_selection": len([
            r for r in analysis["recommendations"].values()
            if r.get("requires_selection")
        ])
    }


@frappe.whitelist()
def bulk_create_from_multiple_rfqs(rfq_list):
    """
    Create purchase orders from multiple RFQs at once
    rfq_list: JSON string of RFQ names
    """
    if isinstance(rfq_list, str):
        rfq_list = json.loads(rfq_list)
    
    results = []
    
    for rfq in rfq_list:
        try:
            result = create_purchase_orders_smart(rfq)
            results.append({
                "rfq": rfq,
                "success": result["success"],
                "pos_created": result["count"],
                "purchase_orders": result["purchase_orders"]
            })
        except Exception as e:
            results.append({
                "rfq": rfq,
                "success": False,
                "error": str(e)
            })
    
    return results


@frappe.whitelist()
def validate_supplier_quotations(rfq):
    """
    Validate that all required quotations are present for an RFQ
    """
    rfq_doc = frappe.get_doc("Request for Quotation", rfq)
    
    # Get suppliers from RFQ
    requested_suppliers = [sup.supplier for sup in rfq_doc.suppliers]
    
    # Get actual quotations received
    received_quotations = frappe.get_all(
        "Supplier Quotation",
        filters={"request_for_quotation": rfq},
        fields=["name", "supplier", "supplier_name", "docstatus"]
    )
    
    received_suppliers = [sq.supplier for sq in received_quotations]
    missing_suppliers = [sup for sup in requested_suppliers if sup not in received_suppliers]
    
    return {
        "rfq": rfq,
        "requested_suppliers": requested_suppliers,
        "received_quotations": len(received_quotations),
        "missing_suppliers": missing_suppliers,
        "all_received": len(missing_suppliers) == 0,
        "quotation_details": received_quotations
    }