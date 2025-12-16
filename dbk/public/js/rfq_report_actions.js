// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
// File: apps/dbk/dbk/public/js/rfq_report_actions.js

frappe.query_reports["RFQ Items from Material Request Enhanced"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        if (column.fieldname == "purchase_uom" && data && data.uom != data.purchase_uom) {
            value = "<span style='color: #ff6600; font-weight: bold;'>" + value + "</span>";
        }
        
        if (column.fieldname == "conversion_factor" && data && data.conversion_factor != 1) {
            value = "<span style='color: #0066ff; font-weight: bold;'>" + value + "</span>";
        }
        
        return value;
    },
    
    "onload": function(report) {
        report.page.add_inner_button(__("Create RFQ"), function() {
            let selected_rows = report.get_checked_items();
            
            if (selected_rows.length === 0) {
                frappe.msgprint(__("Please select at least one item to convert to RFQ"));
                return;
            }
            
            create_rfq_dialog(selected_rows, report);
        }, __("Actions"));
    }
};

function create_rfq_dialog(selected_rows, report) {
    let grouped_items = {};
    let total_items = 0;
    
    selected_rows.forEach(row => {
        if (!grouped_items[row.material_request]) {
            grouped_items[row.material_request] = [];
        }
        grouped_items[row.material_request].push(row);
        total_items++;
    });
    
    let dialog = new frappe.ui.Dialog({
        title: __("Create Request for Quotation"),
        fields: [
            {
                fieldname: "summary_html",
                fieldtype: "HTML",
                options: get_summary_html(grouped_items, total_items)
            },
            {
                fieldname: "section_break_1",
                fieldtype: "Section Break"
            },
            {
                fieldname: "schedule_date",
                label: __("Required By Date"),
                fieldtype: "Date",
                default: frappe.datetime.add_days(frappe.datetime.get_today(), 7),
                reqd: 1
            },
            {
                fieldname: "section_break_2",
                fieldtype: "Section Break"
            },
            {
                fieldname: "suppliers",
                label: __("Select Suppliers"),
                fieldtype: "Table",
                cannot_add_rows: false,
                in_place_edit: true,
                reqd: 1,
                fields: [
                    {
                        fieldname: "supplier",
                        fieldtype: "Link",
                        in_list_view: 1,
                        label: __("Supplier"),
                        options: "Supplier",
                        reqd: 1,
                        get_query: function() {
                            return {
                                filters: {"disabled": 0}
                            };
                        }
                    }
                ]
            },
            {
                fieldname: "section_break_3",
                fieldtype: "Section Break"
            },
            {
                fieldname: "message_for_supplier",
                label: __("Message for Supplier"),
                fieldtype: "Text Editor",
                default: "Dear Supplier,\n\nWe would like to request a quotation for the items listed below.\n\nPlease provide your best prices and delivery terms.\n\nThank you."
            }
        ],
        size: "large",
        primary_action_label: __("Create RFQ"),
        primary_action: function(values) {
            if (!values.suppliers || values.suppliers.length === 0) {
                frappe.msgprint(__("Please select at least one supplier"));
                return;
            }
            
            dialog.hide();
            create_rfq_from_items(selected_rows, values, report);
        }
    });
    
    dialog.show();
}

function get_summary_html(grouped_items, total_items) {
    let html = `
        <div style="padding: 10px; background-color: #f0f4f7; border-radius: 5px; margin-bottom: 10px;">
            <h5 style="margin-top: 0;">Summary</h5>
            <p><strong>Total Items Selected:</strong> ${total_items}</p>
            <p><strong>Material Requests:</strong> ${Object.keys(grouped_items).length}</p>
            <ul style="margin-bottom: 0;">
    `;
    
    for (let mr_name in grouped_items) {
        html += `<li>${mr_name} (${grouped_items[mr_name].length} items)</li>`;
    }
    
    html += `
            </ul>
            <p style="margin-top: 10px; color: #666; font-size: 0.9em;">
                <strong>Note:</strong> All items will be converted to quantity 1 with their Purchase UOM in the RFQ.
            </p>
        </div>
    `;
    
    return html;
}

function create_rfq_from_items(selected_rows, dialog_values, report) {
    frappe.dom.freeze(__("Creating Request for Quotation..."));
    
    let items = selected_rows.map(row => ({
        material_request: row.material_request,
        item_code: row.item_code,
        item_name: row.item_name,
        qty: row.qty,
        uom: row.uom,
        purchase_uom: row.purchase_uom,
        conversion_factor: row.conversion_factor,
        qty_in_purchase_uom: row.qty_in_purchase_uom,
        schedule_date: row.schedule_date,
        warehouse: row.warehouse,
        mr_item_name: row.mr_item_name,
        rate: row.rate
    }));
    
    let suppliers = dialog_values.suppliers.map(s => ({
        supplier: s.supplier
    }));
    
    frappe.call({
        method: "dbk.dbk.rfq_utils.create_rfq_from_material_requests",
        args: {
            items: items,
            suppliers: suppliers,
            schedule_date: dialog_values.schedule_date,
            message_for_supplier: dialog_values.message_for_supplier
        },
        callback: function(r) {
            frappe.dom.unfreeze();
            
            if (r.message && r.message.name) {
                frappe.show_alert({
                    message: __("Request for Quotation {0} created successfully", 
                        ['<a href="/app/request-for-quotation/' + r.message.name + '">' + r.message.name + '</a>']),
                    indicator: "green"
                }, 10);
                
                frappe.confirm(
                    __("RFQ {0} created successfully. Do you want to open it?", [r.message.name]),
                    function() {
                        frappe.set_route("Form", "Request for Quotation", r.message.name);
                    },
                    function() {
                        report.refresh();
                    }
                );
            }
        },
        error: function(r) {
            frappe.dom.unfreeze();
            frappe.msgprint({
                title: __("Error"),
                message: __("Failed to create RFQ. Error: {0}", [r.message || "Unknown error"]),
                indicator: "red"
            });
            console.error("RFQ Creation Error:", r);
        }
    });
}