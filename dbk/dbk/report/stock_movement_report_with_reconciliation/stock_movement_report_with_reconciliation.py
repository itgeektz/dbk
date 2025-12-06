# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, cstr

def execute(filters=None):
    """
    Stock Movement Report - Script Report Version
    Includes Stock Reconciliation
    """
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "posting_date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 90
        },
        {
            "fieldname": "posting_time",
            "label": _("Time"),
            "fieldtype": "Time",
            "width": 80
        },
        {
            "fieldname": "material_request",
            "label": _("Material Request"),
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 130
        },
        {
            "fieldname": "mr_date",
            "label": _("MR Date"),
            "fieldtype": "Date",
            "width": 90
        },
        {
            "fieldname": "voucher_type",
            "label": _("Voucher Type"),
            "fieldtype": "Data",
            "width": 120
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
            "width": 150
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "item_group",
            "label": _("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        },
        {
            "fieldname": "stock_entry_type",
            "label": _("SE Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "source_warehouse",
            "label": _("Source Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "fieldname": "source_opening",
            "label": _("Source Opening"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "out_qty",
            "label": _("Out Qty"),
            "fieldtype": "Float",
            "width": 90
        },
        {
            "fieldname": "source_closing",
            "label": _("Source Closing"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "target_warehouse",
            "label": _("Target Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "fieldname": "target_opening",
            "label": _("Target Opening"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "in_qty",
            "label": _("In Qty"),
            "fieldtype": "Float",
            "width": 90
        },
        {
            "fieldname": "target_closing",
            "label": _("Target Closing"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "uom",
            "label": _("UOM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 60
        },
        {
            "fieldname": "valuation_rate",
            "label": _("Rate"),
            "fieldtype": "Currency",
            "width": 90
        },
        {
            "fieldname": "amount",
            "label": _("Amount"),
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "fieldname": "batch_no",
            "label": _("Batch"),
            "fieldtype": "Link",
            "options": "Batch",
            "width": 100
        },
        {
            "fieldname": "remarks",
            "label": _("Remarks"),
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):
    """
    Main data fetching logic
    Handles all transaction types including Stock Reconciliation
    """
    if not filters:
        filters = {}
    
    # Validate filters
    validate_filters(filters)
    
    conditions = get_conditions(filters)
    
    # Get all stock ledger entries
    sle_data = get_stock_ledger_entries(conditions, filters)
    
    # Get voucher details (Stock Entry, Purchase Receipt, etc.)
    voucher_details = get_voucher_details(sle_data)
    
    # Process and group data
    processed_data = process_stock_movements(sle_data, voucher_details, filters)
    
    return processed_data

def validate_filters(filters):
    """Validate date filters"""
    if not filters.get("from_date"):
        frappe.throw(_("From Date is mandatory"))
    
    if not filters.get("to_date"):
        frappe.throw(_("To Date is mandatory"))
    
    if getdate(filters.get("from_date")) > getdate(filters.get("to_date")):
        frappe.throw(_("From Date cannot be greater than To Date"))

def get_conditions(filters):
    """Build SQL conditions based on filters"""
    conditions = []
    
    if filters.get("from_date"):
        conditions.append("sle.posting_date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("sle.posting_date <= %(to_date)s")
    
    if filters.get("item_code"):
        conditions.append("sle.item_code = %(item_code)s")
    
    if filters.get("item_group"):
        conditions.append("i.item_group = %(item_group)s")
    
    if filters.get("warehouse"):
        conditions.append("sle.warehouse = %(warehouse)s")
    
    if filters.get("voucher_type"):
        conditions.append("sle.voucher_type = %(voucher_type)s")
    
    if filters.get("voucher_no"):
        conditions.append("sle.voucher_no = %(voucher_no)s")
    
    if filters.get("batch_no"):
        conditions.append("sle.batch_no = %(batch_no)s")
    
    # Always exclude cancelled entries
    conditions.append("sle.is_cancelled = 0")
    
    return " AND " + " AND ".join(conditions) if conditions else ""

def get_stock_ledger_entries(conditions, filters):
    """Fetch stock ledger entries with item details"""
    
    query = """
        SELECT 
            sle.posting_date,
            sle.posting_time,
            sle.voucher_type,
            sle.voucher_no,
            sle.voucher_detail_no,
            sle.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            sle.warehouse,
            sle.actual_qty,
            sle.qty_after_transaction,
            sle.incoming_rate as valuation_rate,
            sle.stock_value_difference,
            sle.batch_no,
            sle.serial_no,
            sle.creation
        FROM 
            `tabStock Ledger Entry` sle
            LEFT JOIN `tabItem` i ON sle.item_code = i.name
        WHERE
            sle.docstatus = 1
            {conditions}
        ORDER BY 
            sle.posting_date,
            sle.posting_time,
            sle.creation,
            sle.item_code,
            sle.warehouse
    """.format(conditions=conditions)
    
    return frappe.db.sql(query, filters, as_dict=1)

def get_voucher_details(sle_data):
    """Get additional details from voucher documents"""
    
    voucher_details = {}
    
    # Group by voucher type and numbers
    voucher_map = {}
    for row in sle_data:
        vtype = row.voucher_type
        vno = row.voucher_no
        if vtype not in voucher_map:
            voucher_map[vtype] = set()
        voucher_map[vtype].add(vno)
    
    # Fetch Stock Entry details
    if 'Stock Entry' in voucher_map:
        se_details = frappe.db.sql("""
            SELECT 
                name,
                posting_date as transaction_date,
                stock_entry_type,
                purpose,
                from_warehouse,
                to_warehouse,
                material_request,
                remarks
            FROM 
                `tabStock Entry`
            WHERE 
                name IN ({vouchers})
                AND docstatus = 1
        """.format(vouchers=','.join(['%s']*len(voucher_map['Stock Entry']))),
        tuple(voucher_map['Stock Entry']), as_dict=1)
        
        for se in se_details:
            voucher_details[('Stock Entry', se.name)] = se
    
    # Fetch Purchase Receipt details
    if 'Purchase Receipt' in voucher_map:
        pr_details = frappe.db.sql("""
            SELECT 
                pr.name,
                pr.posting_date as transaction_date,
                pr.supplier as source_warehouse,
                pri.material_request,
                pr.remarks
            FROM 
                `tabPurchase Receipt` pr
                LEFT JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
            WHERE 
                pr.name IN ({vouchers})
                AND pr.docstatus = 1
        """.format(vouchers=','.join(['%s']*len(voucher_map['Purchase Receipt']))),
        tuple(voucher_map['Purchase Receipt']), as_dict=1)
        
        for pr in pr_details:
            voucher_details[('Purchase Receipt', pr.name)] = pr
    
    # Fetch Purchase Invoice details
    if 'Purchase Invoice' in voucher_map:
        pi_details = frappe.db.sql("""
            SELECT 
                pi.name,
                pi.posting_date as transaction_date,
                pi.supplier as source_warehouse,
                pii.material_request,
                pi.remarks
            FROM 
                `tabPurchase Invoice` pi
                LEFT JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
            WHERE 
                pi.name IN ({vouchers})
                AND pi.docstatus = 1
                AND pi.update_stock = 1
        """.format(vouchers=','.join(['%s']*len(voucher_map['Purchase Invoice']))),
        tuple(voucher_map['Purchase Invoice']), as_dict=1)
        
        for pi in pi_details:
            voucher_details[('Purchase Invoice', pi.name)] = pi
    
    # Fetch Delivery Note details
    if 'Delivery Note' in voucher_map:
        dn_details = frappe.db.sql("""
            SELECT 
                name,
                posting_date as transaction_date,
                customer as target_warehouse,
                remarks
            FROM 
                `tabDelivery Note`
            WHERE 
                name IN ({vouchers})
                AND docstatus = 1
        """.format(vouchers=','.join(['%s']*len(voucher_map['Delivery Note']))),
        tuple(voucher_map['Delivery Note']), as_dict=1)
        
        for dn in dn_details:
            voucher_details[('Delivery Note', dn.name)] = dn
    
    # Fetch Sales Invoice details
    if 'Sales Invoice' in voucher_map:
        si_details = frappe.db.sql("""
            SELECT 
                name,
                posting_date as transaction_date,
                customer as target_warehouse,
                remarks
            FROM 
                `tabSales Invoice`
            WHERE 
                name IN ({vouchers})
                AND docstatus = 1
                AND update_stock = 1
        """.format(vouchers=','.join(['%s']*len(voucher_map['Sales Invoice']))),
        tuple(voucher_map['Sales Invoice']), as_dict=1)
        
        for si in si_details:
            voucher_details[('Sales Invoice', si.name)] = si
    
    # Fetch Stock Reconciliation details
    if 'Stock Reconciliation' in voucher_map:
        sr_details = frappe.db.sql("""
            SELECT 
                name,
                posting_date as transaction_date,
                purpose,
                remarks
            FROM 
                `tabStock Reconciliation`
            WHERE 
                name IN ({vouchers})
                AND docstatus = 1
        """.format(vouchers=','.join(['%s']*len(voucher_map['Stock Reconciliation']))),
        tuple(voucher_map['Stock Reconciliation']), as_dict=1)
        
        for sr in sr_details:
            voucher_details[('Stock Reconciliation', sr.name)] = sr
    
    # Fetch Material Request details (for linking)
    material_requests = set()
    for details in voucher_details.values():
        if details.get('material_request'):
            material_requests.add(details.get('material_request'))
    
    if material_requests:
        mr_details = frappe.db.sql("""
            SELECT 
                name,
                transaction_date
            FROM 
                `tabMaterial Request`
            WHERE 
                name IN ({mrs})
        """.format(mrs=','.join(['%s']*len(material_requests))),
        tuple(material_requests), as_dict=1)
        
        mr_dates = {mr.name: mr.transaction_date for mr in mr_details}
        
        # Add MR dates to voucher details
        for key, details in voucher_details.items():
            if details.get('material_request'):
                details['mr_date'] = mr_dates.get(details.get('material_request'))
    
    return voucher_details

def process_stock_movements(sle_data, voucher_details, filters):
    """
    Process stock ledger entries into report format
    Groups movements by voucher and shows source/target
    """
    
    result = []
    
    # Group by voucher
    voucher_groups = {}
    for row in sle_data:
        key = (row.voucher_type, row.voucher_no, row.item_code)
        if key not in voucher_groups:
            voucher_groups[key] = []
        voucher_groups[key].append(row)
    
    # Process each voucher group
    for (vtype, vno, item_code), entries in voucher_groups.items():
        
        # Get voucher details
        voucher_info = voucher_details.get((vtype, vno), {})
        
        # Handle different voucher types
        if vtype == 'Stock Entry':
            result.extend(process_stock_entry(entries, voucher_info, filters))
        
        elif vtype == 'Stock Reconciliation':
            result.extend(process_stock_reconciliation(entries, voucher_info, filters))
        
        elif vtype in ['Purchase Receipt', 'Purchase Invoice']:
            result.extend(process_purchase_entry(entries, voucher_info, filters))
        
        elif vtype in ['Delivery Note', 'Sales Invoice']:
            result.extend(process_delivery_entry(entries, voucher_info, filters))
        
        else:
            # Generic processing for other types
            result.extend(process_generic_entry(entries, voucher_info, filters))
    
    # Apply additional filtering
    result = apply_post_filters(result, filters)
    
    return result

def apply_post_filters(data, filters):
    """Apply filters that need to be checked after processing"""
    
    filtered_data = []
    
    for row in data:
        # Filter by source warehouse
        if filters.get("source_warehouse"):
            if row.get("source_warehouse") != filters.get("source_warehouse"):
                continue
        
        # Filter by target warehouse
        if filters.get("target_warehouse"):
            if row.get("target_warehouse") != filters.get("target_warehouse"):
                continue
        
        # Filter by stock entry type
        if filters.get("stock_entry_type"):
            if row.get("stock_entry_type") != filters.get("stock_entry_type"):
                continue
        
        # Filter by material request
        if filters.get("material_request"):
            if row.get("material_request") != filters.get("material_request"):
                continue
        
        # Filter zero balance items
        if not filters.get("show_zero_balance"):
            if (flt(row.get("in_qty")) == 0 and flt(row.get("out_qty")) == 0):
                continue
        
        filtered_data.append(row)
    
    return filtered_data

def process_stock_entry(entries, voucher_info, filters):
    """Process Stock Entry movements"""
    
    rows = []
    se_type = voucher_info.get('stock_entry_type', '')
    material_request = voucher_info.get('material_request', '')
    
    # Separate source and target entries
    source_entries = [e for e in entries if flt(e.actual_qty) < 0]
    target_entries = [e for e in entries if flt(e.actual_qty) > 0]
    
    # For transfers, pair source and target
    if se_type in ['Material Transfer', 'Material Transfer for Manufacture']:
        # Create paired rows
        for s_entry in source_entries:
            # Find matching target entry
            t_entry = next((t for t in target_entries 
                          if t.item_code == s_entry.item_code), None)
            
            row = {
                'posting_date': s_entry.posting_date,
                'posting_time': s_entry.posting_time,
                'material_request': material_request,
                'mr_date': voucher_info.get('mr_date'),
                'voucher_type': s_entry.voucher_type,
                'voucher_no': s_entry.voucher_no,
                'item_code': s_entry.item_code,
                'item_name': s_entry.item_name,
                'item_group': s_entry.item_group,
                'stock_entry_type': se_type,
                'source_warehouse': s_entry.warehouse,
                'source_opening': flt(s_entry.qty_after_transaction) + abs(flt(s_entry.actual_qty)),
                'out_qty': abs(flt(s_entry.actual_qty)),
                'source_closing': flt(s_entry.qty_after_transaction),
                'target_warehouse': t_entry.warehouse if t_entry else '',
                'target_opening': flt(t_entry.qty_after_transaction) - flt(t_entry.actual_qty) if t_entry else 0,
                'in_qty': flt(t_entry.actual_qty) if t_entry else 0,
                'target_closing': flt(t_entry.qty_after_transaction) if t_entry else 0,
                'uom': s_entry.uom,
                'valuation_rate': flt(s_entry.valuation_rate),
                'amount': abs(flt(s_entry.stock_value_difference)),
                'batch_no': s_entry.batch_no,
                'remarks': voucher_info.get('remarks', '')
            }
            rows.append(row)
    
    elif se_type == 'Material Receipt':
        # Only incoming entries
        for t_entry in target_entries:
            row = {
                'posting_date': t_entry.posting_date,
                'posting_time': t_entry.posting_time,
                'material_request': material_request,
                'mr_date': voucher_info.get('mr_date'),
                'voucher_type': t_entry.voucher_type,
                'voucher_no': t_entry.voucher_no,
                'item_code': t_entry.item_code,
                'item_name': t_entry.item_name,
                'item_group': t_entry.item_group,
                'stock_entry_type': se_type,
                'source_warehouse': '',
                'source_opening': 0,
                'out_qty': 0,
                'source_closing': 0,
                'target_warehouse': t_entry.warehouse,
                'target_opening': flt(t_entry.qty_after_transaction) - flt(t_entry.actual_qty),
                'in_qty': flt(t_entry.actual_qty),
                'target_closing': flt(t_entry.qty_after_transaction),
                'uom': t_entry.uom,
                'valuation_rate': flt(t_entry.valuation_rate),
                'amount': flt(t_entry.stock_value_difference),
                'batch_no': t_entry.batch_no,
                'remarks': voucher_info.get('remarks', '')
            }
            rows.append(row)
    
    elif se_type in ['Material Issue', 'Material Consumption for Manufacture']:
        # Only outgoing entries
        for s_entry in source_entries:
            row = {
                'posting_date': s_entry.posting_date,
                'posting_time': s_entry.posting_time,
                'material_request': material_request,
                'mr_date': voucher_info.get('mr_date'),
                'voucher_type': s_entry.voucher_type,
                'voucher_no': s_entry.voucher_no,
                'item_code': s_entry.item_code,
                'item_name': s_entry.item_name,
                'item_group': s_entry.item_group,
                'stock_entry_type': se_type,
                'source_warehouse': s_entry.warehouse,
                'source_opening': flt(s_entry.qty_after_transaction) + abs(flt(s_entry.actual_qty)),
                'out_qty': abs(flt(s_entry.actual_qty)),
                'source_closing': flt(s_entry.qty_after_transaction),
                'target_warehouse': '',
                'target_opening': 0,
                'in_qty': 0,
                'target_closing': 0,
                'uom': s_entry.uom,
                'valuation_rate': flt(s_entry.valuation_rate),
                'amount': abs(flt(s_entry.stock_value_difference)),
                'batch_no': s_entry.batch_no,
                'remarks': voucher_info.get('remarks', '')
            }
            rows.append(row)
    
    else:
        # Manufacture, Repack, etc. - show both sides
        for entry in entries:
            is_outgoing = flt(entry.actual_qty) < 0
            row = {
                'posting_date': entry.posting_date,
                'posting_time': entry.posting_time,
                'material_request': material_request,
                'mr_date': voucher_info.get('mr_date'),
                'voucher_type': entry.voucher_type,
                'voucher_no': entry.voucher_no,
                'item_code': entry.item_code,
                'item_name': entry.item_name,
                'item_group': entry.item_group,
                'stock_entry_type': se_type,
                'source_warehouse': entry.warehouse if is_outgoing else '',
                'source_opening': flt(entry.qty_after_transaction) + abs(flt(entry.actual_qty)) if is_outgoing else 0,
                'out_qty': abs(flt(entry.actual_qty)) if is_outgoing else 0,
                'source_closing': flt(entry.qty_after_transaction) if is_outgoing else 0,
                'target_warehouse': entry.warehouse if not is_outgoing else '',
                'target_opening': flt(entry.qty_after_transaction) - flt(entry.actual_qty) if not is_outgoing else 0,
                'in_qty': flt(entry.actual_qty) if not is_outgoing else 0,
                'target_closing': flt(entry.qty_after_transaction) if not is_outgoing else 0,
                'uom': entry.uom,
                'valuation_rate': flt(entry.valuation_rate),
                'amount': abs(flt(entry.stock_value_difference)),
                'batch_no': entry.batch_no,
                'remarks': voucher_info.get('remarks', '')
            }
            rows.append(row)
    
    return rows

def process_stock_reconciliation(entries, voucher_info, filters):
    """Process Stock Reconciliation - shows adjustment"""
    
    rows = []
    
    for entry in entries:
        # Calculate what the qty was before reconciliation
        previous_qty = flt(entry.qty_after_transaction) - flt(entry.actual_qty)
        adjustment_qty = flt(entry.actual_qty)
        
        row = {
            'posting_date': entry.posting_date,
            'posting_time': entry.posting_time,
            'material_request': '',
            'mr_date': None,
            'voucher_type': entry.voucher_type,
            'voucher_no': entry.voucher_no,
            'item_code': entry.item_code,
            'item_name': entry.item_name,
            'item_group': entry.item_group,
            'stock_entry_type': 'Stock Reconciliation',
            'source_warehouse': entry.warehouse if adjustment_qty < 0 else '',
            'source_opening': previous_qty if adjustment_qty < 0 else 0,
            'out_qty': abs(adjustment_qty) if adjustment_qty < 0 else 0,
            'source_closing': flt(entry.qty_after_transaction) if adjustment_qty < 0 else 0,
            'target_warehouse': entry.warehouse if adjustment_qty > 0 else '',
            'target_opening': previous_qty if adjustment_qty > 0 else 0,
            'in_qty': adjustment_qty if adjustment_qty > 0 else 0,
            'target_closing': flt(entry.qty_after_transaction) if adjustment_qty > 0 else 0,
            'uom': entry.uom,
            'valuation_rate': flt(entry.valuation_rate),
            'amount': abs(flt(entry.stock_value_difference)),
            'batch_no': entry.batch_no,
            'remarks': f"Reconciliation: {voucher_info.get('purpose', '')} - {voucher_info.get('remarks', '')}"
        }
        rows.append(row)
    
    return rows

def process_purchase_entry(entries, voucher_info, filters):
    """Process Purchase Receipt/Invoice"""
    
    rows = []
    material_request = voucher_info.get('material_request', '')
    
    for entry in entries:
        row = {
            'posting_date': entry.posting_date,
            'posting_time': entry.posting_time,
            'material_request': material_request,
            'mr_date': voucher_info.get('mr_date'),
            'voucher_type': entry.voucher_type,
            'voucher_no': entry.voucher_no,
            'item_code': entry.item_code,
            'item_name': entry.item_name,
            'item_group': entry.item_group,
            'stock_entry_type': 'Purchase',
            'source_warehouse': voucher_info.get('source_warehouse', ''),
            'source_opening': 0,
            'out_qty': 0,
            'source_closing': 0,
            'target_warehouse': entry.warehouse,
            'target_opening': flt(entry.qty_after_transaction) - flt(entry.actual_qty),
            'in_qty': flt(entry.actual_qty),
            'target_closing': flt(entry.qty_after_transaction),
            'uom': entry.uom,
            'valuation_rate': flt(entry.valuation_rate),
            'amount': flt(entry.stock_value_difference),
            'batch_no': entry.batch_no,
            'remarks': voucher_info.get('remarks', '')
        }
        rows.append(row)
    
    return rows

def process_delivery_entry(entries, voucher_info, filters):
    """Process Delivery Note/Sales Invoice"""
    
    rows = []
    
    for entry in entries:
        row = {
            'posting_date': entry.posting_date,
            'posting_time': entry.posting_time,
            'material_request': '',
            'mr_date': None,
            'voucher_type': entry.voucher_type,
            'voucher_no': entry.voucher_no,
            'item_code': entry.item_code,
            'item_name': entry.item_name,
            'item_group': entry.item_group,
            'stock_entry_type': 'Delivery',
            'source_warehouse': entry.warehouse,
            'source_opening': flt(entry.qty_after_transaction) + abs(flt(entry.actual_qty)),
            'out_qty': abs(flt(entry.actual_qty)),
            'source_closing': flt(entry.qty_after_transaction),
            'target_warehouse': voucher_info.get('target_warehouse', ''),
            'target_opening': 0,
            'in_qty': 0,
            'target_closing': 0,
            'uom': entry.uom,
            'valuation_rate': flt(entry.valuation_rate),
            'amount': abs(flt(entry.stock_value_difference)),
            'batch_no': entry.batch_no,
            'remarks': voucher_info.get('remarks', '')
        }
        rows.append(row)
    
    return rows

def process_generic_entry(entries, voucher_info, filters):
    """Process any other voucher types"""
    
    rows = []
    
    for entry in entries:
        is_outgoing = flt(entry.actual_qty) < 0
        
        row = {
            'posting_date': entry.posting_date,
            'posting_time': entry.posting_time,
            'material_request': '',
            'mr_date': None,
            'voucher_type': entry.voucher_type,
            'voucher_no': entry.voucher_no,
            'item_code': entry.item_code,
            'item_name': entry.item_name,
            'item_group': entry.item_group,
            'stock_entry_type': '',
            'source_warehouse': entry.warehouse if is_outgoing else '',
            'source_opening': flt(entry.qty_after_transaction) + abs(flt(entry.actual_qty)) if is_outgoing else 0,
            'out_qty': abs(flt(entry.actual_qty)) if is_outgoing else 0,
            'source_closing': flt(entry.qty_after_transaction) if is_outgoing else 0,
            'target_warehouse': entry.warehouse if not is_outgoing else '',
            'target_opening': flt(entry.qty_after_transaction) - flt(entry.actual_qty) if not is_outgoing else 0,
            'in_qty': flt(entry.actual_qty) if not is_outgoing else 0,
            'target_closing': flt(entry.qty_after_transaction) if not is_outgoing else 0,
            'uom': entry.uom,
            'valuation_rate': flt(entry.valuation_rate),
            'amount': abs(flt(entry.stock_value_difference)),
            'batch_no': entry.batch_no,
            'remarks': voucher_info.get('remarks', '')
        }
        rows.append(row)
    
    return rows