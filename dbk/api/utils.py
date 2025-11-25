import frappe
from frappe.utils import getdate, get_fullname, nowdate

def update_approver(doc, method=None):
    """Update approved_by and approved_date fields if they exist"""
    doc.approved_by = get_fullname(frappe.session.user)
    doc.approved_date = nowdate()

