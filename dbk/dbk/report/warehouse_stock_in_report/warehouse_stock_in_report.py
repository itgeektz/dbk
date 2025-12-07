# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = [
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "posting_time",
            "label": _("Posting Time"),
            "fieldtype": "Time",
            "width": 90
        },
        {
            "fieldname": "voucher_type",
            "label": _("Voucher Type"),
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "voucher_no",
            "label": _("Voucher No"),
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 150
        },
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 130
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "item_group",
            "label": _("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        },
        {
            "fieldname": "warehouse",
            "label": _("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 130
        },
        {
            "fieldname": "qty",
            "label": _("Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "uom",
            "label": _("UOM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "fieldname": "stock_uom",
            "label": _("Stock UOM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 90
        },
        {
            "fieldname": "stock_qty",
            "label": _("Stock Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "valuation_rate",
            "label": _("Valuation Rate"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "amount",
            "label": _("Amount"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "batch_no",
            "label": _("Batch No"),
            "fieldtype": "Link",
            "options": "Batch",
            "width": 100
        },
        {
            "fieldname": "serial_no",
            "label": _("Serial No"),
            "fieldtype": "Small Text",
            "width": 150
        },
        {
            "fieldname": "stock_entry_type",
            "label": _("Stock Entry Type"),
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "supplier",
            "label": _("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 130
        },
        {
            "fieldname": "purchase_order",
            "label": _("Purchase Order"),
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 130
        },
        {
            "fieldname": "material_request",
            "label": _("Material Request"),
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 130
        },
        {
            "fieldname": "supplier_quotation",
            "label": _("Supplier Quotation"),
            "fieldtype": "Link",
            "options": "Supplier Quotation",
            "width": 140
        },
        {
            "fieldname": "rfq",
            "label": _("Request for Quotation"),
            "fieldtype": "Link",
            "options": "Request for Quotation",
            "width": 150
        },
        {
            "fieldname": "project",
            "label": _("Project"),
            "fieldtype": "Link",
            "options": "Project",
            "width": 120
        },
        {
            "fieldname": "remarks",
            "label": _("Remarks"),
            "fieldtype": "Small Text",
            "width": 200
        }
    ]
    return columns

def get_data(filters):
    data = []
    
    # Get Stock Entry data (Material Receipt, Material Transfer, Manufacture, Repack)
    stock_entry_data = get_stock_entry_data(filters)
    data.extend(stock_entry_data)
    
    # Get Purchase Receipt data
    purchase_receipt_data = get_purchase_receipt_data(filters)
    data.extend(purchase_receipt_data)
    
    # Get Stock Reconciliation data (where qty difference is positive)
    stock_recon_data = get_stock_reconciliation_data(filters)
    data.extend(stock_recon_data)
    
    # Sort by posting date and time
    data = sorted(data, key=lambda x: (x.get('posting_date', ''), x.get('posting_time', '')), reverse=True)
    
    return data

def get_stock_entry_data(conditions, filters):
    """Get stock entries where stock is coming IN to warehouse"""
    
    stock_entry_types = []
    if filters.get("stock_entry_type"):
        stock_entry_types = [filters.get("stock_entry_type")]
    else:
        # Stock Entry Types that bring stock IN
        stock_entry_types = [
            'Material Receipt',
            'Material Transfer',
            'Manufacture',
            'Repack'
        ]
    
    # Build type condition using tuple format for frappe
    type_condition = ""
    if stock_entry_types:
        types_tuple = tuple(stock_entry_types)
        type_condition = f" AND se.stock_entry_type IN {types_tuple}"
    
    query = f"""
        SELECT
            se.posting_date,
            se.posting_time,
            'Stock Entry' as voucher_type,
            se.name as voucher_no,
            sed.item_code,
            sed.item_name,
            sed.item_group,
            sed.t_warehouse as warehouse,
            sed.qty,
            sed.uom,
            sed.stock_uom,
            sed.transfer_qty as stock_qty,
            sed.valuation_rate,
            sed.amount,
            sed.batch_no,
            sed.serial_no,
            se.stock_entry_type,
            NULL as supplier,
            se.purchase_order,
            sed.material_request,
            NULL as supplier_quotation,
            NULL as rfq,
            se.project,
            se.remarks
        FROM
            `tabStock Entry` se
        INNER JOIN
            `tabStock Entry Detail` sed ON se.name = sed.parent
        WHERE
            se.docstatus = 1
            AND sed.t_warehouse IS NOT NULL
            AND sed.t_warehouse != ''
            AND se.company = %(company)s
    """
    
    # Add optional conditions
    if filters.get("from_date"):
        query += " AND se.posting_date >= %(from_date)s"
    
    if filters.get("to_date"):
        query += " AND se.posting_date <= %(to_date)s"
    
    if filters.get("warehouse"):
        query += " AND sed.t_warehouse = %(warehouse)s"
    
    if filters.get("item_code"):
        query += " AND sed.item_code = %(item_code)s"
    
    if filters.get("item_group"):
        query += " AND sed.item_group = %(item_group)s"
    
    query += type_condition
    
    data = frappe.db.sql(query, filters, as_dict=1)
    
    # Get linked Material Request and other details
    for row in data:
        if row.get('material_request'):
            mr_details = frappe.db.get_value('Material Request', 
                row['material_request'], 
                ['supplier_quotation'], as_dict=1)
            if mr_details:
                row['supplier_quotation'] = mr_details.get('supplier_quotation')
    
    return data

def get_purchase_receipt_data(filters):
    """Get purchase receipt data"""
    
    query = """
        SELECT
            pr.posting_date,
            pr.posting_time,
            'Purchase Receipt' as voucher_type,
            pr.name as voucher_no,
            pri.item_code,
            pri.item_name,
            pri.item_group,
            pri.warehouse,
            pri.qty,
            pri.uom,
            pri.stock_uom,
            pri.stock_qty,
            pri.valuation_rate,
            pri.amount,
            pri.batch_no,
            pri.serial_no,
            NULL as stock_entry_type,
            pr.supplier,
            pri.purchase_order,
            pri.material_request,
            pri.supplier_quotation,
            NULL as rfq,
            pri.project,
            pr.remarks
        FROM
            `tabPurchase Receipt` pr
        INNER JOIN
            `tabPurchase Receipt Item` pri ON pr.name = pri.parent
        WHERE
            pr.docstatus = 1
            AND pri.warehouse IS NOT NULL
            AND pr.company = %(company)s
    """
    
    # Add optional conditions
    if filters.get("from_date"):
        query += " AND pr.posting_date >= %(from_date)s"
    
    if filters.get("to_date"):
        query += " AND pr.posting_date <= %(to_date)s"
    
    if filters.get("warehouse"):
        query += " AND pri.warehouse = %(warehouse)s"
    
    if filters.get("item_code"):
        query += " AND pri.item_code = %(item_code)s"
    
    if filters.get("item_group"):
        query += " AND pri.item_group = %(item_group)s"
    
    if filters.get("supplier"):
        query += " AND pr.supplier = %(supplier)s"
    
    data = frappe.db.sql(query, filters, as_dict=1)
    
    # Get RFQ from Purchase Order or Supplier Quotation
    for row in data:
        if row.get('supplier_quotation'):
            rfq = frappe.db.get_value('Supplier Quotation', 
                row['supplier_quotation'], 'request_for_quotation')
            row['rfq'] = rfq
        elif row.get('purchase_order'):
            # Get RFQ from PO through Supplier Quotation
            sq = frappe.db.sql("""
                SELECT sq.name, sq.request_for_quotation
                FROM `tabSupplier Quotation` sq
                INNER JOIN `tabSupplier Quotation Item` sqi ON sq.name = sqi.parent
                WHERE sqi.purchase_order = %s
                LIMIT 1
            """, row['purchase_order'], as_dict=1)
            if sq:
                row['supplier_quotation'] = sq[0].name
                row['rfq'] = sq[0].request_for_quotation
    
    return data

def get_stock_reconciliation_data(filters):
    """Get stock reconciliation data where quantity increased"""
    
    query = """
        SELECT
            sr.posting_date,
            sr.posting_time,
            'Stock Reconciliation' as voucher_type,
            sr.name as voucher_no,
            sri.item_code,
            sri.item_name,
            i.item_group,
            sri.warehouse,
            (sri.qty - sri.current_qty) as qty,
            i.stock_uom as uom,
            i.stock_uom as stock_uom,
            (sri.qty - sri.current_qty) as stock_qty,
            sri.valuation_rate,
            ((sri.qty - sri.current_qty) * sri.valuation_rate) as amount,
            sri.batch_no,
            sri.serial_no,
            NULL as stock_entry_type,
            NULL as supplier,
            NULL as purchase_order,
            NULL as material_request,
            NULL as supplier_quotation,
            NULL as rfq,
            NULL as project,
            sr.remarks
        FROM
            `tabStock Reconciliation` sr
        INNER JOIN
            `tabStock Reconciliation Item` sri ON sr.name = sri.parent
        LEFT JOIN
            `tabItem` i ON sri.item_code = i.name
        WHERE
            sr.docstatus = 1
            AND (sri.qty - sri.current_qty) > 0
            AND sr.company = %(company)s
    """
    
    # Add optional conditions
    if filters.get("from_date"):
        query += " AND sr.posting_date >= %(from_date)s"
    
    if filters.get("to_date"):
        query += " AND sr.posting_date <= %(to_date)s"
    
    if filters.get("warehouse"):
        query += " AND sri.warehouse = %(warehouse)s"
    
    if filters.get("item_code"):
        query += " AND sri.item_code = %(item_code)s"
    
    if filters.get("item_group"):
        query += " AND i.item_group = %(item_group)s"
    
    data = frappe.db.sql(query, filters, as_dict=1)
    
    return data