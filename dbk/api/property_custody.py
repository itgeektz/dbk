# Copyright (c) 2026, Nidhin Venu and contributors
# For license information, please see license.txt

"""
Controller support for the Movable Items & Property Custody module.

Mirrors the permission pattern already used for Stock Entry in
dbk/api/stock_entry.py: System Manager and the module's own manager role
(here, "Movable Property Custodian") get unrestricted access, everyone else
is scoped to the warehouses they hold a User Permission on.

This module deliberately never touches Stock Ledger Entry, GL Entry, or Bin —
see the design spec, section 06.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

REQUEST_DOCTYPE = "Movable Property Custody Request"
ITEM_DOCTYPE = "Movable Property Custody Item"
LEDGER_DOCTYPE = "Movable Property Custody Ledger"
OVERRIDE_ROLES = {"System Manager", "Movable Property Custodian"}


# ---------------------------------------------------------------------------
# Ledger posting
# ---------------------------------------------------------------------------

def post_ledger_entries(doc):
	"""Called from on_submit — i.e. at the Received step of either an Issue
	or a Return. Writes one negative row at the warehouse losing custody and
	one positive row at the warehouse gaining it, per item row."""
	movement_type = "Return" if doc.is_return else "Issue"
	against_request = doc.return_against if doc.is_return else None

	for row in doc.items:
		_make_ledger_row(doc, row, doc.source_warehouse, -flt(row.qty), movement_type, against_request)
		_make_ledger_row(doc, row, doc.target_warehouse, flt(row.qty), movement_type, against_request)


def post_reversal_entries(doc):
	"""Called from on_cancel. Ledger rows are never edited or deleted —
	cancelling posts a mirror-image pair that nets the original entry to zero."""
	against_request = doc.return_against if doc.is_return else None

	for row in doc.items:
		_make_ledger_row(doc, row, doc.source_warehouse, flt(row.qty), "Reversal", against_request)
		_make_ledger_row(doc, row, doc.target_warehouse, -flt(row.qty), "Reversal", against_request)


def _make_ledger_row(doc, item_row, warehouse, qty, movement_type, against_request):
	entry = frappe.get_doc(
		{
			"doctype": LEDGER_DOCTYPE,
			"posting_date": doc.posting_date,
			"posting_time": doc.posting_time,
			"item_code": item_row.item_code,
			"unit_tag": item_row.unit_tag,
			"warehouse": warehouse,
			"qty": qty,
			"movement_type": movement_type,
			"condition_flag": item_row.condition_flag,
			"condition_remarks": item_row.condition_remarks,
			"voucher_type": REQUEST_DOCTYPE,
			"voucher_no": doc.name,
			"against_request": against_request,
		}
	)
	entry.flags.from_property_custody_controller = True
	entry.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Outstanding-balance helper (used for return validation and for the
# "pull outstanding items onto a Return" convenience in the client script)
# ---------------------------------------------------------------------------

def get_outstanding_map(request_name):
	"""{(item_code, unit_tag_or_''): outstanding_qty} for a submitted Issue.

	Computed from the source documents (the Issue's own item rows, minus the
	item rows of every submitted Return raised against it), not from the
	ledger — simpler, and doesn't depend on how the ledger's signs are read.
	"""
	issued_rows = frappe.get_all(
		ITEM_DOCTYPE,
		filters={"parent": request_name, "parenttype": REQUEST_DOCTYPE},
		fields=["item_code", "unit_tag", "qty"],
	)

	outstanding = {}
	for row in issued_rows:
		key = (row.item_code, row.unit_tag or "")
		outstanding[key] = outstanding.get(key, 0) + flt(row.qty)

	returned_against = frappe.get_all(
		REQUEST_DOCTYPE,
		filters={"return_against": request_name, "docstatus": 1},
		pluck="name",
	)
	if returned_against:
		returned_rows = frappe.get_all(
			ITEM_DOCTYPE,
			filters={"parent": ["in", returned_against], "parenttype": REQUEST_DOCTYPE},
			fields=["item_code", "unit_tag", "qty"],
		)
		for row in returned_rows:
			key = (row.item_code, row.unit_tag or "")
			outstanding[key] = outstanding.get(key, 0) - flt(row.qty)

	return outstanding


@frappe.whitelist()
def get_return_defaults(request_name):
	"""Used by the client script when Return Against is set: hands back the
	flipped warehouses and a ready-made list of outstanding item rows so the
	requester doesn't have to retype what's already on record."""
	against = frappe.get_doc(REQUEST_DOCTYPE, request_name)
	outstanding = get_outstanding_map(request_name)

	items = []
	for (item_code, unit_tag), qty in outstanding.items():
		if qty <= 0:
			continue
		item_name, stock_uom = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"])
		items.append(
			{
				"item_code": item_code,
				"item_name": item_name,
				"stock_uom": stock_uom,
				"unit_tag": unit_tag or None,
				"qty": qty,
			}
		)

	return {
		"source_warehouse": against.target_warehouse,
		"target_warehouse": against.source_warehouse,
		"outstanding_items": items,
	}


@frappe.whitelist()
def return_against_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link-query for the Return Against field on a Return.

	The client script used to filter this dropdown with a plain
	{"is_return": 0, "docstatus": 1} — that has no way to say "and isn't
	already fully returned," so an Issue stayed listed forever, long after
	every unit on it had already come back.

	This scans submitted Issues, newest first, and keeps only the ones with
	at least one item row still outstanding (per get_outstanding_map, the
	same balance check the return-quantity validation itself uses — so this
	list and that validation can never disagree about what's returnable).

	Uses frappe.get_list rather than frappe.get_all so the module's existing
	warehouse-based scoping (property_custody_permission_query /
	property_custody_has_permission) still applies to whoever is searching —
	an Issue a user can't otherwise see won't show up here either.

	Scans in batches ordered by most-recently-modified rather than pulling
	every submitted Issue on the site, so a long history of already-closed
	ones doesn't have to be walked on every keystroke — it stops as soon as
	it has collected enough genuinely outstanding matches to fill the page.
	"""
	start = cint(start)
	page_len = cint(page_len) or 20

	list_filters = {"is_return": 0, "workflow_state": "**Received**"}
	# or_filters = [["name", "like", f"%{txt}%"]] if txt else None

	needed = start + page_len
	matches = []
	scan_start = 0
	batch = max(page_len * 5, 50)

	while len(matches) < needed:
		candidates = frappe.get_list(
			REQUEST_DOCTYPE,
			filters=list_filters,
			# or_filters=or_filters,
			fields=["name"],
			order_by="modified desc",
			limit_start=scan_start,
			limit_page_length=batch,
		)
		if not candidates:
			break

		for row in candidates:
			outstanding = get_outstanding_map(row.name)
			if any(flt(qty) > 0 for qty in outstanding.values()):
				matches.append(row.name)

		if len(candidates) < batch:
			break  # exhausted the table
		scan_start += batch

	return [[name] for name in matches[start : start + page_len]]


# ---------------------------------------------------------------------------
# Permissions — same shape as dbk.api.stock_entry
# ---------------------------------------------------------------------------

def _allowed_warehouses(user):
	return frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Warehouse"},
		pluck="for_value",
	)


def property_custody_permission_query(user):
	if not user:
		user = frappe.session.user

	if set(frappe.get_roles(user)).intersection(OVERRIDE_ROLES):
		return None

	allowed_warehouses = _allowed_warehouses(user)
	if not allowed_warehouses:
		return None

	warehouse_list = ", ".join(frappe.db.escape(w) for w in allowed_warehouses)
	return (
		f"(`tab{REQUEST_DOCTYPE}`.`source_warehouse` IN ({warehouse_list}) "
		f"OR `tab{REQUEST_DOCTYPE}`.`target_warehouse` IN ({warehouse_list}))"
	)


def property_custody_has_permission(doc, user):
	if not user:
		user = frappe.session.user

	if set(frappe.get_roles(user)).intersection(OVERRIDE_ROLES):
		return True

	allowed_warehouses = _allowed_warehouses(user)
	if not allowed_warehouses:
		return True

	return doc.source_warehouse in allowed_warehouses or doc.target_warehouse in allowed_warehouses


def check_property_receive_permission(doc, method=None):
	"""Extra gate on the Received transition, for when you later scope
	Movable Property Custodian to specific warehouses via User Permission.
	Today the Workflow's own 'allowed' role already keeps the Receive action
	hidden from anyone without the role, so this mostly matters once you
	split that role's reach per-warehouse."""
	form_dict = frappe.local.form_dict or {}
	action = (form_dict.get("action") or "").lower()
	if action != "receive":
		return

	user = frappe.session.user
	if set(frappe.get_roles(user)).intersection(OVERRIDE_ROLES):
		return

	allowed_warehouses = _allowed_warehouses(user)
	if not allowed_warehouses:
		return

	receiving_warehouse = doc.target_warehouse
	if receiving_warehouse in allowed_warehouses:
		return

	frappe.throw(
		_(
			"You are not permitted to Receive this entry. Your allowed warehouses: {0}. "
			"This request's receiving warehouse: {1}."
		).format(", ".join(allowed_warehouses), receiving_warehouse),
		frappe.PermissionError,
	)