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
    rfq_doc = frappe.get_doc("Request for Quotation", rfq) if rfq else None
    if not rfq:
        return [], [], {}, None

    columns, data, summary = [], [], {}
    schedule_date = None

    try:
        # Get the correct field name for RFQ link
        rfq_field = get_rfq_field_name()
        
        # 1️⃣ Get all supplier quotations linked to this RFQ
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
            AND sq.docstatus = 1
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
            fields=["item_code", "item_name", "qty", "schedule_date", "uom"],
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
                "qty": item.qty,
                "uom": item.uom
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
                
                # Mark which suppliers have the lowest rate
                for sq in supplier_quotations:
                    supplier = sq.supplier_name or sq.supplier
                    rate = row.get(f"{supplier}_rate")
                    
                    # Check if this supplier has the lowest rate (with tolerance)
                    if rate is not None and abs(rate - min_rate) < 0.01:
                        row[f"{supplier}_is_lowest"] = True
                    else:
                        row[f"{supplier}_is_lowest"] = False
            else:
                row["min_rate"] = None
                # Mark all as not lowest if no rates
                for sq in supplier_quotations:
                    supplier = sq.supplier_name or sq.supplier
                    row[f"{supplier}_is_lowest"] = False

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
                "contact_number": sq.contact_mobile or "",
                "justification": rfq_doc.justification if rfq_doc else ""
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
def create_purchase_orders_from_meeting(meeting_name):
    """
    Create Purchase Orders from RFQ Meeting
    This is triggered when RFQ Meeting is submitted
    """
    meeting = frappe.get_doc("RFQ Meeting", meeting_name)
    
    if not meeting.item_selections:
        frappe.throw("No items selected in meeting")
    
    # Group items by supplier
    supplier_items = {}
    for item in meeting.item_selections:
        if not item.selected_supplier:
            continue
        
        if item.selected_supplier not in supplier_items:
            supplier_items[item.selected_supplier] = []
        
        supplier_items[item.selected_supplier].append(item)
    
    created_pos = []
    
    for supplier_name, items in supplier_items.items():
        po = create_purchase_order_for_supplier(
            meeting.request_for_quotation,
            supplier_name,
            items,
            meeting.company,
            meeting.required_date,
            meeting.project,
            meeting.name
        )
        
        if po:
            created_pos.append(po.name)
    
    return created_pos


def create_purchase_order_for_supplier(rfq, supplier_name, items, company, required_date, project, meeting_ref=None):
    """Create a single PO for a supplier with selected items"""
    
    # Find supplier quotation
    rfq_field = get_rfq_field_name()
    sq = frappe.db.sql("""
        SELECT sq.name, sq.supplier, sq.supplier_name
        FROM `tabSupplier Quotation` sq
        INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
        WHERE sqi.{} = %s 
        AND (sq.supplier_name = %s OR sq.supplier = %s)
        AND sq.docstatus = 1
        LIMIT 1
    """.format(rfq_field), (rfq, supplier_name, supplier_name), as_dict=True)
    
    if not sq:
        frappe.msgprint(f"No supplier quotation found for {supplier_name}")
        return None
    
    # Create Purchase Order
    po = frappe.new_doc("Purchase Order")
    po.supplier = sq[0].supplier
    po.company = company
    po.schedule_date = required_date
    
    # Set project - ensure it's not None or empty
    if project and str(project).strip():
        po.project = str(project).strip()
    else:
        po.project = "GE"  # Default fallback
    
    # Link to meeting if provided
    if meeting_ref and frappe.db.exists("Custom Field", {"dt": "Purchase Order", "fieldname": "rfq_meeting"}):
        po.rfq_meeting = meeting_ref
    
    # Add items
    items_added = 0
    for item in items:
        # Get item details from supplier quotation
        sq_item = frappe.db.get_value(
            "Supplier Quotation Item",
            {"parent": sq[0].name, "item_code": item.item_code},
            ["rate", "warehouse", "description", "uom"],
            as_dict=True
        )
        
        if sq_item:
            warehouse = sq_item.warehouse
            if not warehouse:
                warehouse = frappe.db.get_value(
                    "Warehouse",
                    {"company": company, "is_group": 0},
                    "name"
                )
            
            po.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": sq_item.description or item.item_name,
                "qty": item.qty,
                "rate": sq_item.rate,
                "uom": sq_item.uom or item.uom,
                "warehouse": warehouse,
                "schedule_date": required_date,
                "project": po.project
            })
            items_added += 1
    
    if items_added == 0:
        frappe.msgprint(_(f"No items found in Supplier Quotation for {supplier_name}. Skipping PO creation."))
        return None
    
    po.insert()
    frappe.db.commit()
    
    return po


@frappe.whitelist()
def create_purchase_orders(rfq, supplier_selections, project=None, required_date=None):
    """
    Create Purchase Orders from selected suppliers (legacy function for report)
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
    company = rfq_doc.company
    
    # Use provided values or defaults from RFQ
    if not project:
        project = getattr(rfq_doc, 'project', 'GE')
    if not required_date:
        required_date = getattr(rfq_doc, 'schedule_date', frappe.utils.today())
    
    for supplier_name, item_codes in supplier_items.items():
        # Get item details for this supplier
        items = []
        for item_code in item_codes:
            item = frappe.db.get_value(
                "Request for Quotation Item",
                {"parent": rfq, "item_code": item_code},
                ["item_code", "item_name", "qty", "uom"],
                as_dict=True
            )
            if item:
                items.append(item)
        
        po = create_purchase_order_for_supplier(
            rfq, supplier_name, items, company, required_date, project
        )
        
        if po:
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


@frappe.whitelist()
def get_comparison_data_for_print(rfq):
    """
    Get formatted comparison data for print formats
    Returns data suitable for Jinja templates
    """
    columns, data, summary, schedule_date = execute({"request_for_quotation": rfq})
    
    if not data:
        return None
    
    # Extract supplier names
    supplier_names = list(summary.keys())
    
    # Determine lowest bidders
    lowest_bidders = set()
    for row in data:
        if row.get("min_rate") is not None:
            for supplier in supplier_names:
                rate = row.get(f"{supplier}_rate")
                if rate is not None and abs(rate - row["min_rate"]) < 0.01:
                    lowest_bidders.add(supplier)
    
    return {
        "suppliers": supplier_names,
        "items": data,
        "summary": summary,
        "schedule_date": schedule_date,
        "lowest_bidders": list(lowest_bidders),
        "rfq": rfq
    }


@frappe.whitelist()
def get_default_committee_members():
    """
    Get default committee members from settings
    Returns list of {member_name, position}
    """
    try:
        settings = frappe.get_single("RFQ Committee Settings")
        
        if settings and settings.default_committee_members:
            # Only return active members
            return [
                {
                    "member_name": member.member_name,
                    "position": member.position
                }
                for member in settings.default_committee_members
                if member.is_active
            ]
        else:
            # Fallback to hardcoded defaults if settings not configured
            return [
                {"member_name": "Francis Mbiu", "position": "Administrator"},
                {"member_name": "Silas Njiru", "position": "Academic Dean"},
                {"member_name": "Judy Wamalwa", "position": "Supply & Logistics"}
            ]
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Default Committee Members Error")
        # Return hardcoded fallback on error
        return [
            {"member_name": "Francis Mbiu", "position": "Administrator"},
            {"member_name": "Silas Njiru", "position": "Academic Dean"},
            {"member_name": "Judy Wamalwa", "position": "Supply & Logistics"}
        ]


def clean_empty_html(html_content):
    """
    Clean empty HTML markup from text editor fields
    Returns None if content is empty, otherwise returns original content
    """
    if not html_content:
        return None
    
    # Common empty patterns from Quill editor
    empty_patterns = [
        '<div class="ql-editor read-mode"><p><br></p></div>',
        '<div class="ql-editor"><p><br></p></div>',
        '<p><br></p>',
        '<p></p>',
        '<div></div>',
        '<br>',
        '&nbsp;'
    ]
    
    html_stripped = html_content.strip()
    
    # Check exact matches
    if html_stripped in empty_patterns:
        return None
    
    # Strip all HTML tags and check for actual text
    import re
    text_only = re.sub(r'<[^>]*>', '', html_stripped)
    text_only = text_only.replace('&nbsp;', '').strip()
    
    return html_content if text_only else None