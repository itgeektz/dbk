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
            return
        
        # Get RFQ items
        rfq_items = frappe.get_all(
            "Request for Quotation Item",
            filters={"parent": self.request_for_quotation},
            fields=["item_code", "item_name", "qty", "uom"],
            order_by="idx"
        )
        
        # Get supplier quotations linked to this RFQ
        sq_list = frappe.db.sql("""
            SELECT DISTINCT sq.name, sq.supplier, sq.supplier_name
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sqi.request_for_quotation = %s
            AND sq.docstatus = 1
        """, (self.request_for_quotation,), as_dict=True)
        
        # For each item, find available suppliers and lowest bidder
        for item in rfq_items:
            suppliers_data = []
            lowest_rate = None
            lowest_supplier = None
            
            for sq in sq_list:
                # Get rate for this item from this supplier
                sq_item = frappe.db.get_value(
                    "Supplier Quotation Item",
                    {
                        "parent": sq.name,
                        "item_code": item.item_code
                    },
                    ["rate"],
                    as_dict=True
                )
                
                if sq_item and sq_item.rate:
                    suppliers_data.append({
                        "supplier": sq.supplier_name or sq.supplier,
                        "rate": sq_item.rate
                    })
                    
                    if lowest_rate is None or sq_item.rate < lowest_rate:
                        lowest_rate = sq_item.rate
                        lowest_supplier = sq.supplier_name or sq.supplier
            
            # Add row to item selections
            if suppliers_data:
                supplier_options = "\n".join([f"{s['supplier']} (Rate: {s['rate']:.2f})" 
                                             for s in suppliers_data])
                
                self.append("item_selections", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "qty": item.qty,
                    "uom": item.uom,
                    "selected_supplier": lowest_supplier,
                    "available_suppliers": supplier_options
                })
    
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
        # Find supplier quotation
        sq = frappe.db.sql("""
            SELECT sq.name, sq.supplier
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
        
        # Add custom field reference to meeting
        if frappe.db.exists("Custom Field", {"dt": "Purchase Order", "fieldname": "rfq_meeting"}):
            po.rfq_meeting = self.name
        
        # Add items
        for item in items:
            # Get item details from supplier quotation
            sq_item = frappe.db.get_value(
                "Supplier Quotation Item",
                {
                    "parent": sq[0].name,
                    "item_code": item.item_code
                },
                ["rate", "warehouse", "description"],
                as_dict=True
            )
            
            if sq_item:
                warehouse = sq_item.warehouse or frappe.db.get_value(
                    "Warehouse",
                    {"company": self.company, "is_group": 0},
                    "name"
                )
                
                po.append("items", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "description": sq_item.description or item.item_name,
                    "qty": item.qty,
                    "rate": sq_item.rate,
                    "uom": item.uom,
                    "warehouse": warehouse,
                    "schedule_date": self.required_date,
                    "project": self.project
                })
        
        po.insert()
        frappe.db.commit()
        
        return po

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