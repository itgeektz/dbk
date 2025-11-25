# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
import json
import frappe
from frappe import _

def get_rfq_field_name():
    """
    Dynamically find the field name that links Supplier Quotation to Request for Quotation
    Cache it for performance
    """
    cache_key = "rfq_field_name"
    field_name = frappe.cache().get_value(cache_key)
    
    if field_name:
        return field_name
    
    # Check Supplier Quotation Item first (most common location)
    sqi_meta = frappe.get_meta("Supplier Quotation Item")
    for field in sqi_meta.fields:
        if field.fieldtype == "Link" and field.options == "Request for Quotation":
            frappe.cache().set_value(cache_key, field.fieldname)
            return field.fieldname
    
    # Check Supplier Quotation header
    sq_meta = frappe.get_meta("Supplier Quotation")
    for field in sq_meta.fields:
        if field.fieldtype == "Link" and field.options == "Request for Quotation":
            frappe.cache().set_value(cache_key, field.fieldname)
            return field.fieldname
    
    # Default fallback
    return "request_for_quotation"


@frappe.whitelist()
def execute(filters=None):
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}

    filters = frappe._dict(filters or {})    
    rfq = filters.get("request_for_quotation")

    if not rfq:
        return [], [], {}, None

    columns, data, summary = [], [], {}
    schedule_date = None

    try:
        # Get the correct field name for RFQ link
        rfq_field = get_rfq_field_name()
        
        # 1️⃣ Get all supplier quotations linked to this RFQ
        # Use SQL to find through items since the link is in child table
        all_quotations = frappe.db.sql("""
            SELECT DISTINCT 
                sq.name,
                sq.supplier,
                sq.supplier_name,
                sq.transaction_date,
                sq.valid_till,
                sq.base_net_total,
                sq.base_total_taxes_and_charges,
                sq.base_grand_total,
                sq.contact_person,
                sq.contact_mobile
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sqi.{} = %s
            ORDER BY sq.transaction_date DESC
        """.format(rfq_field), (rfq,), as_dict=True)

        if not all_quotations:
            frappe.msgprint("No Supplier Quotations linked to this RFQ.")
            return columns, data, summary, schedule_date

        # ✅ Deduplicate: keep the latest quotation per supplier
        supplier_quotations = {}
        for sq in all_quotations:
            supplier = sq.supplier_name or sq.supplier
            if supplier not in supplier_quotations:
                supplier_quotations[supplier] = sq

        supplier_quotations = list(supplier_quotations.values())

        # 2️⃣ Get RFQ items (to build comparison)
        rfq_items = frappe.get_all(
            "Request for Quotation Item",
            filters={"parent": rfq},
            fields=["item_code", "item_name", "qty", "schedule_date"],
            order_by="idx"
        )

        if rfq_items:
            schedule_date = rfq_items[0].schedule_date

        # 3️⃣ Build comparison data table
        for item in rfq_items:
            row = {
                "sl_no": rfq_items.index(item) + 1, 
                "item_code": item.item_code,
                "item_name": item.item_name, 
                "qty": item.qty
            }

            rates = []  # Track all rates for this item
            
            for sq in supplier_quotations:
                supplier = sq.supplier_name or sq.supplier
                sq_item = frappe.db.get_value(
                    "Supplier Quotation Item",
                    {"parent": sq.name, "item_code": item.item_code},
                    ["rate", "amount"],
                    as_dict=True
                )

                if sq_item and sq_item.rate:
                    rate_value = float(sq_item.rate)
                    amount_value = float(sq_item.amount) if sq_item.amount else 0.0
                    
                    row[f"{supplier}_rate"] = rate_value
                    row[f"{supplier}_rate_formatted"] = format_ksh(rate_value)
                    row[f"{supplier}_amount"] = amount_value
                    
                    rates.append(rate_value)
                else:
                    row[f"{supplier}_rate"] = None
                    row[f"{supplier}_rate_formatted"] = "-"
                    row[f"{supplier}_amount"] = None

            # Find minimum rate for highlighting
            if rates:
                min_rate = min(rates)
                row["min_rate"] = min_rate
            else:
                row["min_rate"] = None

            data.append(row)

        # 4️⃣ Build summary per supplier
        for sq in supplier_quotations:
            supplier = sq.supplier_name or sq.supplier
            sub_total = sq.base_net_total or 0.0
            taxes = sq.base_total_taxes_and_charges or 0.0
            total = sq.base_grand_total or (sub_total + taxes)

            # Get payment terms from Payment Schedule
            payment_terms = frappe.db.get_value(
                "Payment Schedule",
                {"parent": sq.name},
                "description"
            ) or "Cheque after Delivery and Inspection of Goods"

            summary[supplier] = {
                "quotation_name": sq.name,
                "supplier": sq.supplier,
                "subtotal": format_ksh(sub_total),
                "subtotal_raw": sub_total,
                "taxes": format_ksh(taxes),
                "taxes_raw": taxes,
                "total": format_ksh(total),
                "total_raw": total,
                "payment_terms": payment_terms,
                "contact_person": sq.contact_person or "",
                "contact_number": sq.contact_mobile or ""
            }

        # 5️⃣ Define columns for completeness
        columns = [
            {"label": "Sl No", "fieldname": "sl_no", "fieldtype": "Int", "width": 60},
            {"label": "Item", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
            {"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 80},
        ]

        for supplier in summary.keys():
            columns.append({
                "label": f"{supplier} Rate",
                "fieldname": f"{supplier}_rate_formatted",
                "fieldtype": "Data",
                "width": 120,
                "align": "right"
            })

        return columns, data, summary, schedule_date

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "DBK Supplier Comparisson Report Error")
        return [], [], {}, None


def format_ksh(value):
    """Format values with thousand separators and convert millions."""
    if value is None or value == "-" or value == "":
        return "-"

    try:
        value = float(value)
    except:
        return "-"

    # Convert values >= 1 million to X.YZ M
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.2f}M"

    # Normal KSh format with comma separators
    return f"{value:,.2f}"


@frappe.whitelist()
def create_purchase_orders(rfq, supplier_selections):
    """
    Create Purchase Orders from selected suppliers
    supplier_selections: JSON string like {"item_code": "supplier_name", ...}
    """
    if isinstance(supplier_selections, str):
        supplier_selections = json.loads(supplier_selections)
    
    # Group items by supplier
    supplier_items = {}
    
    for item_code, supplier_name in supplier_selections.items():
        if supplier_name not in supplier_items:
            supplier_items[supplier_name] = []
        supplier_items[supplier_name].append(item_code)
    
    created_pos = []
    
    # Get RFQ details
    rfq_doc = frappe.get_doc("Request for Quotation", rfq)
    
    for supplier_name, item_codes in supplier_items.items():
        # Find the supplier quotation - try different field names
        sq = None
        
        # First try with opportunity field (common link field)
        sq = frappe.db.get_value(
            "Supplier Quotation",
            {"opportunity": rfq, "supplier_name": supplier_name},
            ["name", "supplier", "supplier_name"],
            as_dict=True
        )
        
        # If not found, search using SQL to find the link
        if not sq:
            sq_list = frappe.db.sql("""
                SELECT sq.name, sq.supplier, sq.supplier_name
                FROM `tabSupplier Quotation` sq
                INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
                WHERE sqi.request_for_quotation = %s 
                AND sq.supplier_name = %s
                LIMIT 1
            """, (rfq, supplier_name), as_dict=True)
            
            if sq_list:
                sq = sq_list[0]
        
        if not sq:
            continue
        
        # Create Purchase Order
        po = frappe.new_doc("Purchase Order")
        po.supplier = sq.supplier
        po.schedule_date = rfq_doc.schedule_date if hasattr(rfq_doc, 'schedule_date') else frappe.utils.today()
        po.company = rfq_doc.company if hasattr(rfq_doc, 'company') else frappe.defaults.get_user_default("Company")
        project_value = None
        if hasattr(rfq_doc, 'project'):
            project_value = rfq_doc.project
        
        # Set project - never allow None or empty string
        if project_value and str(project_value).strip():
            po.project = str(project_value).strip()
        else:
            po.project = "GE"
        # Add items
        items_added = 0
        for item_code in item_codes:
            # Get item details from supplier quotation
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
                    warehouse = frappe.db.get_value(
                        "Warehouse",
                        {"company": po.company, "is_group": 0},
                        "name"
                    )
                
                po.append("items", {
                    "item_code": sq_item.item_code,
                    "item_name": sq_item.item_name,
                    "description": sq_item.description or sq_item.item_name,
                    "qty": sq_item.qty,
                    "rate": sq_item.rate,
                    "uom": sq_item.uom,
                    "warehouse": warehouse,
                    "schedule_date": po.schedule_date,
                    "project": po.project  # Set project at item level too
                })
                items_added += 1
        
        if items_added == 0:
            frappe.msgprint(_("No items found in Supplier Quotation for {0}. Skipping PO creation.").format(supplier_name))
            continue
        
        # Calculate taxes if template exists
        if po.taxes_and_charges:
            po.set_missing_values()
        
        po.insert()
        frappe.db.commit()
        created_pos.append(po.name)
    
    return created_pos


@frappe.whitelist()
def get_lowest_suppliers(rfq):
    """Get the lowest supplier for each item"""
    columns, data, summary, schedule_date = execute({"request_for_quotation": rfq})
    
    lowest_selections = {}
    ties = {}  # Items with multiple suppliers at same lowest price
    
    for row in data:
        item_code = row.get("item_code")
        min_rate = row.get("min_rate")
        
        if min_rate is None:
            continue
        
        # Find all suppliers with this minimum rate
        suppliers_at_min = []
        for key, value in row.items():
            if key.endswith("_rate") and not key.endswith("_rate_formatted"):
                if value == min_rate:
                    supplier = key.replace("_rate", "")
                    suppliers_at_min.append(supplier)
        
        if len(suppliers_at_min) == 1:
            lowest_selections[item_code] = suppliers_at_min[0]
        elif len(suppliers_at_min) > 1:
            ties[item_code] = {
                "suppliers": suppliers_at_min,
                "rate": min_rate,
                "item_name": row.get("item_name")
            }
    
    return {
        "lowest_selections": lowest_selections,
        "ties": ties,
        "summary": summary
    }