// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
// For license information, please see license.txt

frappe.query_reports["DBK Item Balance Report"] = {
	filters: [
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Warehouse",
			default: function() {
				// Try to get the default warehouse
				let default_warehouse = frappe.defaults.get_user_default("default_warehouse");
				
				// If no user default, try to find "Stores - DBK" or any main store
				if (!default_warehouse) {
					frappe.call({
						method: "frappe.client.get_value",
						args: {
							doctype: "Warehouse",
							filters: {
								warehouse_name: ["like", "%Store%"],
								disabled: 0
							},
							fieldname: "name"
						},
						async: false,
						callback: function(r) {
							if (r.message && r.message.name) {
								default_warehouse = r.message.name;
							}
						}
					});
				}
				
				return default_warehouse ? [default_warehouse] : [];
			}(),
			get_data: function(txt) {
				return frappe.db.get_link_options("Warehouse", txt, {
					disabled: 0
				});
			}
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Item",
			get_data: async function (txt) {
				let item_group = frappe.query_report.get_filter_value("item_group");

				let filters = {
					is_stock_item: 1,
					disabled: 0
				};

				// Only add item_group filter if it has values
				if (item_group) {
					if (Array.isArray(item_group) && item_group.length > 0) {
						filters.item_group = item_group;
					} else if (!Array.isArray(item_group)) {
						filters.item_group = item_group;
					}
				}

				try {
					let response = await frappe.call({
						method: "erpnext.controllers.queries.item_query",
						args: {
							doctype: "Item",
							txt: txt,
							searchfield: "name",
							start: 0,
							page_len: 20,
							filters: filters,
							as_dict: 1
						}
					});

					let data = response.message || [];
					
					data = data.map(function(item) {
						return {
							value: item.name,
							description: item.description
						};
					});

					return data;
				} catch (error) {
					console.error("Error fetching items:", error);
					return [];
				}
			}
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Item Group",
			get_data: function(txt) {
				return frappe.db.get_link_options("Item Group", txt);
			}
		},
		{
			fieldname: "include_zero_stock_items",
			label: __("Include Zero Stock Items"),
			fieldtype: "Check",
			default: 0
		}
	],

	onload: function(report) {
		// Set initial filter value if not already set
		if (!frappe.query_report.get_filter_value("warehouse")) {
			// Try to find and set default warehouse
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Warehouse",
					filters: {
						disabled: 0
					},
					fields: ["name"],
					limit_page_length: 1,
					order_by: "name"
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						frappe.query_report.set_filter_value("warehouse", [r.message[0].name]);
					}
				}
			});
		}
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "bal_qty") {
			if (data && data.bal_qty > 0) {
				value = "<span style='color:green; font-weight: bold;'>" + value + "</span>";
			} else if (data && data.bal_qty < 0) {
				value = "<span style='color:red; font-weight: bold;'>" + value + "</span>";
			}
		}

		return value;
	}
};