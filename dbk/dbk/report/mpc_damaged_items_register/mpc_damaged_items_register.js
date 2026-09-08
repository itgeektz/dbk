// Copyright (c) 2026, Nidhin Venu and contributors
// For license information, please see license.txt

frappe.query_reports["MPC Damaged Items Register"] = {
	filters: [
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "condition_flag",
			label: __("Condition"),
			fieldtype: "Select",
			options: ["", "Damaged", "Missing"],
		},
	],
};
