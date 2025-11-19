// apps/dbk/dbk/public/js/material_request.js

frappe.ui.form.on("Material Request Item", {
    item_code(frm, cdt, cdn) {
        update_row_qty(frm, cdt, cdn);
    },
    from_warehouse(frm, cdt, cdn) {
        update_row_qty(frm, cdt, cdn);
    },
    warehouse(frm, cdt, cdn) {
        update_row_qty(frm, cdt, cdn);
    }
});

function update_row_qty(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row) return;
    if (!row.item_code) return;

    // Debounce/abort logic can be added if needed; simple calls are fine for typical MR sizes.

    // SOURCE (from_warehouse) -> custom_actual_qty
    if (row.from_warehouse) {
        frappe.call({
            method: "dbk.api.stock.get_actual_qty",
            args: {
                item_code: row.item_code,
                warehouse: row.from_warehouse
            },
            callback: function(r) {
                const val = (r && r.message) ? r.message : 0;
                frappe.model.set_value(cdt, cdn, "custom_actual_qty", val);
            }
        });
    } else {
        frappe.model.set_value(cdt, cdn, "custom_actual_qty", 0);
    }

    // TARGET (warehouse) -> actual_qty_target
    if (row.warehouse) {
        frappe.call({
            method: "dbk.api.stock.get_actual_qty",
            args: {
                item_code: row.item_code,
                warehouse: row.warehouse
            },
            callback: function(r) {
                const val = (r && r.message) ? r.message : 0;
                frappe.model.set_value(cdt, cdn, "actual_qty_target", val);
            }
        });
    } else {
        frappe.model.set_value(cdt, cdn, "actual_qty_target", 0);
    }
}
