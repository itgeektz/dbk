frappe.ui.form.on("Material Request Item", {
    item_code(frm, cdt, cdn) {
        update_qty_for_both(frm, cdt, cdn);
    },
    from_warehouse(frm, cdt, cdn) {
        update_qty_for_both(frm, cdt, cdn);
    },
    warehouse(frm, cdt, cdn) {
        update_qty_for_both(frm, cdt, cdn);
    }
});


function update_qty_for_both(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    if (row.item_code) {

        // Source warehouse (from_warehouse) → custom_actual_qty
        if (row.from_warehouse) {
            frappe.call({
                method: "dbk.api.stock.get_actual_qty",
                args: {
                    item_code: row.item_code,
                    warehouse: row.from_warehouse
                },
                callback(r) {
                    frappe.model.set_value(cdt, cdn, "custom_actual_qty", r.message || 0);
                }
            });
        } else {
            frappe.model.set_value(cdt, cdn, "custom_actual_qty", 0);
        }

        // Target warehouse (warehouse) → actual_qty_target
        if (row.warehouse) {
            frappe.call({
                method: "dbk.api.stock.get_actual_qty",
                args: {
                    item_code: row.item_code,
                    warehouse: row.warehouse
                },
                callback(r) {
                    frappe.model.set_value(cdt, cdn, "actual_qty_target", r.message || 0);
                }
            });
        } else {
            frappe.model.set_value(cdt, cdn, "actual_qty_target", 0);
        }
    }
}
