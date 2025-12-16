// Copyright (c) 2025, Frappe Technologies Pvt. Ltd.
// For license information, please see license.txt

/* ============================
   Report Definition
=============================== */

frappe.query_reports["RFQ Items from Material Request Enhanced"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "item_code",
            label: __("Item"),
            fieldtype: "Link",
            options: "Item"
        },
        {
            fieldname: "warehouse",
            label: __("Warehouse"),
            fieldtype: "Link",
            options: "Warehouse"
        },
        {
            fieldname: "workflow_state",
            label: __("Approval Status"),
            fieldtype: "Select",
            options: "\nDraft\nPending\nApproved\nRejected"
        }
    ],

    /* ============================
       Formatter
    =============================== */

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) return value;

        // Highlight Purchase UOM mismatch
        if (column.fieldname === "purchase_uom" && data.uom !== data.purchase_uom) {
            value = `<span style="color:#ff6600;font-weight:bold;">${value}</span>`;
        }

        // Highlight conversion factor
        if (column.fieldname === "conversion_factor" && data.conversion_factor !== 1) {
            value = `<span style="color:#0066ff;font-weight:bold;">${value}</span>`;
        }

        return value;
    },

    /* ============================
       On Load
    =============================== */

    onload: function (report) {

        // Create RFQ
        report.page.add_inner_button(__("Create RFQ"), function () {
            let selected_rows = get_checked_items(report);

            if (!selected_rows.length) {
                frappe.msgprint(__("Please select at least one item to convert to RFQ"));
                return;
            }

            convert_to_rfq(selected_rows, report);
        }, __("Actions"));

        // View UOM conversions
        report.page.add_inner_button(__("View UOM Conversions"), function () {
            let selected_rows = get_checked_items(report);

            if (!selected_rows.length) {
                frappe.msgprint(__("Please select items to view UOM details"));
                return;
            }

            show_uom_details(selected_rows);
        }, __("Actions"));

        // Select all rows
        report.page.add_inner_button(__("Select All"), function () {
            (report.data || []).forEach(row => row.select_row = 1);
            report.refresh();
        }, __("Actions"));

        // Clear selection
        report.page.add_inner_button(__("Clear Selection"), function () {
            (report.data || []).forEach(row => row.select_row = 0);
            report.refresh();
        }, __("Actions"));
        // Enable checkboxes after report renders
        setTimeout(() => {
            enable_checkboxes(report);
        }, 500);
    }
};

/* ============================
   Helpers
=============================== */

function get_checked_items(report) {
    return (report.checked_items || []);
}

/* ============================
   RFQ Conversion
=============================== */

function convert_to_rfq(selected_rows, report) {

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
        size: "large",
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "summary_html",
                options: get_summary_html(grouped_items, total_items)
            },
            { fieldtype: "Section Break" },
            {
                fieldname: "supplier_group",
                label: __("Supplier Group"),
                fieldtype: "Link",
                options: "Supplier Group",
                onchange() {
                    let group = dialog.get_value("supplier_group");
                    if (group) load_suppliers_by_group(group, dialog);
                }
            },
            { fieldtype: "Column Break" },
            {
                fieldname: "schedule_date",
                label: __("Required By Date"),
                fieldtype: "Date",
                default: frappe.datetime.add_days(frappe.datetime.get_today(), 7),
                reqd: 1
            },
            { fieldtype: "Section Break" },
            {
                fieldname: "suppliers",
                label: __("Suppliers"),
                fieldtype: "Table",
                reqd: 1,
                fields: [
                    {
                        fieldname: "supplier",
                        label: __("Supplier"),
                        fieldtype: "Link",
                        options: "Supplier",
                        in_list_view: 1,
                        reqd: 1
                    },
                    {
                        fieldname: "email_id",
                        label: __("Email"),
                        fieldtype: "Data",
                        in_list_view: 1,
                        read_only: 1
                    }
                ]
            },
            { fieldtype: "Section Break" },
            {
                fieldname: "message_for_supplier",
                label: __("Message for Supplier"),
                fieldtype: "Text Editor",
                default: get_default_message()
            }
        ],
        primary_action_label: __("Create RFQ"),
        primary_action(values) {

            if (!values.suppliers || !values.suppliers.length) {
                frappe.msgprint(__("Please select at least one supplier"));
                return;
            }

            dialog.hide();
            create_rfq_document(selected_rows, values, report);
        }
    });

    dialog.show();
}

/* ============================
   RFQ Utilities
=============================== */

function get_summary_html(grouped_items, total_items) {
    let html = `
        <div style="padding:10px;background:#f0f4f7;border-radius:6px">
            <h5>${__("Summary")}</h5>
            <p><b>${__("Total Items")}:</b> ${total_items}</p>
            <p><b>${__("Material Requests")}:</b> ${Object.keys(grouped_items).length}</p>
            <ul>
    `;

    Object.keys(grouped_items).forEach(mr => {
        html += `<li>${mr} (${grouped_items[mr].length})</li>`;
    });

    html += `
            </ul>
            <p style="color:#666;font-size:12px">
                ${__("Items will be converted using Purchase UOM.")}
            </p>
        </div>`;

    return html;
}

function get_default_message() {
    return `Dear Supplier,

Please provide your best quotation for the attached items.

Thank you.`;
}

function load_suppliers_by_group(group, dialog) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Supplier",
            filters: { supplier_group: group, disabled: 0 },
            fields: ["name", "email_id"],
            limit_page_length: 100
        },
        callback(r) {
            let grid = dialog.fields_dict.suppliers.grid;
            grid.df.data = [];
            grid.refresh();

            (r.message || []).forEach(s => {
                let row = grid.add_new_row();
                frappe.model.set_value(row.doctype, row.name, "supplier", s.name);
                frappe.model.set_value(row.doctype, row.name, "email_id", s.email_id);
            });
        }
    });
}

function create_rfq_document(selected_rows, values, report) {
    frappe.dom.freeze(__("Creating Request for Quotation..."));

    frappe.call({
        method: "dbk.dbk.report.rfq_items_from_material_request_enhanced.rfq_utils.create_rfq_from_material_requests",
        args: {
            items: selected_rows,
            suppliers: values.suppliers,
            schedule_date: values.schedule_date,
            message_for_supplier: values.message_for_supplier
        },
        callback(r) {
            frappe.dom.unfreeze();

            if (r.message) {
                frappe.show_alert({
                    message: __("RFQ {0} created successfully", [
                        `<a href="/app/request-for-quotation/${r.message.name}">${r.message.name}</a>`
                    ]),
                    indicator: "green"
                });

                frappe.confirm(
                    __("Do you want to open the RFQ?"),
                    () => frappe.set_route("Form", "Request for Quotation", r.message.name),
                    () => report.refresh()
                );
            }
        },
        error() {
            frappe.dom.unfreeze();
            frappe.msgprint({
                title: __("Error"),
                message: __("Failed to create RFQ"),
                indicator: "red"
            });
        }
    });
}

/* ============================
   UOM Viewer
=============================== */

function show_uom_details(rows) {
    let html = `
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Item</th>
                    <th>MR UOM</th>
                    <th>Purchase UOM</th>
                    <th>Conversion</th>
                    <th>Qty</th>
                    <th>Qty (Purchase)</th>
                </tr>
            </thead>
            <tbody>
    `;

    rows.forEach(r => {
        let hl = r.uom !== r.purchase_uom ? ' style="background:#fff3cd"' : '';
        html += `
            <tr${hl}>
                <td>${r.item_code}</td>
                <td>${r.uom}</td>
                <td>${r.purchase_uom}</td>
                <td>${r.conversion_factor}</td>
                <td>${r.qty}</td>
                <td>${r.qty_in_purchase_uom}</td>
            </tr>`;
    });

    html += `</tbody></table>`;

    frappe.msgprint({
        title: __("UOM Conversion Details"),
        message: html,
        wide: true
    });
}

// =====================================================================
// ENABLE CHECKBOXES FUNCTION
// =====================================================================

function enable_checkboxes(report) {
    console.log("Enabling checkboxes...");
    
    // Find all disabled checkboxes in the report
    let $checkboxes = $('.dt-cell__content input[type="checkbox"][disabled]');
    
    console.log("Found disabled checkboxes:", $checkboxes.length);
    
    // Enable them and add click handler
    $checkboxes.each(function(index) {
        let $checkbox = $(this);
        
        // Remove disabled attribute
        $checkbox.removeAttr('disabled');
        $checkbox.removeClass('disabled-deselected');
        
        // Add click handler
        $checkbox.off('click').on('click', function(e) {
            let is_checked = $(this).is(':checked');
            
            // Find the row index
            let $cell = $(this).closest('.dt-cell');
            let $row = $cell.closest('.dt-row');
            let row_index = $row.index();
            
            console.log("Checkbox clicked, row:", row_index, "checked:", is_checked);
            
            // Get row data
            if (report.data && report.data[row_index]) {
                let row_data = report.data[row_index];
                
                // Initialize checked_items if needed
                if (!report.checked_items) {
                    report.checked_items = [];
                }
                
                if (is_checked) {
                    // Add to checked items
                    let exists = report.checked_items.find(item => 
                        item.attendance === row_data.attendance
                    );
                    
                    if (!exists) {
                        report.checked_items.push(row_data);
                        console.log("Added to checked items:", row_data.attendance);
                    }
                } else {
                    // Remove from checked items
                    report.checked_items = report.checked_items.filter(item => 
                        item.attendance !== row_data.attendance
                    );
                    console.log("Removed from checked items:", row_data.attendance);
                }
                
                console.log("Total checked:", report.checked_items.length);
            }
        });
    });
    
    console.log("Checkboxes enabled!");
}