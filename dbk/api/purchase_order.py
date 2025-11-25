import frappe
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime

def autoname(doc, method=None):
    # safe project text (no spaces, no dots)
    project = (doc.project or "GE").strip().replace(" ", "-").replace(".", "-")

    # month and year two-digit
    dt = now_datetime()
    month = dt.strftime("%m")
    year = dt.strftime("%y")

    # IMPORTANT: put a dot (.) BEFORE the numeric placeholder
    # so series key becomes: DBK PO-<project>-MM-YY-.<#####>
    key = f"DBK PO-{project}-{month}-{year}-."

    # Generate name — make_autoname expects the dot before #####
    doc.name = make_autoname(key + "#####")
