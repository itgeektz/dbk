// Copyright (c) 2025, Your Company and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Movement Report (With Reconciliation)"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1,
            "width": 100
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1,
            "width": 100
        },
        {
            "fieldname": "item_code",
            "label": __("Item"),
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function() {
                return {
                    filters: {
                        "disabled": 0
                    }
                };
            }
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "get_query": function() {
                return {
                    filters: {
                        "is_group": 0,
                        "disabled": 0
                    }
                };
            }
        },
        {
            "fieldname": "source_warehouse",
            "label": __("Source Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "get_query": function() {
                return {
                    filters: {
                        "is_group": 0,
                        "disabled": 0
                    }
                };
            }
        },
        {
            "fieldname": "target_warehouse",
            "label": __("Target Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "get_query": function() {
                return {
                    filters: {
                        "is_group": 0,
                        "disabled": 0
                    }
                };
            }
        },
        {
            "fieldname": "voucher_type",
            "label": __("Voucher Type"),
            "fieldtype": "Select",
            "options": [
                "",
                "Stock Entry",
                "Purchase Receipt",
                "Purchase Invoice",
                "Delivery Note",
                "Sales Invoice",
                "Stock Reconciliation"
            ],
            "default": ""
        },
        {
            "fieldname": "stock_entry_type",
            "label": __("Stock Entry Type"),
            "fieldtype": "Select",
            "options": [
                "",
                "Material Receipt",
                "Material Issue",
                "Material Transfer",
                "Material Transfer for Manufacture",
                "Material Consumption for Manufacture",
                "Manufacture",
                "Repack",
                "Send to Subcontractor"
            ],
            "depends_on": "eval:doc.voucher_type=='Stock Entry'"
        },
        {
            "fieldname": "voucher_no",
            "label": __("Voucher Number"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "material_request",
            "label": __("Material Request"),
            "fieldtype": "Link",
            "options": "Material Request"
        },
        {
            "fieldname": "batch_no",
            "label": __("Batch No"),
            "fieldtype": "Link",
            "options": "Batch"
        },
        {
            "fieldname": "show_zero_balance",
            "label": __("Show Zero Balance Items"),
            "fieldtype": "Check",
            "default": 0
        }
    ]
};