# in your app, e.g., your_app/api/warehouse.py
import frappe
from frappe import _

@frappe.whitelist()
def get_user_warehouses():
    """
    Returns the list of warehouses allowed for the current user.
    Does not require user to have read access to User Permission.
    """
    user = frappe.session.user
    # Fetch User Permissions safely
    permissions = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Warehouse", "apply_to_all_doctypes": 1},
        fields=["for_value"]
    )
    # Return list of allowed warehouses
    return [p.for_value for p in permissions]
