// Copyright (c) 2025, Enest and contributors
// For license information, please see license.txt

frappe.ui.form.on('RFQ Meeting', {
    refresh: function(frm) {
        // Add button to load items
        if (!frm.doc.__islocal && !frm.doc.item_selections.length) {
            frm.add_custom_button(__('Load RFQ Items'), function() {
                frm.call('load_rfq_items').then(() => {
                    frm.refresh_field('item_selections');
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

function load_default_committee_members(frm) {
    // Fetch default committee members from server
    // This pulls from a configurable settings DocType
    frappe.call({
        method: 'dbk.dbk.doctype.rfq_meeting.rfq_meeting.get_default_committee_members',
        callback: function(r) {
            if (r.message) {
                r.message.forEach(member => {
                    frm.add_child('committee_members', {
                        member_name: member.member_name,
                        position: member.position
                    });
                });
                frm.refresh_field('committee_members');
            }
        }
    });
}