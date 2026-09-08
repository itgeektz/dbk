# Copyright (c) 2026, Nidhin Venu and contributors
# For license information, please see license.txt

"""
Coverage for dbk.dbk.doctype.movable_property_custody_request and the
posting/permission logic in dbk.api.property_custody.

Run with:
    bench --site your-site run-tests --app dbk \
        --module dbk.dbk.doctype.movable_property_custody_request.test_movable_property_custody_request

These tests talk to the Document API directly (insert / submit / cancel),
not through the Workflow UI, so they exercise the controller's own guard
rails regardless of whether the Workflow record described in
WORKFLOW_SETUP.md has been created yet. If that Workflow *is* active by the
time you run these, note that it only manages workflow_state on save from
the desk UI — it does not stop a script from setting workflow_state and
calling .submit() directly, so these tests remain valid either way.

Each test method runs inside FrappeTestCase's own DB transaction and is
rolled back automatically — nothing here leaves data behind on your site.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from dbk.api.property_custody import get_outstanding_map

RECEIVE_STATE = "Received"


class TestMovablePropertyCustodyRequest(FrappeTestCase):
	def setUp(self):
		self.company = self._get_default_company()
		self.item_code = self._get_or_create_item("_Test MPC Item", is_stock_item=0)
		self.stock_item_code = self._get_or_create_item("_Test MPC Stock Item", is_stock_item=1)
		self.store_wh = self._get_or_create_warehouse("_Test MPC Store")
		self.dept_a_wh = self._get_or_create_warehouse("_Test MPC Dept A")
		self.dept_b_wh = self._get_or_create_warehouse("_Test MPC Dept B")

	# ------------------------------------------------------------------
	# fixtures
	# ------------------------------------------------------------------

	def _get_default_company(self):
		company = frappe.get_all("Company", limit=1, pluck="name")
		if not company:
			self.skipTest("No Company found on this site — cannot run these tests.")
		return company[0]

	def _get_or_create_item(self, name, is_stock_item):
		if frappe.db.exists("Item", name):
			return name
		item_group = frappe.get_all("Item Group", limit=1, pluck="name")
		item_group = item_group[0] if item_group else "All Item Groups"
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": name,
				"item_name": name,
				"item_group": item_group,
				"is_stock_item": 1 if is_stock_item else 0,
				"stock_uom": "Nos",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _get_or_create_warehouse(self, name):
		existing = frappe.get_all(
			"Warehouse",
			filters={"warehouse_name": name, "company": self.company},
			limit=1,
			pluck="name",
		)
		if existing:
			return existing[0]
		doc = frappe.get_doc(
			{"doctype": "Warehouse", "warehouse_name": name, "company": self.company}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _make_request(self, **kwargs):
		defaults = {
			"doctype": "Movable Property Custody Request",
			"company": self.company,
			"requested_by": frappe.session.user,
		}
		defaults.update(kwargs)
		return frappe.get_doc(defaults)

	def _issue_and_receive(self, items, source=None, target=None):
		"""Create + submit an Issue in one step, as if it just cleared the Received gate."""
		doc = self._make_request(
			is_return=0,
			source_warehouse=source or self.store_wh,
			target_warehouse=target or self.dept_a_wh,
			items=items,
		)
		doc.insert()
		doc.workflow_state = RECEIVE_STATE
		doc.submit()
		return doc

	def _return_and_receive(self, against, items):
		doc = self._make_request(is_return=1, return_against=against, items=items)
		doc.insert()
		doc.workflow_state = RECEIVE_STATE
		doc.submit()
		return doc

	def _ledger_rows(self, voucher_no):
		return frappe.get_all(
			"Movable Property Custody Ledger",
			filters={"voucher_no": voucher_no},
			fields=["item_code", "unit_tag", "warehouse", "qty", "movement_type", "condition_flag", "condition_remarks"],
		)

	# ------------------------------------------------------------------
	# basic validation
	# ------------------------------------------------------------------

	def test_qty_must_be_positive(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 0}],
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_source_and_target_warehouse_cannot_be_same(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.store_wh,
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_at_least_one_item_required(self):
		doc = self._make_request(
			is_return=0, source_warehouse=self.store_wh, target_warehouse=self.dept_a_wh, items=[]
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_draft_does_not_require_workflow_state(self):
		"""Saving a Draft (docstatus 0) should never trigger the Received-only guard."""
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		doc.insert()
		self.assertEqual(doc.docstatus, 0)

	# ------------------------------------------------------------------
	# the Received-only submit gate
	# ------------------------------------------------------------------

	def test_submit_blocked_without_received_workflow_state(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		doc.insert()
		doc.workflow_state = "Pending Approval"
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_submit_succeeds_with_received_workflow_state(self):
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 1}])
		self.assertEqual(issue.docstatus, 1)
		self.assertEqual(issue.workflow_state, RECEIVE_STATE)
		self.assertTrue(issue.received_by)
		self.assertTrue(issue.posting_date)

	def test_no_ledger_entries_for_an_unsubmitted_draft(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		doc.insert()  # never submitted — the "Rejected" path never posts either
		self.assertEqual(len(self._ledger_rows(doc.name)), 0)

	# ------------------------------------------------------------------
	# ledger posting on Issue
	# ------------------------------------------------------------------

	def test_issue_posts_signed_ledger_pair(self):
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 4}])
		rows = self._ledger_rows(issue.name)
		self.assertEqual(len(rows), 2)

		by_warehouse = {r.warehouse: r.qty for r in rows}
		self.assertEqual(by_warehouse[self.store_wh], -4)
		self.assertEqual(by_warehouse[self.dept_a_wh], 4)
		self.assertTrue(all(r.movement_type == "Issue" for r in rows))

	def test_issue_never_touches_stock_ledger_or_bin(self):
		"""The whole point of a parallel custody ledger: no Stock Ledger Entry, no Bin change."""
		bin_before = frappe.db.get_value(
			"Bin", {"item_code": self.stock_item_code, "warehouse": self.dept_a_wh}, "actual_qty"
		)

		issue = self._issue_and_receive(
			[{"item_code": self.stock_item_code, "qty": 3}],
			source=self.store_wh,
			target=self.dept_a_wh,
		)

		sle_count = frappe.db.count("Stock Ledger Entry", {"voucher_no": issue.name})
		self.assertEqual(sle_count, 0)

		bin_after = frappe.db.get_value(
			"Bin", {"item_code": self.stock_item_code, "warehouse": self.dept_a_wh}, "actual_qty"
		)
		self.assertEqual(bin_before, bin_after)

	def test_non_stock_item_can_be_moved(self):
		"""No restriction to stock items — the module works for any Item."""
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 1}])
		self.assertEqual(issue.docstatus, 1)

	# ------------------------------------------------------------------
	# unit / serial tagging
	# ------------------------------------------------------------------

	def test_unit_tag_requires_qty_of_one(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 2, "unit_tag": "TAG-1"}],
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_duplicate_unit_tag_within_one_request_blocked(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[
				{"item_code": self.item_code, "qty": 1, "unit_tag": "TAG-DUP"},
				{"item_code": self.item_code, "qty": 1, "unit_tag": "TAG-DUP"},
			],
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_same_item_different_tags_to_different_departments(self):
		"""The scenario that motivated unit tagging: two units of the same item
		code, out to two different departments, at the same time."""
		issue_a = self._issue_and_receive(
			[{"item_code": self.item_code, "qty": 1, "unit_tag": "DRILL-A1"}],
			target=self.dept_a_wh,
		)
		issue_b = self._issue_and_receive(
			[{"item_code": self.item_code, "qty": 1, "unit_tag": "DRILL-A2"}],
			target=self.dept_b_wh,
		)
		self.assertEqual(issue_a.docstatus, 1)
		self.assertEqual(issue_b.docstatus, 1)

		outstanding_a = get_outstanding_map(issue_a.name)
		outstanding_b = get_outstanding_map(issue_b.name)
		self.assertEqual(outstanding_a.get((self.item_code, "DRILL-A1")), 1)
		self.assertEqual(outstanding_b.get((self.item_code, "DRILL-A2")), 1)

	# ------------------------------------------------------------------
	# returns: full, partial, over, wrong reference
	# ------------------------------------------------------------------

	def test_full_return_closes_outstanding_balance(self):
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 3}])
		self.assertEqual(get_outstanding_map(issue.name).get((self.item_code, "")), 3)

		self._return_and_receive(issue.name, [{"item_code": self.item_code, "qty": 3}])

		self.assertEqual(get_outstanding_map(issue.name).get((self.item_code, ""), 0), 0)

	def test_partial_return_leaves_remaining_balance(self):
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 5}])
		self._return_and_receive(issue.name, [{"item_code": self.item_code, "qty": 2}])

		self.assertEqual(get_outstanding_map(issue.name).get((self.item_code, "")), 3)

	def test_over_return_is_blocked(self):
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 2}])
		ret = self._make_request(
			is_return=1, return_against=issue.name, items=[{"item_code": self.item_code, "qty": 5}]
		)
		with self.assertRaises(frappe.ValidationError):
			ret.insert()

	def test_return_requires_return_against(self):
		doc = self._make_request(
			is_return=1, items=[{"item_code": self.item_code, "qty": 1}]
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_return_against_a_draft_issue_is_blocked(self):
		draft_issue = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		draft_issue.insert()  # never submitted

		ret = self._make_request(
			is_return=1, return_against=draft_issue.name, items=[{"item_code": self.item_code, "qty": 1}]
		)
		with self.assertRaises(frappe.ValidationError):
			ret.insert()

	def test_return_of_a_return_is_blocked(self):
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 2}])
		first_return = self._return_and_receive(issue.name, [{"item_code": self.item_code, "qty": 2}])

		second_return = self._make_request(
			is_return=1,
			return_against=first_return.name,
			items=[{"item_code": self.item_code, "qty": 2}],
		)
		with self.assertRaises(frappe.ValidationError):
			second_return.insert()

	def test_return_with_wrong_unit_tag_is_blocked(self):
		issue = self._issue_and_receive(
			[{"item_code": self.item_code, "qty": 1, "unit_tag": "DRILL-B1"}]
		)
		ret = self._make_request(
			is_return=1,
			return_against=issue.name,
			items=[{"item_code": self.item_code, "qty": 1, "unit_tag": "DRILL-WRONG-TAG"}],
		)
		with self.assertRaises(frappe.ValidationError):
			ret.insert()

	def test_return_with_correct_unit_tag_succeeds(self):
		issue = self._issue_and_receive(
			[{"item_code": self.item_code, "qty": 1, "unit_tag": "DRILL-C1"}]
		)
		ret = self._return_and_receive(
			issue.name, [{"item_code": self.item_code, "qty": 1, "unit_tag": "DRILL-C1"}]
		)
		self.assertEqual(ret.docstatus, 1)
		self.assertEqual(get_outstanding_map(issue.name).get((self.item_code, "DRILL-C1"), 0), 0)

	def test_return_auto_fills_flipped_warehouses(self):
		issue = self._issue_and_receive(
			[{"item_code": self.item_code, "qty": 1}], source=self.store_wh, target=self.dept_a_wh
		)
		ret = self._make_request(
			is_return=1, return_against=issue.name, items=[{"item_code": self.item_code, "qty": 1}]
		)
		ret.insert()
		self.assertEqual(ret.source_warehouse, self.dept_a_wh)
		self.assertEqual(ret.target_warehouse, self.store_wh)

	def test_overdue_return_is_flagged_by_required_by(self):
		"""Sanity check for the data the Overdue Returns report relies on."""
		issue = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			required_by=add_days(nowdate(), -5),
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		issue.insert()
		issue.workflow_state = RECEIVE_STATE
		issue.submit()

		self.assertTrue(issue.required_by < nowdate())
		self.assertGreater(get_outstanding_map(issue.name).get((self.item_code, ""), 0), 0)

	# ------------------------------------------------------------------
	# Return Against link-query
	# ------------------------------------------------------------------

	def test_return_against_query_excludes_fully_returned_requests(self):
		from dbk.api.property_custody import return_against_query

		still_open = self._issue_and_receive([{"item_code": self.item_code, "qty": 2}])

		partially_returned = self._issue_and_receive([{"item_code": self.item_code, "qty": 4}])
		self._return_and_receive(partially_returned.name, [{"item_code": self.item_code, "qty": 1}])

		fully_returned = self._issue_and_receive([{"item_code": self.item_code, "qty": 1}])
		self._return_and_receive(fully_returned.name, [{"item_code": self.item_code, "qty": 1}])

		results = return_against_query("Movable Property Custody Request", "", "name", 0, 20, {})
		names = {row[0] for row in results}

		self.assertIn(still_open.name, names)
		self.assertIn(partially_returned.name, names)
		self.assertNotIn(fully_returned.name, names)

	def test_return_against_query_excludes_drafts_and_returns_themselves(self):
		from dbk.api.property_custody import return_against_query

		draft_issue = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		draft_issue.insert()  # never submitted

		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 1}])
		a_return = self._return_and_receive(issue.name, [{"item_code": self.item_code, "qty": 1}])

		results = return_against_query("Movable Property Custody Request", "", "name", 0, 100, {})
		names = {row[0] for row in results}

		self.assertNotIn(draft_issue.name, names)  # never submitted — nothing to return against
		self.assertNotIn(a_return.name, names)  # a Return can't itself be returned against

	def test_return_against_query_respects_txt_filter(self):
		from dbk.api.property_custody import return_against_query

		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 1}])
		results = return_against_query(
			"Movable Property Custody Request", issue.name, "name", 0, 20, {}
		)
		names = {row[0] for row in results}
		self.assertIn(issue.name, names)

		no_match = return_against_query(
			"Movable Property Custody Request", "NO-SUCH-REQUEST-XYZ", "name", 0, 20, {}
		)
		self.assertEqual(no_match, [])

	# ------------------------------------------------------------------
	# condition / damage flagging
	# ------------------------------------------------------------------

	def test_condition_flag_defaults_to_good(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[{"item_code": self.item_code, "qty": 1}],
		)
		doc.insert()
		self.assertEqual(doc.items[0].condition_flag, "Good")

	def test_damaged_flag_does_not_block_submit_and_is_posted_to_ledger(self):
		doc = self._make_request(
			is_return=0,
			source_warehouse=self.store_wh,
			target_warehouse=self.dept_a_wh,
			items=[
				{
					"item_code": self.item_code,
					"qty": 1,
					"condition_flag": "Damaged",
					"condition_remarks": "Casing cracked on arrival.",
				}
			],
		)
		doc.insert()
		doc.workflow_state = RECEIVE_STATE
		doc.submit()  # a Damaged flag is a record, not a lock

		rows = self._ledger_rows(doc.name)
		self.assertTrue(all(r.condition_flag == "Damaged" for r in rows))
		self.assertTrue(all(r.condition_remarks == "Casing cracked on arrival." for r in rows))

	# ------------------------------------------------------------------
	# cancel / reversal
	# ------------------------------------------------------------------

	def test_cancel_posts_reversal_pair_that_nets_to_zero(self):
		issue = self._issue_and_receive([{"item_code": self.item_code, "qty": 4}])
		issue.cancel()

		rows = self._ledger_rows(issue.name)
		self.assertEqual(len(rows), 4)  # original Issue pair + Reversal pair

		total_by_warehouse = {}
		for r in rows:
			total_by_warehouse[r.warehouse] = total_by_warehouse.get(r.warehouse, 0) + r.qty
		self.assertEqual(total_by_warehouse[self.store_wh], 0)
		self.assertEqual(total_by_warehouse[self.dept_a_wh], 0)

		reversal_rows = [r for r in rows if r.movement_type == "Reversal"]
		self.assertEqual(len(reversal_rows), 2)
