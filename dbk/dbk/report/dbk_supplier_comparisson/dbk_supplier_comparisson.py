# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
import json
import frappe

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
        # ------------------------------
        # 1️⃣ Get all supplier quotations linked to this RFQ
        # ------------------------------
        all_quotations = frappe.get_all(
            "Supplier Quotation",
            filters={"request_for_quotation": rfq},
            fields=[
                "name",
                "supplier",
                "supplier_name",
                "transaction_date",
                "valid_till",
                "base_net_total",
                "base_total_taxes_and_charges",
                "base_grand_total",
                "contact_person",
                "contact_mobile"
            ],
            order_by="transaction_date desc"
        )

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

        # ------------------------------
        # 2️⃣ Get RFQ items (to build comparison)
        # ------------------------------
        rfq_items = frappe.get_all(
            "Request for Quotation Item",
            filters={"parent": rfq},
            fields=["item_code", "item_name", "qty", "schedule_date"]
        )

        if rfq_items:
            schedule_date = rfq_items[0].schedule_date

        # ------------------------------
        # 3️⃣ Build comparison data table
        # ------------------------------
        for item in rfq_items:
            row = {"item_name": item.item_name, "qty": item.qty}

            for sq in supplier_quotations:
                supplier = sq.supplier_name or sq.supplier
                sq_item = frappe.db.get_value(
                    "Supplier Quotation Item",
                    {"parent": sq.name, "item_code": item.item_code},
                    ["rate", "amount"],
                    as_dict=True
                )

                row[f"{supplier}_rate"] = sq_item.rate if sq_item else "-"
                row[f"{supplier}_amount"] = sq_item.amount if sq_item else "-"

            data.append(row)

        # ------------------------------
        # 4️⃣ Build summary per supplier
        # ------------------------------
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
                "subtotal": sub_total,
                "taxes": taxes,
                "total": total,
                "payment_terms": payment_terms,
                "contact_person": sq.contact_person or "",
                "contact_number": sq.contact_mobile or ""
            }

        # ------------------------------
        # 5️⃣ Define columns for completeness
        # ------------------------------
        columns = [
            {"label": "Item", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
            {"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 80},
        ]

        for supplier in summary.keys():
            columns.append({
                "label": f"{supplier} Rate",
                "fieldname": f"{supplier}_rate",
                "fieldtype": "Currency",
                "width": 100
            })
            columns.append({
                "label": f"{supplier} Amount",
                "fieldname": f"{supplier}_amount",
                "fieldtype": "Currency",
                "width": 120
            })

        # ------------------------------
        # ✅ Return final structured data
        # ------------------------------
        return columns, data, summary, schedule_date

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "DBK Supplier Comparisson Report Error")
        return [], [], {}, None

"""
import frappe

def execute(filters=None):
    if not filters.get("request_for_quotation"):
        frappe.throw("Please select a Request for Quotation.")

    rfq_name = filters.get("request_for_quotation")

    # Get linked Supplier Quotations
    quotations = frappe.get_all(
        "Supplier Quotation",
        filters={"request_for_quotation": rfq_name},
        fields=["name", "supplier"]
    )

    if not quotations:
        frappe.msgprint("No Supplier Quotations found for this RFQ.")
        return [], []

    # Deduplicate suppliers (avoid repeats)
    suppliers = sorted(list(set([q.supplier for q in quotations])))

    # Get item data
    items = frappe.get_all(
        "Supplier Quotation Item",
        filters={"parent": ["in", [q.name for q in quotations]]},
        fields=["parent", "item_code", "item_name", "qty", "rate"]
    )

    # Build structured comparison
    item_dict = {}
    for row in items:
        supplier = next(q.supplier for q in quotations if q.name == row.parent)
        if row.item_name not in item_dict:
            item_dict[row.item_name] = {
                "item_code": row.item_code,
                "qty": row.qty,
                "rates": {}
            }
        item_dict[row.item_name]["rates"][supplier] = row.rate

    # Prepare final data
    data = []
    for item_name, info in item_dict.items():
        row = {
            "item_name": item_name,
            "qty": info["qty"]
        }
        for supplier in suppliers:
            rate = info["rates"].get(supplier)
            amount = rate * info["qty"] if rate else None
            row[f"{supplier}_rate"] = rate
            row[f"{supplier}_amount"] = amount
        data.append(row)

    # Prepare columns (deduplicated)
    columns = [
        {"label": "Item", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "Quantity", "fieldname": "qty", "fieldtype": "Float", "width": 100},
    ]

    for supplier in suppliers:
        columns.extend([
            {"label": f"{supplier} (Rate)", "fieldname": f"{supplier}_rate", "fieldtype": "Currency", "width": 120},
            {"label": f"{supplier} (Amount)", "fieldname": f"{supplier}_amount", "fieldtype": "Currency", "width": 120},
        ])

    # Store unique suppliers in message for the JS print section
    frappe.local.response["supplier_list"] = suppliers

    return columns, data

"""