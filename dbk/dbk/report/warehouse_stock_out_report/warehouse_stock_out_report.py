# Copyright (c) 2025, DBK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	"""Define report columns"""
	return [
		
		{
			"fieldname": "date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 100
		},
		{
			"fieldname": "department",
			"label": _("Item Group"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "item_code",
			"label": _("Item"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"fieldname": "quantity",
			"label": _("Quantity"),
			"fieldtype": "Float",
			"width": 100
		},
		{
			"fieldname": "uom",
			"label": _("Unit"),
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80
		},
		{
			"fieldname": "from_warehouse",
			"label": _("From Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180
		},
		{
			"fieldname": "to_warehouse",
			"label": _("Transferred To"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180
		},
		{
			"fieldname": "comment",
			"label": _("Comment"),
			"fieldtype": "Small Text",
			"width": 200
		},
		{
			"fieldname": "purpose",
			"label": _("Purpose"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "voucher_no",
			"label": _("Stock Entry"),
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 140
		},
		{
			"fieldname": "material_request",
			"label": _("Material Request"),
			"fieldtype": "Link",
			"options": "Material Request",
			"width": 140
		}
	]

def get_data(filters):
	"""Get stock out data based on filters"""
	conditions = get_conditions(filters)
	
	# Check if warehouse is a group and get child warehouses
	warehouses = get_warehouses(filters.get("warehouse"))
	
	if not warehouses:
		return []
	
	warehouse_conditions = "AND sed.s_warehouse IN ({})".format(
		", ".join([f"'{w}'" for w in warehouses])
	)
	
	query = f"""
		SELECT
			COALESCE(item.item_group, 'Uncategorized') as department,
			sed.item_code,
			sed.uom,
			sed.qty as quantity,
			se.posting_date as date,
			sed.s_warehouse as from_warehouse,
			sed.t_warehouse as to_warehouse,
			se.stock_entry_type as purpose,
			mr.custom_material_usage_intention as comment,
			mr.name as material_request,
			se.name as voucher_no,
			se.material_request
		FROM
			`tabStock Entry Detail` sed
		INNER JOIN
			`tabStock Entry` se ON sed.parent = se.name
		INNER JOIN
			`tabItem` item ON sed.item_code = item.item_code
		LEFT JOIN
			`tabMaterial Request` mr ON se.material_request = mr.name
		WHERE
			se.docstatus = 1
			AND sed.s_warehouse IS NOT NULL
			AND sed.s_warehouse != ''
			AND se.stock_entry_type IN ('Material Transfer', 'Material Issue')
			{warehouse_conditions}
			{conditions}
		ORDER BY
			se.posting_date DESC, se.posting_time DESC
	"""
	
	data = frappe.db.sql(query, as_dict=1)
	
	# If warehouse is a group, aggregate data
	if filters.get("warehouse") and filters.get("aggregate_group"):
		data = aggregate_warehouse_data(data, filters)
	
	return data

def get_conditions(filters):
	"""Build SQL conditions based on filters"""
	conditions = []
	
	if filters.get("from_date"):
		conditions.append(f"se.posting_date >= '{filters.get('from_date')}'")
	
	if filters.get("to_date"):
		conditions.append(f"se.posting_date <= '{filters.get('to_date')}'")
	
	if filters.get("department"):
		conditions.append(f"item.item_group = '{filters.get('department')}'")
	
	if filters.get("item_code"):
		conditions.append(f"sed.item_code = '{filters.get('item_code')}'")
	
	if filters.get("item_group"):
		conditions.append(f"item.item_group = '{filters.get('item_group')}'")
	
	if filters.get("purpose"):
		conditions.append(f"se.stock_entry_type = '{filters.get('purpose')}'")
	
	if filters.get("material_request"):
		conditions.append(f"se.material_request = '{filters.get('material_request')}'")
	
	return "AND " + " AND ".join(conditions) if conditions else ""

def get_warehouses(warehouse):
	"""Get warehouse and its children if it's a group"""
	if not warehouse:
		# Return all warehouses if none selected
		return [w.name for w in frappe.get_all("Warehouse", filters={"is_group": 0})]
	
	# Check if warehouse is a group
	is_group = frappe.db.get_value("Warehouse", warehouse, "is_group")
	
	if is_group:
		# Get all child warehouses
		lft, rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])
		child_warehouses = frappe.db.sql("""
			SELECT name 
			FROM `tabWarehouse`
			WHERE lft >= %s AND rgt <= %s AND is_group = 0
		""", (lft, rgt), as_dict=1)
		return [w.name for w in child_warehouses]
	else:
		return [warehouse]

def aggregate_warehouse_data(data, filters):
	"""Aggregate data by item when warehouse is a group"""
	if not filters.get("aggregate_group"):
		return data
	
	aggregated = {}
	
	for row in data:
		key = (row.item_code, row.department, row.date, )
		
		if key in aggregated:
			aggregated[key]["quantity"] += row.quantity
			# Concatenate warehouses if different
			if row.from_warehouse and row.from_warehouse not in aggregated[key]["from_warehouse"]:
				aggregated[key]["from_warehouse"] += f", {row.from_warehouse}"
			if row.to_warehouse and row.to_warehouse not in aggregated[key]["to_warehouse"]:
				aggregated[key]["to_warehouse"] += f", {row.to_warehouse}"
			# Concatenate voucher numbers
			if row.voucher_no and row.voucher_no not in aggregated[key]["voucher_no"]:
				aggregated[key]["voucher_no"] += f", {row.voucher_no}"
		else:
			aggregated[key] = row.copy()
	
	return list(aggregated.values())

def get_chart_data(data, filters):
	"""Generate chart data for the report"""
	if not data:
		return None
	
	# Group by department
	department_data = {}
	for row in data:
		dept = row.get("department") or "Uncategorized"
		if dept not in department_data:
			department_data[dept] = 0
		department_data[dept] += flt(row.get("quantity", 0))
	
	labels = list(department_data.keys())
	values = list(department_data.values())
	
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": "Quantity Issued",
					"values": values
				}
			]
		},
		"type": "bar",
		"colors": ["#4C51BF"]
	}