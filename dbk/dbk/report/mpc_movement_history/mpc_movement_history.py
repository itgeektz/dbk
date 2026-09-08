# Copyright (c) 2026, Nidhin Venu and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters or {})
	return columns, data


def get_columns():
	return [
		{"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "posting_time", "label": _("Time"), "fieldtype": "Time", "width": 90},
		{"fieldname": "movement_type", "label": _("Type"), "fieldtype": "Data", "width": 90},
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 130},
		{"fieldname": "unit_tag", "label": _("Unit Tag"), "fieldtype": "Data", "width": 100},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"fieldname": "qty", "label": _("Qty"), "fieldtype": "Float", "width": 90},
		{"fieldname": "condition_flag", "label": _("Condition"), "fieldtype": "Data", "width": 90},
		{"fieldname": "voucher_no", "label": _("Request"), "fieldtype": "Link", "options": "Movable Property Custody Request", "width": 130},
		{"fieldname": "against_request", "label": _("Against"), "fieldtype": "Link", "options": "Movable Property Custody Request", "width": 130},
	]


def get_data(filters):
	query_filters = {}

	if filters.get("item_code"):
		query_filters["item_code"] = filters["item_code"]
	if filters.get("warehouse"):
		query_filters["warehouse"] = filters["warehouse"]
	if filters.get("voucher_no"):
		query_filters["voucher_no"] = filters["voucher_no"]
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]

	return frappe.get_all(
		"Movable Property Custody Ledger",
		filters=query_filters,
		fields=[
			"posting_date",
			"posting_time",
			"movement_type",
			"item_code",
			"unit_tag",
			"warehouse",
			"qty",
			"condition_flag",
			"voucher_no",
			"against_request",
		],
		order_by="posting_date desc, posting_time desc, name desc",
	)
