# Copyright (c) 2025, Enest and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class RFQMeeting(Document):
    def validate(self):
        # Fetch RFQ details
        if self.request_for_quotation:
            rfq = frappe.get_doc("Request for Quotation", self.request_for_quotation)
            
            # Set default company if not set
            if not self.company:
                self.company = rfq.company
            
            # Set default required date from RFQ schedule date
            if not self.required_date and rfq.schedule_date:
                self.required_date = rfq.schedule_date
            
            # Set default project from RFQ
            if not self.project and hasattr(rfq, 'project') and rfq.project:
                self.project = rfq.project
            
            # Load items if not already loaded
            if not self.item_selections:
                self.load_rfq_items()
    
    def load_rfq_items(self):
        """Load items from RFQ with supplier quotations"""
        if not self.request_for_quotation:
            frappe.log_error("No RFQ provided", "load_rfq_items")
            return
        
        # Get RFQ items
        rfq_items = frappe.get_all(
            "Request for Quotation Item",
            filters={"parent": self.request_for_quotation},
            fields=["item_code", "item_name", "qty", "uom"],
            order_by="idx"
        )
        
        if not rfq_items:
            frappe.log_error(f"No items found for RFQ: {self.request_for_quotation}", "load_rfq_items")
            return
        
        # Get supplier quotations linked to this RFQ
        sq_list = frappe.db.sql("""
            SELECT DISTINCT sq.name, sq.supplier, sq.supplier_name
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sqi.request_for_quotation = %s
            AND sq.docstatus = 1
        """, (self.request_for_quotation,), as_dict=True)
        
        if not sq_list:
            frappe.msgprint(f"No submitted Supplier Quotations found for RFQ: {self.request_for_quotation}")
            return
        
        # For each item, find available suppliers and lowest bidder
        items_added = 0
        for item in rfq_items:
            suppliers_data = []
            lowest_rate = None
            lowest_supplier_code = None
            lowest_sq = None
            
            for sq in sq_list:
                # Get rate for this item from this supplier
                sq_item = frappe.db.get_value(
                    "Supplier Quotation Item",
                    {
                        "parent": sq.name,
                        "item_code": item.item_code
                    },
                    ["rate", "net_rate"],
                    as_dict=True
                )
                
                if sq_item and (sq_item.net_rate or sq_item.rate):
                    # Use net_rate for comparison if available
                    comparison_rate = float(sq_item.net_rate) if sq_item.net_rate else float(sq_item.rate)
                    display_rate = float(sq_item.rate) if sq_item.rate else comparison_rate
                    
                    suppliers_data.append({
                        "supplier": sq.supplier,
                        "supplier_name": sq.supplier_name or sq.supplier,
                        "rate": comparison_rate,
                        "display_rate": display_rate,
                        "sq_name": sq.name
                    })
                    
                    if lowest_rate is None or comparison_rate < lowest_rate:
                        lowest_rate = comparison_rate
                        lowest_supplier_code = sq.supplier
                        lowest_sq = sq.name
            
            # Add row to item selections only if suppliers found
            if suppliers_data:
                # Sort suppliers by rate (lowest first)
                suppliers_data.sort(key=lambda x: x['rate'])
                
                # Format available suppliers list with rates
                supplier_options = "\n".join([
                    f"{s['supplier_name']} (Rate: {s['display_rate']:,.2f})" 
                    for s in suppliers_data
                ])
                
                # CRITICAL: Append with all fields including available_suppliers
                new_row = self.append("item_selections", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "qty": item.qty,
                    "uom": item.uom,
                    "selected_supplier": lowest_supplier_code,
                    "supplier_quotation": lowest_sq,
                    "quoted_rate": lowest_rate,
                    "available_suppliers": supplier_options  # THIS IS CRITICAL
                })
                
                items_added += 1
                
                # Debug log
                frappe.log_error(
                    f"Added item: {item.item_code}\n"
                    f"Lowest supplier: {lowest_supplier_code}\n"
                    f"Rate: {lowest_rate}\n"
                    f"Available suppliers:\n{supplier_options}",
                    "load_rfq_items - Item Added"
                )
        
        frappe.msgprint(f"Loaded {items_added} items with supplier quotations")
    
    def on_submit(self):
        """Create purchase orders when meeting is submitted"""
        if not self.item_selections:
            frappe.throw("Please select suppliers for items before submitting")
        
        # Group items by supplier
        supplier_items = {}
        for item in self.item_selections:
            if not item.selected_supplier:
                continue
            
            if item.selected_supplier not in supplier_items:
                supplier_items[item.selected_supplier] = []
            
            supplier_items[item.selected_supplier].append(item)
        
        # Create POs
        created_pos = []
        for supplier_name, items in supplier_items.items():
            po = self.create_purchase_order(supplier_name, items)
            if po:
                created_pos.append(po.name)
        
        if created_pos:
            frappe.msgprint(
                f"Created Purchase Orders: {', '.join(created_pos)}",
                title="Purchase Orders Created",
                indicator="green"
            )
    
    def create_purchase_order(self, supplier_name, items):
        """Create a purchase order for given supplier and items"""
        # Find supplier quotation - get the actual supplier code
        sq = frappe.db.sql("""
            SELECT sq.name, sq.supplier, sq.supplier_name
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sqi.request_for_quotation = %s
            AND (sq.supplier_name = %s OR sq.supplier = %s)
            AND sq.docstatus = 1
            LIMIT 1
        """, (self.request_for_quotation, supplier_name, supplier_name), as_dict=True)
        
        if not sq:
            frappe.msgprint(f"No supplier quotation found for {supplier_name}")
            return None
        
        # Create PO
        po = frappe.new_doc("Purchase Order")
        po.supplier = sq[0].supplier
        po.company = self.company
        po.schedule_date = self.required_date
        po.project = self.project
        
        # Add custom field references if they exist
        if frappe.db.exists("Custom Field", {"dt": "Purchase Order", "fieldname": "rfq_meeting"}):
            po.rfq_meeting = self.name
        
        if frappe.db.exists("Custom Field", {"dt": "Purchase Order", "fieldname": "request_for_quotation"}):
            po.request_for_quotation = self.request_for_quotation
        
        # Add items
        for item in items:
            sq_name = item.supplier_quotation if item.supplier_quotation else None
            
            if not sq_name:
                sq_lookup = frappe.db.sql("""
                    SELECT sq.name
                    FROM `tabSupplier Quotation` sq
                    INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
                    WHERE sqi.request_for_quotation = %s
                    AND (sq.supplier_name = %s OR sq.supplier = %s)
                    AND sqi.item_code = %s
                    AND sq.docstatus = 1
                    ORDER BY sq.transaction_date DESC
                    LIMIT 1
                """, (self.request_for_quotation, supplier_name, supplier_name, item.item_code), as_dict=True)
                
                if sq_lookup:
                    sq_name = sq_lookup[0].name
                else:
                    sq_name = sq[0].name
            
            sq_item = frappe.db.get_value(
                "Supplier Quotation Item",
                {
                    "parent": sq_name,
                    "item_code": item.item_code
                },
                ["rate", "net_rate", "warehouse", "description"],
                as_dict=True
            )
            
            if sq_item:
                warehouse = sq_item.warehouse or frappe.db.get_value(
                    "Warehouse",
                    {"company": self.company, "is_group": 0},
                    "name"
                )
                
                if sq_item.net_rate:
                    rate = sq_item.net_rate
                elif hasattr(item, 'quoted_rate') and item.quoted_rate:
                    rate = item.quoted_rate
                else:
                    rate = sq_item.rate
                
                po_item = po.append("items", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "description": sq_item.description or item.item_name,
                    "qty": item.qty,
                    "rate": rate,
                    "uom": item.uom,
                    "warehouse": warehouse,
                    "schedule_date": self.required_date,
                    "project": self.project
                })
                
                try:
                    po_item.supplier_quotation = sq_name
                except Exception as e:
                    frappe.log_error(
                        f"Could not set supplier_quotation on PO item: {str(e)}",
                        "Supplier Quotation Reference Error"
                    )
                
                try:
                    po_item.rfq_meeting = self.name
                except:
                    pass
        
        po.insert()
        frappe.db.commit()
        
        return po


# ============================================================================
# WHITELISTED METHODS
# ============================================================================

@frappe.whitelist()
def get_rfq_comparison_data(rfq):
    """Get comparison data for print format"""
    from dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson import execute
    
    filters = {"request_for_quotation": rfq}
    columns, data, summary, schedule_date = execute(filters)
    
    return {
        "columns": columns,
        "data": data,
        "summary": summary,
        "schedule_date": schedule_date
    }


@frappe.whitelist()
def get_supplier_quotation_for_item(rfq, supplier, item_code):
    """
    Get the Supplier Quotation reference for a specific item from a specific supplier
    """
    try:
        sq_data = frappe.db.sql("""
            SELECT 
                sq.name as supplier_quotation,
                sq.supplier,
                sq.supplier_name,
                sqi.item_code,
                sqi.qty,
                sqi.rate,
                sqi.net_rate,
                sqi.amount,
                sqi.uom,
                sq.transaction_date,
                sq.valid_till
            FROM 
                `tabSupplier Quotation` sq
            INNER JOIN 
                `tabSupplier Quotation Item` sqi ON sq.name = sqi.parent
            WHERE 
                sqi.request_for_quotation = %(rfq)s
                AND (sq.supplier_name = %(supplier)s OR sq.supplier = %(supplier)s)
                AND sqi.item_code = %(item_code)s
                AND sq.docstatus = 1
            ORDER BY 
                sq.transaction_date DESC
            LIMIT 1
        """, {
            'rfq': rfq,
            'supplier': supplier,
            'item_code': item_code
        }, as_dict=True)
        
        if sq_data:
            result = sq_data[0]
            # Use net_rate if available, otherwise rate
            result['rate'] = result.get('net_rate') or result.get('rate')
            return result
        else:
            frappe.log_error(
                f"No Supplier Quotation found for RFQ: {rfq}, Supplier: {supplier}, Item: {item_code}",
                "Supplier Quotation Not Found"
            )
            return None
            
    except Exception as e:
        frappe.log_error(
            f"Error fetching supplier quotation: {str(e)}",
            "Get Supplier Quotation Error"
        )
        return None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_suppliers_for_item(doctype, txt, searchfield, start, page_len, filters):
    """
    Query function to get list of suppliers who have submitted quotations
    for a specific item in the given RFQ
    """
    rfq = filters.get('request_for_quotation')
    item_code = filters.get('item_code')
    
    if not rfq or not item_code:
        frappe.log_error(
            f"Missing filters: rfq={rfq}, item_code={item_code}",
            "get_suppliers_for_item - Missing Filters"
        )
        return []
    
    # Build search condition
    search_condition = ""
    if txt:
        search_condition = "AND (sq.supplier LIKE %(txt)s OR sq.supplier_name LIKE %(txt)s)"
    
    try:
        suppliers = frappe.db.sql("""
            SELECT DISTINCT 
                sq.supplier,
                sq.supplier_name,
                sqi.rate as quoted_rate,
                sqi.net_rate,
                sq.name as quotation_ref
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sqi.request_for_quotation = %(rfq)s
            AND sqi.item_code = %(item_code)s
            AND sq.docstatus = 1
            {search_condition}
            ORDER BY COALESCE(sqi.net_rate, sqi.rate) ASC
            LIMIT %(page_len)s OFFSET %(start)s
        """.format(search_condition=search_condition), {
            'rfq': rfq,
            'item_code': item_code,
            'txt': f'%{txt}%' if txt else '%',
            'start': start,
            'page_len': page_len
        }, as_dict=True)
        
        results = []
        for supplier in suppliers:
            supplier_display = supplier.supplier_name or supplier.supplier
            rate = supplier.net_rate or supplier.quoted_rate
            
            if rate:
                display_text = f"{supplier_display} (Rate: {rate:,.2f})"
            else:
                display_text = supplier_display
            
            results.append((supplier.supplier, display_text))
        
        # Log for debugging
        frappe.log_error(
            f"Query returned {len(results)} suppliers for RFQ: {rfq}, Item: {item_code}",
            "get_suppliers_for_item - Success"
        )
        
        return results
        
    except Exception as e:
        frappe.log_error(
            f"Error in get_suppliers_for_item: {str(e)}\nRFQ: {rfq}, Item: {item_code}",
            "get_suppliers_for_item Error"
        )
        return []


@frappe.whitelist()
def get_available_suppliers_for_item(rfq, item_code):
    """
    Get list of all available suppliers who quoted for an item
    """
    if not rfq or not item_code:
        return ""
    
    try:
        suppliers = frappe.db.sql("""
            SELECT DISTINCT 
                sq.supplier,
                sq.supplier_name,
                sqi.rate,
                sqi.net_rate
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sqi.request_for_quotation = %(rfq)s
            AND sqi.item_code = %(item_code)s
            AND sq.docstatus = 1
            ORDER BY COALESCE(sqi.net_rate, sqi.rate) ASC
        """, {
            'rfq': rfq,
            'item_code': item_code
        }, as_dict=True)
        
        if not suppliers:
            return "No suppliers found for this item"
        
        supplier_list = []
        for supplier in suppliers:
            name = supplier.supplier_name or supplier.supplier
            rate = supplier.net_rate or supplier.rate
            supplier_list.append(f"{name} (Rate: {rate:,.2f})")
        
        result = "\n".join(supplier_list)
        
        # Log for debugging
        frappe.log_error(
            f"RFQ: {rfq}, Item: {item_code}\nResult:\n{result}",
            "get_available_suppliers_for_item - Success"
        )
        
        return result
        
    except Exception as e:
        frappe.log_error(
            f"Error in get_available_suppliers_for_item: {str(e)}\nRFQ: {rfq}, Item: {item_code}",
            "get_available_suppliers_for_item Error"
        )
        return "Error loading suppliers"


@frappe.whitelist()
def get_default_committee_members():
    """Get default committee members from settings"""
    try:
        settings = frappe.get_single("RFQ Committee Settings")
        
        if settings and settings.default_committee_members:
            return [
                {
                    "member_name": member.member_name,
                    "position": member.position
                }
                for member in settings.default_committee_members
                if member.is_active
            ]
        else:
            # Fallback
            return [
                {"member_name": "Francis Mbiu", "position": "Administrator"},
                {"member_name": "Silas Njiru", "position": "Academic Dean"},
                {"member_name": "Judy Wamalwa", "position": "Supply & Logistics"}
            ]
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Default Committee Members Error")
        return [
            {"member_name": "Francis Mbiu", "position": "Administrator"},
            {"member_name": "Silas Njiru", "position": "Academic Dean"},
            {"member_name": "Judy Wamalwa", "position": "Supply & Logistics"}
        ]