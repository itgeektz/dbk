# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


@frappe.whitelist()
def create_rfq_from_material_requests(items, suppliers, schedule_date, message_for_supplier=None):
    """
    Server-side method to create RFQ from selected Material Request items
    
    Args:
        items: JSON string of selected items from report
        suppliers: JSON string of suppliers to send RFQ
        schedule_date: Required by date for RFQ
        message_for_supplier: Optional message for suppliers
    
    Returns:
        Name of created RFQ document
    """
    import json
    
    # Parse JSON strings
    if isinstance(items, str):
        items = json.loads(items)
    if isinstance(suppliers, str):
        suppliers = json.loads(suppliers)
    
    if not items:
        frappe.throw(_("No items selected to create RFQ"))
    
    if not suppliers:
        frappe.throw(_("Please select at least one supplier"))
    
    # Create RFQ document
    rfq = frappe.get_doc({
        "doctype": "Request for Quotation",
        "transaction_date": nowdate(),
        "schedule_date": schedule_date,
        "message_for_supplier": message_for_supplier or "",
        "company": frappe.defaults.get_user_default("Company")
    })
    
    # Add suppliers
    for supplier in suppliers:
        supplier_name = supplier.get("supplier") or supplier.get("name")
        if supplier_name:
            rfq.append("suppliers", {
                "supplier": supplier_name
            })
    
    # Add items with UOM conversion
    for item in items:
        rfq_item = prepare_rfq_item(item)
        rfq.append("items", rfq_item)
    
    # Insert and save
    rfq.insert(ignore_permissions=False)
    
    frappe.db.commit()
    
    return {
        "name": rfq.name,
        "message": _("Request for Quotation {0} created successfully").format(rfq.name)
    }


def prepare_rfq_item(item):
    """
    Prepare RFQ item from Material Request item with UOM conversion
    
    Args:
        item: Dictionary containing Material Request item data
    
    Returns:
        Dictionary for RFQ item
    """
    item_code = item.get("item_code")
    
    # Get item master data
    item_doc = frappe.get_cached_doc("Item", item_code)
    
    # Determine UOM to use in RFQ
    purchase_uom = item.get("purchase_uom")
    if not purchase_uom:
        # Try to get from item master
        purchase_uom = getattr(item_doc, "purchase_uom", None)
    
    if not purchase_uom:
        # Fall back to stock UOM
        purchase_uom = item_doc.stock_uom
    
    # Get conversion factor
    conversion_factor = get_conversion_factor(
        item_code,
        item.get("uom"),
        purchase_uom
    )
    
    # Calculate quantity in purchase UOM
    original_qty = flt(item.get("qty", 1))
    qty_in_purchase_uom = flt(original_qty * conversion_factor)
    
    # Prepare RFQ item dict
    rfq_item = {
        "item_code": item_code,
        "item_name": item.get("item_name"),
        "schedule_date": item.get("schedule_date") or item.get("required_date"),
        "qty": 1,  # Always set to 1 as per requirement
        "uom": purchase_uom,
        "conversion_factor": conversion_factor,
        "stock_uom": item_doc.stock_uom,
        "warehouse": item.get("warehouse"),
        "material_request": item.get("material_request"),
        "material_request_item": item.get("mr_item_name"),
        "description": item.get("item_name") or item_doc.description,
    }
    
    # Add custom fields if they exist to store original quantity
    if frappe.db.exists("Custom Field", {
        "dt": "Request for Quotation Item",
        "fieldname": "custom_original_qty"
    }):
        rfq_item["custom_original_qty"] = qty_in_purchase_uom
    
    if frappe.db.exists("Custom Field", {
        "dt": "Request for Quotation Item", 
        "fieldname": "custom_original_uom"
    }):
        rfq_item["custom_original_uom"] = item.get("uom")
    
    return rfq_item


def get_conversion_factor(item_code, from_uom, to_uom):
    """
    Get conversion factor between two UOMs for an item
    
    Args:
        item_code: Item code
        from_uom: Source UOM
        to_uom: Target UOM
    
    Returns:
        Float conversion factor
    """
    if from_uom == to_uom:
        return 1.0
    
    # Check UOM Conversion Detail child table
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
    
    # Check if there's a standard UOM conversion (not item-specific)
    try:
        from erpnext.setup.utils import get_exchange_rate
        # This is a fallback for standard UOM conversions
        # You might need to implement custom logic here
        pass
    except:
        pass
    
    # Default to 1 if no conversion found
    frappe.log_error(
        message=f"No conversion factor found for {item_code} from {from_uom} to {to_uom}",
        title="UOM Conversion Missing"
    )
    
    return 1.0


@frappe.whitelist()
def get_item_uom_details(item_code, uom=None):
    """
    Get UOM details for an item
    
    Args:
        item_code: Item code
        uom: Optional specific UOM to get details for
    
    Returns:
        Dictionary with UOM details
    """
    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} does not exist").format(item_code))
    
    item = frappe.get_cached_doc("Item", item_code)
    
    result = {
        "item_code": item_code,
        "stock_uom": item.stock_uom,
        "purchase_uom": getattr(item, "purchase_uom", item.stock_uom),
        "sales_uom": getattr(item, "sales_uom", item.stock_uom),
        "uom_conversions": []
    }
    
    # Get all UOM conversions for this item
    if hasattr(item, "uoms"):
        for uom_row in item.uoms:
            result["uom_conversions"].append({
                "uom": uom_row.uom,
                "conversion_factor": uom_row.conversion_factor
            })
    
    # If specific UOM requested, calculate conversion from stock UOM
    if uom and uom != item.stock_uom:
        result["conversion_factor"] = get_conversion_factor(
            item_code,
            item.stock_uom,
            uom
        )
    
    return result


@frappe.whitelist()
def validate_material_request_items(material_request):
    """
    Validate and get items from Material Request that can be converted to RFQ
    
    Args:
        material_request: Material Request name
    
    Returns:
        List of items that can be converted
    """
    if not frappe.db.exists("Material Request", material_request):
        frappe.throw(_("Material Request {0} does not exist").format(material_request))
    
    mr = frappe.get_doc("Material Request", material_request)
    
    if mr.docstatus != 1:
        frappe.throw(_("Material Request must be submitted to create RFQ"))
    
    # Get items marked for purchase
    purchase_items = []
    for item in mr.items:
        if item.custom_purchase == 1:
            item_dict = {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "uom": item.uom,
                "schedule_date": item.schedule_date,
                "warehouse": item.warehouse,
                "rate": item.rate,
                "amount": item.amount,
                "mr_item_name": item.name
            }
            
            # Add UOM details
            uom_details = get_item_uom_details(item.item_code, item.uom)
            item_dict.update({
                "stock_uom": uom_details["stock_uom"],
                "purchase_uom": uom_details["purchase_uom"],
                "conversion_factor": get_conversion_factor(
                    item.item_code,
                    item.uom,
                    uom_details["purchase_uom"]
                )
            })
            
            purchase_items.append(item_dict)
    
    return purchase_items