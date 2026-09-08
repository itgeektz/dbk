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
		{"fieldname": "movement_type", "label": _("Found At"), "fieldtype": "Data", "width": 100},
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 130},
		{"fieldname": "unit_tag", "label": _("Unit Tag"), "fieldtype": "Data", "width": 100},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"fieldname": "condition_flag", "label": _("Condition"), "fieldtype": "Data", "width": 90},
		{"fieldname": "condition_remarks", "label": _("Remarks"), "fieldtype": "Data", "width": 220},
		{"fieldname": "voucher_no", "label": _("Request"), "fieldtype": "Link", "options": "Movable Property Custody Request", "width": 130},
		{"fieldname": "received_by", "label": _("Flagged By"), "fieldtype": "Link", "options": "User", "width": 150},
	]


def get_data(filters):
	query_filters = {"condition_flag": ["!=", "Good"]}

	if filters.get("item_code"):
		query_filters["item_code"] = filters["item_code"]
	if filters.get("warehouse"):
		query_filters["warehouse"] = filters["warehouse"]
	if filters.get("condition_flag"):
		query_filters["condition_flag"] = filters["condition_flag"]

	rows = frappe.get_all(
		"Movable Property Custody Ledger",
		filters=query_filters,
		fields=[
			"posting_date",
			"movement_type",
			"item_code",
			"unit_tag",
			"warehouse",
			"condition_flag",
			"condition_remarks",
			"voucher_no",
		],
		order_by="posting_date desc, name desc",
	)

	# "Flagged by" is whoever performed Received on the referenced request —
	# looked up separately since the ledger itself doesn't duplicate that field.
	request_names = list({row["voucher_no"] for row in rows if row.get("voucher_no")})
	received_by_map = {}
	if request_names:
		received_by_map = {
			r.name: r.received_by
			for r in frappe.get_all(
				"Movable Property Custody Request",
				filters={"name": ["in", request_names]},
				fields=["name", "received_by"],
			)
		}

	for row in rows:
		row["received_by"] = received_by_map.get(row.get("voucher_no"))

	return rows
