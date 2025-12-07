import frappe
from frappe import _
from frappe.utils import cint


def share_stock_entry_on_review(doc, method):
    """
    When a Stock Entry moves to 'Review', share it with all users who have
    permission for the target warehouse.
    """
    if doc.workflow_state != "Reviewed":
        return

    target_warehouse = doc.to_warehouse
    if not target_warehouse:
        frappe.logger().info(f"[SHARE DEBUG] No warehouse found in Stock Entry {doc.name}")
        return

    users = frappe.get_all(
        "User Permission",
        filters={"allow": "Warehouse", "for_value": target_warehouse},
        pluck="user"
    )

    if not users:
        frappe.logger().info(f"[SHARE DEBUG] No users found for warehouse {target_warehouse}")
        return

    for user in users:
        if frappe.db.exists(
            "DocShare",
            {"share_doctype": "Stock Entry", "share_name": doc.name, "user": user}
        ):
            continue

        frappe.share.add(
            doctype="Stock Entry",
            name=doc.name,
            user=user,
            read=1,
            write=1,
            submit=1,
            share=0,
            everyone=0
        )

    frappe.logger().info(f"[SHARE DEBUG] Shared {doc.name} with: {', '.join(users)}")


def check_receive_permission(doc, method=None):
    """
    Allow 'Receive' workflow action if the user has permission for
    the Stock Entry's target warehouse, even if ERPNext would normally
    block access to the document due to warehouse-based user permissions.
    """

    form_dict = frappe.local.form_dict or {}
    action = (form_dict.get("action") or "").lower()

    # Only enforce for "receive" action
    if action != "receive":
        return

    user = frappe.session.user

    # Always allow System Manager or Store Manager
    if set(frappe.get_roles(user)).intersection({"System Manager", "Store Manager"}):
        return

    allowed_warehouses = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Warehouse"},
        pluck="for_value"
    )

    if not allowed_warehouses:
        return

    # If target warehouse matches user permission, override permission safely
    if doc.to_warehouse and doc.to_warehouse in allowed_warehouses:
        frappe.logger().info(f"[PERMISSION OVERRIDE] User {user} allowed to Receive Stock Entry {doc.name}")

        # Temporarily ignore all permission checks
        frappe.flags.ignore_permissions = True
        frappe.flags.ignore_links = True
        frappe.flags.ignore_validate_update_after_submit = True
        frappe.flags.in_workflow_override = True

        #  Explicitly set doc flags to bypass Frappe's doctype-level permission
        doc.flags.ignore_permissions = True
        doc.flags.ignore_links = True
        doc.flags.ignore_validate_update_after_submit = True
        doc.flags.in_workflow_override = True

        # Give the user temporary permission at runtime (bypass role check)
        #frappe.set_user_permlevel(user, doc.doctype, 0, {
        #    "read": 1,
        #    "write": 1,
        #    "submit": 1
        #})

        return  # Allow action

    # Otherwise deny explicitly
    frappe.throw(
        _("You are not permitted to Receive this entry. "
          f"Your allowed warehouses: {', '.join(allowed_warehouses)}. "
          f"This Stock Entry's target warehouse: {doc.to_warehouse}."),
        frappe.PermissionError,
    )


def stock_entry_permission_query(user):
    if set(frappe.get_roles(user)).intersection({"System Manager", "Store Manager"}):
        return None

    allowed_warehouses = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Warehouse"},
        pluck="for_value"
    )

    if not allowed_warehouses:
        return None

    warehouse_list = ", ".join([f"'{w}'" for w in allowed_warehouses])
    return (
        f"(`tabStock Entry`.`to_warehouse` IN ({warehouse_list}) "
        f"OR `tabStock Entry`.`from_warehouse` IN ({warehouse_list}))"
    )


def stock_entry_has_permission(doc, user):
    if set(frappe.get_roles(user)).intersection({"System Manager", "Store Manager"}):
        return True

    allowed_warehouses = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Warehouse"},
        pluck="for_value"
    )

    if not allowed_warehouses:
        return True

    if (doc.to_warehouse and doc.to_warehouse in allowed_warehouses) or (
        doc.from_warehouse and doc.from_warehouse in allowed_warehouses
    ):
        return True

    return False

def before_save(doc, method=None):
    # Only run this check if workflow_state is not in excluded list
    if doc.workflow_state in ["Reviewed", "Received", "Rejected", "Submitted"]:
        return
    try:
        doc.material_request = doc.item[0].material_request
    except Exception as e:
        pass
    for item in doc.items:

        if not item.s_warehouse:
            continue

        is_group = frappe.db.get_value("Warehouse", item.s_warehouse, "is_group")

        if not is_group:
            continue

        # Get child warehouses under the group
        lft, rgt = frappe.db.get_value("Warehouse", item.s_warehouse, ["lft", "rgt"])
        child_warehouses = frappe.get_all(
            "Warehouse",
            filters={"lft": [">", lft], "rgt": ["<", rgt]},
            pluck="name"
        )

        # Collect warehouses that have stock
        warehouses_with_stock = []
        for wh in child_warehouses:
            qty = frappe.db.get_value(
                "Bin",
                {"item_code": item.item_code, "warehouse": wh},
                "actual_qty"
            )
            if qty and qty > 0:
                warehouses_with_stock.append((wh, qty))

        # ------------------------
        # CASE 1: NO STOCK FOUND
        # ------------------------
        if not warehouses_with_stock:
            frappe.throw(
                f"❌ The selected warehouse <b>{item.s_warehouse}</b> is a "
                f"<b>Group Warehouse</b> for item <b>{item.item_code}</b>.<br><br>"
                "❌ No child warehouses currently have available stock for this item."
            )

        # ------------------------
        # CASE 2: MULTIPLE WAREHOUSES HAVE STOCK
        # ------------------------
        if len(warehouses_with_stock) > 1:
            stock_details = "<br>".join(
                [f"<b>{item.item_code}</b> is available in <b>{wh}</b> with Qty <b>{qty}</b>"
                 for wh, qty in warehouses_with_stock]
            )
            frappe.throw(
                f"❌ Multiple child warehouses under <b>{item.s_warehouse}</b> have available stock "
                f"for item <b>{item.item_code}</b>:<br><br>{stock_details}<br><br>"
                "Please select the correct warehouse manually."
            )

        # ------------------------
        # CASE 3: EXACTLY ONE WAREHOUSE HAS STOCK
        # ------------------------
        selected_wh, selected_qty = warehouses_with_stock[0]

        # Update the source warehouse safely
        item.s_warehouse = selected_wh
        
        frappe.msgprint(
            f"✔ Auto-selected warehouse <b>{selected_wh}</b> for item <b>{item.item_code}</b> "
            f"(Available Qty: <b>{selected_qty}</b>)",
            alert=True
        )
