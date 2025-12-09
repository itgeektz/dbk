// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Warehouse Stock In Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"get_query": function() {
				var company = frappe.query_report.get_filter_value('company');
				return {
					"filters": {
						"company": company
					}
				}
			}
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function() {
				return {
					"query": "erpnext.controllers.queries.item_query"
				}
			}
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		/***
		{
			"fieldname": "stock_entry_type",
			"label": __("Stock Entry Type"),
			"fieldtype": "Select",
			"options": "\nMaterial Receipt\nMaterial Transfer\nManufacture\nRepack",
			"default": ""
		},
		{
			"fieldname": "supplier",
			"label": __("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier"
		}
			***/
	],
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		// Highlight different voucher types with different colors
		if (column.fieldname == "voucher_type") {
			if (data.voucher_type == "Purchase Receipt") {
				value = `<span style="color: #2ecc71; font-weight: bold;">${data.voucher_type}</span>`;
			} else if (data.voucher_type == "Stock Entry") {
				value = `<span style="color: #3498db; font-weight: bold;">${data.voucher_type}</span>`;
			} else if (data.voucher_type == "Stock Reconciliation") {
				value = `<span style="color: #e67e22; font-weight: bold;">${data.voucher_type}</span>`;
			}
		}
		
		// Highlight positive quantities in green
		if (column.fieldname == "qty" || column.fieldname == "stock_qty") {
			if (data[column.fieldname] > 0) {
				value = `<span style="color: #27ae60;">${value}</span>`;
			}
		}
		
		return value;
	}
};