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
		{"fieldname": "request", "label": _("Issue"), "fieldtype": "Link", "options": "Movable Property Custody Request", "width": 130},
		{"fieldname": "posting_date", "label": _("Issued On"), "fieldtype": "Date", "width": 100},
		{"fieldname": "requested_by", "label": _("Requested By"), "fieldtype": "Link", "options": "User", "width": 150},
		{"fieldname": "source_warehouse", "label": _("Lending Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"fieldname": "target_warehouse", "label": _("Currently With"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 130},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 150},
		{"fieldname": "unit_tag", "label": _("Unit Tag"), "fieldtype": "Data", "width": 110},
		{"fieldname": "issued_qty", "label": _("Issued Qty"), "fieldtype": "Float", "width": 100},
		{"fieldname": "returned_qty", "label": _("Returned Qty"), "fieldtype": "Float", "width": 100},
		{"fieldname": "outstanding_qty", "label": _("Outstanding Qty"), "fieldtype": "Float", "width": 110},
		{"fieldname": "required_by", "label": _("Required By"), "fieldtype": "Date", "width": 100},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	return frappe.db.sql(
		f"""
		SELECT
			issue.name AS request,
			issue.posting_date,
			issue.requested_by,
			issue.source_warehouse,
			issue.target_warehouse,
			issue.required_by,
			item.item_code,
			item.item_name,
			item.unit_tag,
			item.qty AS issued_qty,
			COALESCE(ret.returned_qty, 0) AS returned_qty,
			(item.qty - COALESCE(ret.returned_qty, 0)) AS outstanding_qty
		FROM `tabMovable Property Custody Item` item
		INNER JOIN `tabMovable Property Custody Request` issue
			ON issue.name = item.parent AND item.parenttype = 'Movable Property Custody Request'
		LEFT JOIN (
			SELECT
				r.return_against AS issue_name,
				ri.item_code AS item_code,
				COALESCE(ri.unit_tag, '') AS unit_tag,
				SUM(ri.qty) AS returned_qty
			FROM `tabMovable Property Custody Request` r
			INNER JOIN `tabMovable Property Custody Item` ri
				ON ri.parent = r.name AND ri.parenttype = 'Movable Property Custody Request'
			WHERE r.is_return = 1 AND r.docstatus = 1
			GROUP BY r.return_against, ri.item_code, COALESCE(ri.unit_tag, '')
		) ret
			ON ret.issue_name = issue.name
			AND ret.item_code = item.item_code
			AND ret.unit_tag = COALESCE(item.unit_tag, '')
		WHERE issue.is_return = 0 AND issue.docstatus = 1 {conditions}
		HAVING outstanding_qty > 0.0000001
		ORDER BY issue.posting_date DESC, issue.name DESC
		""",
		values,
		as_dict=True,
	)


def get_conditions(filters):
	conditions = []
	values = {}

	if filters.get("company"):
		conditions.append("AND issue.company = %(company)s")
		values["company"] = filters["company"]

	if filters.get("warehouse"):
		conditions.append("AND (issue.source_warehouse = %(warehouse)s OR issue.target_warehouse = %(warehouse)s)")
		values["warehouse"] = filters["warehouse"]

	if filters.get("item_code"):
		conditions.append("AND item.item_code = %(item_code)s")
		values["item_code"] = filters["item_code"]

	return " ".join(conditions), values
