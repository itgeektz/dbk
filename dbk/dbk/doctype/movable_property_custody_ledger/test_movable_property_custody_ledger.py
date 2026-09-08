# Copyright (c) 2026, Nidhin Venu and contributors
# For license information, please see license.txt

"""
The ledger is meant to be append-only and posted only by
dbk.api.property_custody (which sets flags.from_property_custody_controller
before insert) — see movable_property_custody_ledger.py. These confirm that
holds even for a user with otherwise full permissions (Administrator, as
tests run), not just for an ordinary role.

Run with:
    bench --site your-site run-tests --app dbk \
        --module dbk.dbk.doctype.movable_property_custody_ledger.test_movable_property_custody_ledger
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMovablePropertyCustodyLedgerIntegrity(FrappeTestCase):
	def setUp(self):
		item = frappe.get_all("Item", limit=1, pluck="name")
		warehouse = frappe.get_all("Warehouse", limit=1, pluck="name")
		if not item or not warehouse:
			self.skipTest("Need at least one Item and one Warehouse on this site to run these tests.")
		self.item_code = item[0]
		self.warehouse = warehouse[0]

	def _unposted_row(self):
		return frappe.get_doc(
			{
				"doctype": "Movable Property Custody Ledger",
				"item_code": self.item_code,
				"warehouse": self.warehouse,
				"qty": 1,
				"movement_type": "Issue",
				"voucher_type": "Movable Property Custody Request",
				"voucher_no": "TEST-NOT-A-REAL-VOUCHER",
			}
		)

	def _posted_row(self):
		"""A row inserted the only sanctioned way — with the controller flag set.

		ignore_links=True because voucher_no is a Dynamic Link and these tests
		use a placeholder voucher number rather than a real, submitted Request
		— what's under test here is the ledger's own append-only guard, not
		Frappe's generic link-integrity check on that field.
		"""
		doc = self._unposted_row()
		doc.flags.from_property_custody_controller = True
		doc.insert(ignore_permissions=True, ignore_links=True)
		return doc

	def test_direct_insert_without_controller_flag_is_blocked(self):
		with self.assertRaises(frappe.ValidationError):
			self._unposted_row().insert(ignore_permissions=True, ignore_links=True)

	def test_insert_with_controller_flag_succeeds(self):
		doc = self._posted_row()
		self.assertTrue(doc.name)
		self.assertEqual(frappe.db.get_value("Movable Property Custody Ledger", doc.name, "qty"), 1)

	def test_posted_entry_cannot_be_edited(self):
		doc = self._posted_row()

		reloaded = frappe.get_doc("Movable Property Custody Ledger", doc.name)
		reloaded.flags.ignore_links = True
		reloaded.qty = 999
		with self.assertRaises(frappe.ValidationError):
			reloaded.save(ignore_permissions=True)

		# and the stored value never moved
		self.assertEqual(frappe.db.get_value("Movable Property Custody Ledger", doc.name, "qty"), 1)

	def test_posted_entry_cannot_be_deleted(self):
		doc = self._posted_row()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Movable Property Custody Ledger", doc.name, ignore_permissions=True)

		self.assertTrue(frappe.db.exists("Movable Property Custody Ledger", doc.name))