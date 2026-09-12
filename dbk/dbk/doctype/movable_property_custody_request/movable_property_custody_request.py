# Copyright (c) 2026, Nidhin Venu and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate, nowtime

from dbk.api.property_custody import get_outstanding_map, post_ledger_entries, post_reversal_entries

# The one workflow_state a transition is allowed to submit from. Set up your
# Workflow (see WORKFLOW_SETUP.md) so that only the "Receive" action leads to
# a docstatus-1 state, and name that state exactly "Received".
RECEIVE_STATES = {
	0: "Received",           # Issue
	1: "Received at Store",  # Return
}


class MovablePropertyCustodyRequest(Document):
	def validate(self):
		self.validate_warehouses()
		self.validate_items()
		if cint(self.is_return):
			self.pull_return_warehouses()
			self.validate_return_quantities()

	def validate_warehouses(self):
		if self.source_warehouse and self.target_warehouse and self.source_warehouse == self.target_warehouse:
			frappe.throw(_("Source Warehouse and Target Warehouse cannot be the same."))

	def validate_items(self):
		if not self.items:
			frappe.throw(_("Add at least one item to move."))

		seen_tags = set()
		for row in self.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row #{0}: Qty must be greater than zero.").format(row.idx))

			if row.unit_tag:
				if flt(row.qty) != 1:
					frappe.throw(
						_("Row #{0}: Qty must be exactly 1 for {1} because a Serial / Unit Tag is set.").format(
							row.idx, row.item_code
						)
					)
				key = (row.item_code, row.unit_tag)
				if key in seen_tags:
					frappe.throw(
						_("Row #{0}: Unit Tag {1} for {2} is already used elsewhere in this request.").format(
							row.idx, row.unit_tag, row.item_code
						)
					)
				seen_tags.add(key)

	def pull_return_warehouses(self):
		if not self.return_against:
			frappe.throw(_("Return Against is mandatory for a Return."))

		against = frappe.get_doc("Movable Property Custody Request", self.return_against)

		if cint(against.is_return):
			frappe.throw(_("{0} is itself a Return and cannot be returned again.").format(self.return_against))

		if against.docstatus != 1:
			frappe.throw(
				_("{0} must be a submitted (Received) Issue before it can be returned.").format(self.return_against)
			)

		# The item is always going home: source/target flip relative to the Issue.
		self.source_warehouse = against.target_warehouse
		self.target_warehouse = against.source_warehouse

	def validate_return_quantities(self):
		outstanding = get_outstanding_map(self.return_against)

		for row in self.items:
			key = (row.item_code, row.unit_tag or "")
			available = flt(outstanding.get(key, 0))

			if flt(row.qty) - available > 1e-6:
				label = f"{row.item_code} ({row.unit_tag})" if row.unit_tag else row.item_code
				frappe.throw(
					_(
						"Row #{0}: Cannot return {1} of {2} — only {3} is currently outstanding against {4}."
					).format(row.idx, row.qty, label, available, self.return_against)
				)

			if row.unit_tag and available <= 0:
				frappe.throw(
					_("Row #{0}: {1} is not an outstanding unit against {2}.").format(
						row.idx, row.unit_tag, self.return_against
					)
				)

	def before_submit(self):
		"""Permit submission only from the correct final workflow state."""

		expected_state = (
			"Received at Store"
			if cint(self.is_return)
			else "Received"
		)

		if self.workflow_state != expected_state:
			frappe.throw(
				_(
					'This document can only be submitted through the '
					'"{0}" workflow state.'
				).format(expected_state)
			)

		if not self.posting_date:
			self.posting_date = nowdate()

		if not self.posting_time:
			self.posting_time = nowtime()

		self.received_by = frappe.session.user

	def on_submit(self):
		post_ledger_entries(self)

	def on_cancel(self):
		post_reversal_entries(self)
