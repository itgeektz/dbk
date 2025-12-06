// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["DBK Material Request to Purchase"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "purpose",
            "label": __("Purpose"),
            "fieldtype": "Select",
            "options": "\nPurchase\nMaterial Transfer\nMaterial Issue\nManufacture\nCustomer Provided",
            "default": "Purchase"
        },
        {
            "fieldname": "target_warehouse",
            "label": __("Target Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "get_query": function() {
                return {
                    filters: {
                        "company": frappe.query_report.get_filter_value('company'),
                        "is_group": 0
                    }
                };
            }
        },
        {
            "fieldname": "source_warehouse",
            "label": __("Source Warehouse (Main Store)"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "get_query": function() {
                return {
                    filters: {
                        "company": frappe.query_report.get_filter_value('company')
                    }
                };
            }
        },
        {
            "fieldname": "remove_duplicates",
            "label": __("Consolidate Duplicate Items"),
            "fieldtype": "Check",
            "default": 1
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        if (column.fieldname == "status") {
            if (value == "Pending") {
                value = `<span class="indicator-pill orange">${value}</span>`;
            } else if (value == "Partially Ordered") {
                value = `<span class="indicator-pill yellow">${value}</span>`;
            } else if (value == "Ordered") {
                value = `<span class="indicator-pill green">${value}</span>`;
            } else if (value == "Cancelled") {
                value = `<span class="indicator-pill red">${value}</span>`;
            }
        }
        
        if (column.fieldname == "current_stock" && data) {
            if (flt(value) <= 0) {
                value = `<span style="color: red; font-weight: bold;">${value || 0}</span>`;
            } else if (flt(value) < flt(data.quantity)) {
                value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
            } else {
                value = `<span style="color: green;">${value}</span>`;
            }
        }
        
        return value;
    },
    
    "onload": function(report) {
        // Add button to create RFQ
        report.page.add_inner_button(__("Create Request for Quotation"), function() {
            let selected_items = [];
            let checked_rows = report.get_checked_items();
            
            if (checked_rows && checked_rows.length > 0) {
                selected_items = checked_rows;
            } else {
                // If no rows selected, show dialog to select items
                frappe.msgprint(__("Please select items by checking the checkboxes"));
                return;
            }
            
            // Show supplier selection dialog
            show_supplier_dialog(selected_items, report);
        });
        
        // Add button to export selected items
        report.page.add_inner_button(__("Export Selected Items"), function() {
            let checked_rows = report.get_checked_items();
            
            if (!checked_rows || checked_rows.length === 0) {
                frappe.msgprint(__("Please select items to export"));
                return;
            }
            
            // Export to Excel
            frappe.tools.downloadify(checked_rows, null, report);
        });
    }
};

function show_supplier_dialog(items, report) {
    // Create dialog for supplier selection
    let dialog = new frappe.ui.Dialog({
        title: __("Select Suppliers for RFQ"),
        fields: [
            {
                fieldname: "suppliers",
                label: __("Suppliers"),
                fieldtype: "MultiSelectList",
                reqd: 1,
                get_data: function(txt) {
                    return frappe.db.get_link_options("Supplier", txt, {
                        disabled: 0
                    });
                }
            },
            {
                fieldname: "items_html",
                fieldtype: "HTML"
            }
        ],
        primary_action_label: __("Create RFQ"),
        primary_action: function(values) {
            if (!values.suppliers || values.suppliers.length === 0) {
                frappe.msgprint(__("Please select at least one supplier"));
                return;
            }
            
            frappe.call({
                method: "dbk.dbk.report.dbk_material_request_to_purchase.dbk_material_request_to_purchase.create_rfq_from_report",
                args: {
                    items: items,
                    suppliers: values.suppliers
                },
                freeze: true,
                freeze_message: __("Creating Request for Quotation..."),
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __("Success"),
                            message: __("Request for Quotation {0} created successfully", [
                                `<a href="/app/request-for-quotation/${r.message}">${r.message}</a>`
                            ]),
                            indicator: "green"
                        });
                        dialog.hide();
                        report.refresh();
                    }
                }
            });
        }
    });
    
    // Show selected items
    let items_html = `
        <div class="selected-items">
            <h5>${__("Selected Items")} (${items.length})</h5>
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>${__("Item Code")}</th>
                        <th>${__("Quantity")}</th>
                        <th>${__("UOM")}</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    items.forEach(function(item) {
        items_html += `
            <tr>
                <td>${item.item_code}</td>
                <td>${item.quantity}</td>
                <td>${item.stock_uom}</td>
            </tr>
        `;
    });
    
    items_html += `
                </tbody>
            </table>
        </div>
    `;
    
    dialog.fields_dict.items_html.$wrapper.html(items_html);
    dialog.show();
}