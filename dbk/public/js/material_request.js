// ======================================================================
//  Material Request – Custom Enhancements (dbk)
//  - Restrict schedule_date
//  - User warehouse filtering + auto-assign
//  - Prevent selecting group warehouses
//  - Show stock availability inside group children
//  - Auto-update stock availability fields in child rows
// ======================================================================

frappe.ui.form.on("Material Request", {
    
    refresh(frm) { /*
        // --------------------------------------------------------------
        // 1️⃣ Restrict schedule_date (parent level) to today onward
        // --------------------------------------------------------------
        if (frm.fields_dict.schedule_date) {
            frm.fields_dict.schedule_date.datepicker.update({
                minDate: frappe.datetime.str_to_obj(frappe.datetime.get_today())
            });
        }

        // --------------------------------------------------------------
        // 2️⃣ Restrict child schedule_date to parent schedule_date
        // --------------------------------------------------------------
        frm.fields_dict.items.grid.update_docfield_property(
            "schedule_date",
            "min_date",
            frm.doc.schedule_date || frappe.datetime.get_today()
        );

        // --------------------------------------------------------------
        // 3️⃣ Fetch allowed warehouses for this user
        // --------------------------------------------------------------
        frappe.call({
            method: "dbk.api.warehouse.get_user_warehouses",
            callback: function (r) {
                let allowed = r.message || [];

                // Filter for parent-level warehouse (set_warehouse)
                frm.set_query("set_warehouse", function () {
                    if (allowed.length > 1) {
                        return { filters: { name: ["in", allowed] } };
                    } else if (allowed.length === 1) {
                        return { filters: { name: allowed[0] } };
                    } else {
                        return {};
                    }
                });

                // Auto-fill if user has exactly 1 warehouse
                if (allowed.length === 1) {
                    frm.set_value("set_warehouse", allowed[0]);
                }

                // Prevent clearing when only 1 warehouse
                frm.fields_dict["set_warehouse"].df.onchange = () => {
                    if (allowed.length === 1 && !frm.doc.set_warehouse) {
                        frm.set_value("set_warehouse", allowed[0]);
                    }
                };

                // Apply warehouse restriction to child table
                frm.fields_dict.items.grid.get_field("warehouse").get_query = function () {
                    if (allowed.length > 1) {
                        return { filters: { name: ["in", allowed] } };
                    } else if (allowed.length === 1) {
                        return { filters: { name: allowed[0] } };
                    } else {
                        return {};
                    }
                };
            }
        });
    },

    // --------------------------------------------------------------
    // 4️⃣ Validate: Prevent Group Warehouse on items
    // --------------------------------------------------------------
    validate(frm) {
        let promises = [];

        (frm.doc.items || []).forEach(item => {
            if (!item.warehouse) return;

            promises.push(
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "Warehouse",
                        filters: { name: item.warehouse },
                        fieldname: ["is_group", "lft", "rgt"]
                    }
                }).then(res => {
                    let data = res.message;
                    if (!data || !data.is_group) return;

                    // Fetch children of this group warehouse
                    return frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Warehouse",
                            fields: ["name"],
                            filters: {
                                lft: [">", data.lft],
                                rgt: ["<", data.rgt]
                            }
                        }
                    }).then(childRes => {
                        let children = childRes.message || [];
                        let stockChecks = [];

                        children.forEach(ch => {
                            stockChecks.push(
                                frappe.call({
                                    method: "frappe.client.get_value",
                                    args: {
                                        doctype: "Bin",
                                        filters: {
                                            item_code: item.item_code,
                                            warehouse: ch.name
                                        },
                                        fieldname: "actual_qty"
                                    }
                                }).then(qtyRes => {
                                    return {
                                        wh: ch.name,
                                        qty: qtyRes.message?.actual_qty
                                    };
                                })
                            );
                        });

                        return Promise.all(stockChecks).then(results => {
                            let available = results.filter(r => r.qty > 0);

                            if (available.length > 0) {
                                let msg = available
                                    .map(r =>
                                        `<b>${item.item_code}</b> is available in <b>${r.wh}</b> (Qty <b>${r.qty}</b>)`
                                    )
                                    .join("<br>");

                                frappe.msgprint({
                                    title: "Invalid Warehouse (Group Selected)",
                                    indicator: "red",
                                    message:
                                        `❌ <b>${item.warehouse}</b> is a <b>Group Warehouse</b>.<br><br>` +
                                        `Available stock found in:<br><br>${msg}`
                                });

                                frappe.validated = false;
                            } else {
                                frappe.msgprint({
                                    title: "Invalid Warehouse (Group Selected)",
                                    indicator: "red",
                                    message:
                                        `❌ <b>${item.warehouse}</b> is a <b>Group Warehouse</b>.<br><br>` +
                                        `No stock is available in any child warehouse.`
                                });

                                frappe.validated = false;
                            }
                        });
                    });
                })
            );
        });

        return Promise.all(promises); */
    }
});

// ======================================================================
// 5️⃣ CHILD TABLE : Auto-update actual_qty & target qty
// ======================================================================

frappe.ui.form.on("Material Request Item", {
    item_code(frm, cdt, cdn) {
        update_row_qty(frm, cdt, cdn);
    },
    from_warehouse(frm, cdt, cdn) {
        update_row_qty(frm, cdt, cdn);
    },
    warehouse(frm, cdt, cdn) {
        update_row_qty(frm, cdt, cdn);
    },
});

function update_row_qty(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row || !row.item_code) return;

    // Source warehouse → custom_actual_qty
    if (row.from_warehouse) {
        frappe.call({
            method: "dbk.api.stock.get_actual_qty",
            args: {
                item_code: row.item_code,
                warehouse: row.from_warehouse
            },
            callback: function(r) {
                frappe.model.set_value(cdt, cdn, "custom_actual_qty", r?.message || 0);
            }
        });
    } else {
        frappe.model.set_value(cdt, cdn, "custom_actual_qty", 0);
    }

    // Target warehouse → actual_qty_target
    if (row.warehouse) {
        frappe.call({
            method: "dbk.api.stock.get_actual_qty",
            args: {
                item_code: row.item_code,
                warehouse: row.warehouse
            },
            callback: function(r) {
                frappe.model.set_value(cdt, cdn, "actual_qty_target", r?.message || 0);
            }
        });
    } else {
        frappe.model.set_value(cdt, cdn, "actual_qty_target", 0);
    }
}
