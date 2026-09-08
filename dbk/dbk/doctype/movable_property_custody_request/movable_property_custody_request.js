// Copyright (c) 2026, Nidhin Venu and contributors
// For license information, please see license.txt

frappe.ui.form.on("Movable Property Custody Request", {
	onload(frm) {
		frm.set_query("return_against", () => ({
			query: "dbk.api.property_custody.return_against_query",
		}));
	},

	refresh(frm) {
		apply_labels(frm);
		toggle_return_fields(frm);
	},

	is_return(frm) {
		if (!frm.doc.is_return) {
			frm.set_value("return_against", null);
			frm.set_value("source_warehouse", null);
			frm.set_value("target_warehouse", null);
		}
		toggle_return_fields(frm);
		apply_labels(frm);
	},

	return_against(frm) {
		if (!frm.doc.return_against) {
			return;
		}
		frappe.call({
			method: "dbk.api.property_custody.get_return_defaults",
			args: { request_name: frm.doc.return_against },
			callback(r) {
				if (!r.message) {
					return;
				}
				frm.set_value("source_warehouse", r.message.source_warehouse);
				frm.set_value("target_warehouse", r.message.target_warehouse);
				frm.clear_table("items");
				(r.message.outstanding_items || []).forEach((row) => {
					const child = frm.add_child("items");
					child.item_code = row.item_code;
					child.item_name = row.item_name;
					child.stock_uom = row.stock_uom;
					child.unit_tag = row.unit_tag;
					child.qty = row.qty;
				});
				frm.refresh_field("items");
				if (!(r.message.outstanding_items || []).length) {
					frappe.msgprint(__("Nothing is currently outstanding against {0}.", [frm.doc.return_against]));
				}
			},
		});
	},
});

function apply_labels(frm) {
	const is_return = cint(frm.doc.is_return);
	frm.set_df_property(
		"source_warehouse",
		"label",
		is_return ? __("Returning From (current custody)") : __("Issuing / Lending Warehouse")
	);
	frm.set_df_property(
		"target_warehouse",
		"label",
		is_return ? __("Return To (original store)") : __("Receiving Department")
	);
}

function toggle_return_fields(frm) {
	const is_return = cint(frm.doc.is_return);
	frm.toggle_reqd("return_against", is_return);
	frm.toggle_display("required_by", !is_return);
	frm.set_df_property("source_warehouse", "read_only", is_return ? 1 : 0);
	frm.set_df_property("target_warehouse", "read_only", is_return ? 1 : 0);
}
