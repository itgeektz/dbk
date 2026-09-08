# Copyright (c) 2026, Nidhin Venu and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MovablePropertyCustodyLedger(Document):
	"""Append-only custody log.

	Rows are only ever inserted by dbk.api.property_custody (with
	ignore_permissions=True) when a Movable Property Custody Request reaches
	its Received state, or reversed on cancel. Nothing here is meant to be
	created, edited, or deleted by hand — that's enforced below rather than
	relying only on the DocType's permission matrix.
	"""

	def validate(self):
		if not self.flags.from_property_custody_controller:
			frappe.throw(
				_("Movable Property Custody Ledger entries are created automatically and cannot be entered directly.")
			)

	def on_update(self):
		if not self.flags.from_property_custody_controller and not self.flags.in_insert:
			frappe.throw(_("Ledger entries cannot be edited once posted."))

	def on_trash(self):
		frappe.throw(_("Ledger entries are permanent and cannot be deleted. Post a Reversal instead."))
