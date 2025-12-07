// Copyright (c) 2025, DBK and contributors
// For license information, please see license.txt

frappe.query_reports["Warehouse Stock Out Report"] = {
	"filters": [
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
				return {
					"filters": {}
				};
			}
		},
		{
			"fieldname": "aggregate_group",
			"label": __("Aggregate Group Warehouses"),
			"fieldtype": "Check",
			"default": 1,
			"description": "If warehouse is a group, aggregate data from all child warehouses"
		},
		{
			"fieldname": "department",
			"label": __("Department (Item Group)"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function() {
				return {
					"query": "frappe.desk.search.search_link",
					"filters": {}
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
			"fieldname": "purpose",
			"label": __("Purpose"),
			"fieldtype": "Select",
			"options": "\nMaterial Transfer\nMaterial Issue",
			"default": ""
		},
		{
			"fieldname": "material_request",
			"label": __("Material Request"),
			"fieldtype": "Link",
			"options": "Material Request"
		}
	],
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		// Highlight quantities
		if (column.fieldname == "quantity" && data) {
			value = `<span style="color: #e53e3e; font-weight: 600;">${value}</span>`;
		}
		
		// Format department with badge
		if (column.fieldname == "department" && data && data.department) {
			const colors = {
				'MVM': 'badge-primary',
				'GENERAL': 'badge-success',
				'Tailoring': 'badge-info',
				'Carpentry': 'badge-warning',
				'Uncategorized': 'badge-secondary'
			};
			const badge_class = colors[data.department] || 'badge-primary';
			value = `<span class="badge ${badge_class}">${data.department}</span>`;
		}
		
		// Format warehouse names with shorter display
		if ((column.fieldname == "from_warehouse" || column.fieldname == "to_warehouse") && value) {
			// Show shortened warehouse name if too long
			const display_value = value.length > 20 ? value.substring(0, 20) + '...' : value;
			value = `<span style="font-size: 0.85em;" title="${value}">${display_value}</span>`;
		}
		
		// Format comment with tooltip for long text
		if (column.fieldname == "comment" && value) {
			const display_value = value.length > 50 ? value.substring(0, 50) + '...' : value;
			value = `<span title="${value}">${display_value}</span>`;
		}
		
		return value;
	},
	
	"onload": function(report) {
		// Add custom buttons
		report.page.add_inner_button(__("Export to Excel"), function() {
			frappe.query_report.export_report("xlsx");
		});
		
		report.page.add_inner_button(__("Print"), function() {
			frappe.query_report.print_report();
		});
		
		// Add summary section
		report.page.add_inner_button(__("Show Summary"), function() {
			show_summary(report);
		});
		
		// Add refresh button
		report.page.add_inner_button(__("Refresh"), function() {
			report.refresh();
		});
	},
	
	"after_datatable_render": function(datatable) {
		// Add summary row at the bottom
		$(datatable.wrapper).find('.dt-scrollable').append(`
			<div class="dt-summary" style="padding: 10px; background: #f7fafc; border-top: 2px solid #e2e8f0; margin-top: 10px;">
				<strong>Total Records: </strong><span id="total-records">0</span> | 
				<strong>Total Quantity: </strong><span id="total-quantity">0</span>
			</div>
		`);
	},
	
	"get_datatable_options": function(options) {
		return Object.assign(options, {
			checkboxColumn: true,
			events: {
				onCheckRow: function(data) {
					// Handle row selection
					console.log(data);
				}
			}
		});
	}
};

function show_summary(report) {
	let data = report.data;
	
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data to summarize"));
		return;
	}
	
	// Calculate summaries
	let total_quantity = 0;
	let department_summary = {};
	let warehouse_summary = {};
	let item_summary = {};
	let purpose_summary = {};
	
	data.forEach(row => {
		total_quantity += row.quantity || 0;
		
		// By department
		if (row.department) {
			department_summary[row.department] = (department_summary[row.department] || 0) + row.quantity;
		}
		
		// By warehouse
		if (row.from_warehouse) {
			warehouse_summary[row.from_warehouse] = (warehouse_summary[row.from_warehouse] || 0) + row.quantity;
		}
		
		// By purpose
		if (row.purpose) {
			purpose_summary[row.purpose] = (purpose_summary[row.purpose] || 0) + row.quantity;
		}
		
		// By item
		if (row.item_code) {
			if (!item_summary[row.item_code]) {
				item_summary[row.item_code] = {
					name: row.item_name || row.item_code,
					quantity: 0
				};
			}
			item_summary[row.item_code].quantity += row.quantity;
		}
	});
	
	// Build summary HTML
	let html = `
		<div style="padding: 20px;">
			<h4 style="margin-bottom: 20px; color: #2d3748;">📊 Stock Out Summary</h4>
			
			<div style="margin-bottom: 25px;">
				<h5 style="color: #4a5568; margin-bottom: 10px;">Overall Statistics</h5>
				<table class="table table-bordered" style="width: 100%;">
					<tr>
						<td style="background: #f7fafc; font-weight: 600; width: 40%;">Total Transactions</td>
						<td>${data.length}</td>
					</tr>
					<tr>
						<td style="background: #f7fafc; font-weight: 600;">Total Quantity Issued</td>
						<td style="color: #e53e3e; font-weight: 700;">${total_quantity.toFixed(2)}</td>
					</tr>
				</table>
			</div>
			
			<div style="margin-bottom: 25px;">
				<h5 style="color: #4a5568; margin-bottom: 10px;">By Purpose</h5>
				<table class="table table-bordered" style="width: 100%;">
					<thead style="background: #edf2f7;">
						<tr>
							<th>Purpose</th>
							<th style="text-align: right;">Quantity</th>
							<th style="text-align: right;">% of Total</th>
						</tr>
					</thead>
					<tbody>
						${Object.entries(purpose_summary)
							.sort((a, b) => b[1] - a[1])
							.map(([purpose, qty]) => `
								<tr>
									<td><span class="badge badge-info">${purpose}</span></td>
									<td style="text-align: right; font-weight: 600;">${qty.toFixed(2)}</td>
									<td style="text-align: right;">${((qty / total_quantity) * 100).toFixed(1)}%</td>
								</tr>
							`).join('')}
					</tbody>
				</table>
			</div>
			
			<div style="margin-bottom: 25px;">
				<h5 style="color: #4a5568; margin-bottom: 10px;">By Department (Item Group)</h5>
				<table class="table table-bordered" style="width: 100%;">
					<thead style="background: #edf2f7;">
						<tr>
							<th>Department</th>
							<th style="text-align: right;">Quantity</th>
							<th style="text-align: right;">% of Total</th>
						</tr>
					</thead>
					<tbody>
						${Object.entries(department_summary)
							.sort((a, b) => b[1] - a[1])
							.map(([dept, qty]) => `
								<tr>
									<td><span class="badge badge-primary">${dept}</span></td>
									<td style="text-align: right; font-weight: 600;">${qty.toFixed(2)}</td>
									<td style="text-align: right;">${((qty / total_quantity) * 100).toFixed(1)}%</td>
								</tr>
							`).join('')}
					</tbody>
				</table>
			</div>
			
			<div style="margin-bottom: 25px;">
				<h5 style="color: #4a5568; margin-bottom: 10px;">Top 10 Items by Quantity</h5>
				<table class="table table-bordered" style="width: 100%;">
					<thead style="background: #edf2f7;">
						<tr>
							<th>Item</th>
							<th style="text-align: right;">Quantity</th>
						</tr>
					</thead>
					<tbody>
						${Object.entries(item_summary)
							.sort((a, b) => b[1].quantity - a[1].quantity)
							.slice(0, 10)
							.map(([code, data]) => `
								<tr>
									<td>${data.name}</td>
									<td style="text-align: right; font-weight: 600;">${data.quantity.toFixed(2)}</td>
								</tr>
							`).join('')}
					</tbody>
				</table>
			</div>
			
			<div>
				<h5 style="color: #4a5568; margin-bottom: 10px;">By Source Warehouse</h5>
				<table class="table table-bordered" style="width: 100%;">
					<thead style="background: #edf2f7;">
						<tr>
							<th>Warehouse</th>
							<th style="text-align: right;">Quantity</th>
							<th style="text-align: right;">% of Total</th>
						</tr>
					</thead>
					<tbody>
						${Object.entries(warehouse_summary)
							.sort((a, b) => b[1] - a[1])
							.map(([warehouse, qty]) => `
								<tr>
									<td>${warehouse}</td>
									<td style="text-align: right; font-weight: 600;">${qty.toFixed(2)}</td>
									<td style="text-align: right;">${((qty / total_quantity) * 100).toFixed(1)}%</td>
								</tr>
							`).join('')}
					</tbody>
				</table>
			</div>
		</div>
	`;
	
	// Show in dialog
	let d = new frappe.ui.Dialog({
		title: __("Stock Out Summary"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "summary_html"
			}
		]
	});
	
	d.fields_dict.summary_html.$wrapper.html(html);
	d.show();
}

// Update summary when data changes
frappe.query_reports["Warehouse Stock Out Report"].on_data_render = function(data) {
	if (data && data.length > 0) {
		let total_quantity = data.reduce((sum, row) => sum + (row.quantity || 0), 0);
		
		setTimeout(() => {
			$('#total-records').text(data.length);
			$('#total-quantity').text(total_quantity.toFixed(2));
		}, 100);
	}
};