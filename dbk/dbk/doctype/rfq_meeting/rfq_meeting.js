// Copyright (c) 2025, Enest and contributors
// For license information, please see license.txt

frappe.ui.form.on('RFQ Meeting', {
    refresh: function(frm) {
        // Add button to load items
        if (!frm.doc.__islocal && !frm.doc.item_selections.length) {
            frm.add_custom_button(__('Load RFQ Items'), function() {
                frm.call('load_rfq_items').then(() => {
                    frm.refresh_field('item_selections');
                    
                    // CRITICAL: Setup queries after loading items
                    setTimeout(() => {
                        setup_all_supplier_queries(frm);
                    }, 500);
                    
                    frappe.show_alert({
                        message: __('Items loaded from RFQ'),
                        indicator: 'green'
                    }, 3);
                });
            });
        }
        
        // Add button to view comparison
        if (frm.doc.request_for_quotation) {
            frm.add_custom_button(__('View Supplier Comparison'), function() {
                frappe.set_route('query-report', 'DBK Supplier Comparisson', {
                    request_for_quotation: frm.doc.request_for_quotation
                });
            });
        }
        
        // Add default committee members if empty (only for new docs)
        if (frm.doc.__islocal && !frm.doc.committee_members.length) {
            load_default_committee_members(frm);
        }
        
        // CRITICAL: Setup supplier queries for all existing rows on refresh
        if (frm.doc.item_selections && frm.doc.item_selections.length > 0) {
            setTimeout(() => {
                setup_all_supplier_queries(frm);
            }, 300);
        }
    },
    
    request_for_quotation: function(frm) {
        if (frm.doc.request_for_quotation) {
            // Fetch RFQ details
            frappe.db.get_doc('Request for Quotation', frm.doc.request_for_quotation)
                .then(rfq => {
                    if (!frm.doc.company) {
                        frm.set_value('company', rfq.company);
                    }
                    if (!frm.doc.required_date && rfq.schedule_date) {
                        frm.set_value('required_date', rfq.schedule_date);
                    }
                    if (!frm.doc.project && rfq.project) {
                        frm.set_value('project', rfq.project);
                    }
                    if (!frm.doc.justification && rfq.justification) {
                        frm.set_value('justification', rfq.justification);
                    }
                });
        }
    }
});

// ============================================================================
// CHILD TABLE: RFQ Meeting Item Selection
// ============================================================================
frappe.ui.form.on('RFQ Meeting Item Selection', {
    // When grid is rendered, setup query
    item_selections_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (!row.qty) {
            frappe.model.set_value(cdt, cdn, 'qty', 1);
        }
        
        // Setup query for the new row
        setTimeout(() => {
            setup_supplier_query_for_row(frm, cdn);
        }, 100);
    },
    
    // When supplier is changed
    selected_supplier: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (!row.selected_supplier || !frm.doc.request_for_quotation) {
            return;
        }
        
        // Show loading indicator
        frappe.show_alert({
            message: __('Fetching quotation details...'),
            indicator: 'blue'
        }, 2);
        
        // Fetch updated quotation details
        frappe.call({
            method: 'dbk.dbk.doctype.rfq_meeting.rfq_meeting.get_supplier_quotation_for_item',
            args: {
                rfq: frm.doc.request_for_quotation,
                supplier: row.selected_supplier,
                item_code: row.item_code
            },
            callback: function(r) {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'supplier_quotation', r.message.supplier_quotation);
                    frappe.model.set_value(cdt, cdn, 'quoted_rate', r.message.rate);
                    
                    frappe.show_alert({
                        message: __('Updated - Rate: {0}', [format_currency(r.message.rate)]),
                        indicator: 'green'
                    }, 5);
                    
                    frm.refresh_field('item_selections');
                } else {
                    frappe.show_alert({
                        message: __('No quotation found for this supplier and item'),
                        indicator: 'orange'
                    }, 5);
                    
                    frappe.model.set_value(cdt, cdn, 'supplier_quotation', null);
                    frappe.model.set_value(cdt, cdn, 'quoted_rate', 0);
                }
            },
            error: function(err) {
                console.error('Error fetching supplier quotation:', err);
                frappe.msgprint({
                    title: __('Error'),
                    message: __('Could not fetch supplier quotation details'),
                    indicator: 'red'
                });
            }
        });
    },
    
    // When item code changes
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (row.item_code) {
            // Clear previous selections
            frappe.model.set_value(cdt, cdn, 'selected_supplier', null);
            frappe.model.set_value(cdt, cdn, 'supplier_quotation', null);
            frappe.model.set_value(cdt, cdn, 'quoted_rate', 0);
            
            // Load available suppliers
            load_available_suppliers(frm, cdn);
            
            // Setup query
            setTimeout(() => {
                setup_supplier_query_for_row(frm, cdn);
            }, 100);
        }
    }
});

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Setup queries for ALL rows in the grid
 * This is the most reliable approach
 */
function setup_all_supplier_queries(frm) {
    if (!frm.doc.request_for_quotation) {
        console.log("No RFQ selected, skipping query setup");
        return;
    }
    
    if (!frm.doc.item_selections || frm.doc.item_selections.length === 0) {
        console.log("No items in selection, skipping query setup");
        return;
    }
    
    console.log(`Setting up queries for ${frm.doc.item_selections.length} items`);
    
    // Setup query for each row
    frm.doc.item_selections.forEach((row, idx) => {
        setup_supplier_query_for_row(frm, row.name);
    });
    
    // Refresh the grid to apply queries
    frm.refresh_field('item_selections');
}

/**
 * Setup query filter for a specific row
 */
function setup_supplier_query_for_row(frm, row_name) {
    if (!frm.doc.request_for_quotation) {
        return;
    }
    
    let row = frappe.get_doc(locals, 'RFQ Meeting Item Selection', row_name);
    
    if (!row || !row.item_code) {
        console.log(`Skipping query setup for row ${row_name} - no item_code`);
        return;
    }
    
    // Get the grid and the specific row
    let grid = frm.fields_dict['item_selections'].grid;
    let grid_row = grid.grid_rows_by_docname[row_name];
    
    if (!grid_row) {
        console.log(`Grid row not found for ${row_name}`);
        return;
    }
    
    // Get the supplier field
    let supplier_field = grid_row.get_field('selected_supplier');
    
    if (!supplier_field) {
        console.log(`Supplier field not found in row ${row_name}`);
        return;
    }
    
    // Set the query
    supplier_field.get_query = function() {
        return {
            query: 'dbk.dbk.doctype.rfq_meeting.rfq_meeting.get_suppliers_for_item',
            filters: {
                'request_for_quotation': frm.doc.request_for_quotation,
                'item_code': row.item_code
            }
        };
    };
    
    console.log(`Query setup complete for row ${row_name}, item: ${row.item_code}`);
}

/**
 * Load available suppliers text for an item
 */
function load_available_suppliers(frm, row_name) {
    let row = frappe.get_doc(locals, 'RFQ Meeting Item Selection', row_name);
    
    if (!frm.doc.request_for_quotation || !row || !row.item_code) {
        return;
    }
    
    frappe.call({
        method: 'dbk.dbk.doctype.rfq_meeting.rfq_meeting.get_available_suppliers_for_item',
        args: {
            rfq: frm.doc.request_for_quotation,
            item_code: row.item_code
        },
        callback: function(r) {
            if (r.message) {
                frappe.model.set_value('RFQ Meeting Item Selection', row_name, 'available_suppliers', r.message);
                console.log(`Available suppliers loaded for ${row.item_code}: ${r.message}`);
            }
        },
        error: function(err) {
            console.error('Error loading available suppliers:', err);
        }
    });
}

/**
 * Load default committee members
 */
function load_default_committee_members(frm) {
    frappe.call({
        method: 'dbk.dbk.doctype.rfq_meeting.rfq_meeting.get_default_committee_members',
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                r.message.forEach(member => {
                    frm.add_child('committee_members', {
                        member_name: member.member_name,
                        position: member.position
                    });
                });
                frm.refresh_field('committee_members');
                
                frappe.show_alert({
                    message: __('{0} committee members added', [r.message.length]),
                    indicator: 'blue'
                }, 3);
            }
        },
        error: function(err) {
            console.error('Error loading default committee members:', err);
        }
    });
}