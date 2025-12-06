# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint
from frappe.utils.nestedset import get_descendants_of

def execute(filters=None):
	return DBKItemBalanceReport(filters).run()


class DBKItemBalanceReport:
	def __init__(self, filters=None):
		self.filters = filters or {}
		self.data = []
		self.columns = []
		
	def run(self):
		self.float_precision = cint(frappe.db.get_default("float_precision")) or 3
		self.columns = self.get_columns()
		self.data = self.get_data()
		return self.columns, self.data
	
	def get_columns(self):
		return [
			{
				"label": _("Item Code"),
				"fieldname": "item_code",
				"fieldtype": "Link",
				"options": "Item",
				"width": 150,
			},
			{
				"label": _("Item Name"),
				"fieldname": "item_name",
				"fieldtype": "Data",
				"width": 200,
			},
			{
				"label": _("Item Group"),
				"fieldname": "item_group",
				"fieldtype": "Link",
				"options": "Item Group",
				"width": 120,
			},
			{
				"label": _("Warehouse"),
				"fieldname": "warehouse",
				"fieldtype": "Link",
				"options": "Warehouse",
				"width": 150,
			},
			{
				"label": _("Parent Warehouse"),
				"fieldname": "parent_warehouse",
				"fieldtype": "Link",
				"options": "Warehouse",
				"width": 150,
			},
			{
				"label": _("Stock UOM"),
				"fieldname": "stock_uom",
				"fieldtype": "Link",
				"options": "UOM",
				"width": 80,
			},
			{
				"label": _("Current Balance"),
				"fieldname": "bal_qty",
				"fieldtype": "Float",
				"width": 120,
			},
			{
				"label": _("Valuation Rate"),
				"fieldname": "valuation_rate",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"label": _("Balance Value"),
				"fieldname": "bal_value",
				"fieldtype": "Currency",
				"width": 120,
			},
		]
	
	def get_data(self):
		"""Get all stock items from Item Master and lookup their balances"""
		
		# Get warehouses to query - expand parent warehouses to include children
		warehouses = self.get_warehouses_to_query()
		
		if not warehouses:
			frappe.msgprint(_("Please select at least one warehouse"), indicator="red")
			return []
		
		# Step 1: Get ALL items from Item Master based on filters
		items = self.get_all_items()
		
		if not items:
			frappe.msgprint(_("No items found matching the criteria"), indicator="orange")
			return []
		
		# Debug: Log item count
		frappe.msgprint(_("Found {0} items in Item Master").format(len(items)), indicator="blue", alert=True)
		
		# Step 2: Get stock balances for these items (VLOOKUP equivalent)
		stock_balances = self.get_stock_balances(items, warehouses)
		
		# Debug: Log balance records count
		frappe.msgprint(_("Found {0} balance records in Bin").format(len(stock_balances)), indicator="blue", alert=True)
		
		# Step 3: Build the report data - ALL items x ALL warehouses
		data = []
		include_zero = self.filters.get("include_zero_stock_items", 0)
		
		items_added = 0
		items_skipped = 0
		
		for item in items:
			for warehouse_info in warehouses:
				warehouse = warehouse_info['warehouse']
				parent_warehouse = warehouse_info['parent_warehouse']
				
				# Lookup stock balance for this item-warehouse combination
				balance_key = (item['item_code'], warehouse)
				balance_info = stock_balances.get(balance_key, {})
				
				bal_qty = flt(balance_info.get('bal_qty', 0), self.float_precision)
				valuation_rate = flt(balance_info.get('valuation_rate', 0), self.float_precision)
				bal_value = flt(bal_qty * valuation_rate, self.float_precision)
				
				# Include row if it has stock or if include_zero is checked
				if include_zero or bal_qty != 0:
					data.append({
						'item_code': item['item_code'],
						'item_name': item['item_name'],
						'item_group': item['item_group'],
						'stock_uom': item['stock_uom'],
						'warehouse': warehouse,
						'parent_warehouse': parent_warehouse,
						'bal_qty': bal_qty,
						'valuation_rate': valuation_rate,
						'bal_value': bal_value
					})
					items_added += 1
				else:
					items_skipped += 1
		
		# Debug: Log final counts
		frappe.msgprint(
			_("Report: {0} rows added, {1} rows skipped (zero balance)").format(items_added, items_skipped),
			indicator="green",
			alert=True
		)
		
		return data
	
	def get_all_items(self):
		"""Get ALL items from Item Master based on filters (like Excel Item Master sheet)"""
		
		conditions = ["is_stock_item = 1", "disabled = 0"]
		query_params = []
		
		# Apply item group filter
		if self.filters.get("item_group"):
			item_groups = self.filters.get("item_group")
			if not isinstance(item_groups, list):
				item_groups = [item_groups]
			
			# Filter out empty values
			item_groups = [ig for ig in item_groups if ig]
			
			if item_groups:
				# Get all descendants of selected item groups
				all_item_groups = []
				for ig in item_groups:
					all_item_groups.append(ig)
					all_item_groups.extend(get_descendants_of("Item Group", ig, ignore_permissions=True))
				
				conditions.append(f"item_group IN ({', '.join(['%s'] * len(all_item_groups))})")
				query_params.extend(all_item_groups)
		
		# Apply item code filter
		if self.filters.get("item_code"):
			item_codes = self.filters.get("item_code")
			if not isinstance(item_codes, list):
				item_codes = [item_codes]
			
			# Filter out empty values
			item_codes = [ic for ic in item_codes if ic]
			
			if item_codes:
				conditions.append(f"item_code IN ({', '.join(['%s'] * len(item_codes))})")
				query_params.extend(item_codes)
		
		# Get all items from Item Master
		query = f"""
			SELECT 
				item_code,
				item_name,
				item_group,
				stock_uom
			FROM `tabItem`
			WHERE {' AND '.join(conditions)}
			ORDER BY item_code
		"""
		
		items = frappe.db.sql(query, tuple(query_params), as_dict=1)
		return items
	
	def get_stock_balances(self, items, warehouses):
		"""Get stock balances for items (like Excel Stock Balance sheet for VLOOKUP)"""
		
		if not items or not warehouses:
			return {}
		
		item_codes = [item['item_code'] for item in items]
		warehouse_names = [wh['warehouse'] for wh in warehouses]
		
		# Query to get actual stock balances from Bin table
		# NOTE: Only items with Bin records will be returned
		# Items without any stock transactions won't have Bin records
		query = """
			SELECT 
				item_code,
				warehouse,
				COALESCE(actual_qty, 0) as bal_qty,
				COALESCE(valuation_rate, 0) as valuation_rate
			FROM `tabBin`
			WHERE item_code IN ({item_codes})
			AND warehouse IN ({warehouses})
		""".format(
			item_codes=', '.join(['%s'] * len(item_codes)),
			warehouses=', '.join(['%s'] * len(warehouse_names))
		)
		
		balances = frappe.db.sql(query, tuple(item_codes + warehouse_names), as_dict=1)
		
		# Create a dictionary for easy lookup: (item_code, warehouse) -> balance_info
		balance_dict = {}
		for balance in balances:
			key = (balance['item_code'], balance['warehouse'])
			balance_dict[key] = {
				'bal_qty': balance['bal_qty'],
				'valuation_rate': balance['valuation_rate']
			}
		
		# Return the dictionary - items not in this dict will default to 0 balance
		# This is correct - items without Bin records have never had stock
		return balance_dict
	
	def get_warehouses_to_query(self):
		"""Get list of warehouses with their parent info, expanding parent warehouses to include children"""
		selected_warehouses = self.filters.get("warehouse")
		
		if not selected_warehouses:
			# If no warehouse selected, return empty list - user must select warehouse
			return []
		
		if not isinstance(selected_warehouses, list):
			selected_warehouses = [selected_warehouses]
		
		# Filter out empty values
		selected_warehouses = [wh for wh in selected_warehouses if wh]
		
		if not selected_warehouses:
			return []
		
		# Expand parent warehouses to include all children
		all_warehouse_names = []
		for warehouse in selected_warehouses:
			all_warehouse_names.append(warehouse)
			# Get all child warehouses
			children = get_descendants_of("Warehouse", warehouse, ignore_permissions=True)
			all_warehouse_names.extend(children)
		
		# Remove duplicates
		all_warehouse_names = list(set(all_warehouse_names))
		
		# Get warehouse details including parent warehouse
		if not all_warehouse_names:
			return []
		
		query = """
			SELECT 
				name as warehouse,
				parent_warehouse
			FROM `tabWarehouse`
			WHERE name IN ({warehouses})
			AND disabled = 0
			ORDER BY parent_warehouse, name
		""".format(
			warehouses=', '.join(['%s'] * len(all_warehouse_names))
		)
		
		warehouses = frappe.db.sql(query, tuple(all_warehouse_names), as_dict=1)
		return warehouses