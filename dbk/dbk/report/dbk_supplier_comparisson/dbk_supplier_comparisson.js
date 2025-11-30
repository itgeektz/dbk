// File: dbk/dbk/report/dbk_supplier_comparisson/dbk_supplier_comparisson.js

frappe.query_reports["DBK Supplier Comparisson"] = {
  filters: [
    {
      fieldtype: "Link",
      label: __("Company"),
      options: "Company",
      fieldname: "company",
      default: frappe.defaults.get_user_default("Company"),
      reqd: 1,
    },
    {
      fieldname: "from_date",
      label: __("From Date"),
      fieldtype: "Date",
      default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
      reqd: 1,
    },
    {
      fieldname: "to_date",
      label: __("To Date"),
      fieldtype: "Date",
      default: frappe.datetime.get_today(),
      reqd: 1,
    },
    {
      fieldtype: "Link",
      label: __("Request for Quotation"),
      options: "Request for Quotation",
      fieldname: "request_for_quotation",
      reqd: 1,
    },
    {
      fieldname: "supplier",
      label: __("Supplier"),
      fieldtype: "MultiSelectList",
      options: "Supplier",
      get_data: function (txt) {
        return frappe.db.get_link_options("Supplier", txt);
      },
    },
  ],

  formatter: function(value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);
    
    // Highlight cells with minimum rate
    if (column.fieldname.endsWith("_rate_formatted") && data) {
      const supplier = column.fieldname.replace("_rate_formatted", "");
      const rate_field = supplier + "_rate";
      
      if (data[rate_field] !== null && data[rate_field] !== undefined && 
          data.min_rate !== null && data.min_rate !== undefined) {
        
        // Use a small epsilon for floating point comparison
        if (Math.abs(data[rate_field] - data.min_rate) < 0.01) {
          value = `<div style="background-color: #d4edda; font-weight: bold; padding: 4px;">${value}</div>`;
        }
      }
    }
    
    return value;
  },

  onload: function (report) {
    // Button: Print Simple Comparison
    report.page.add_inner_button(__("Print Simple Comparison"), async function () {
      await printSimpleComparison(report);
    });

    // Button: Create Meeting & POs
    report.page.add_inner_button(__("Create Meeting"), async function () {
      await createMeetingAndPOs(report);
    }, __("Actions"));

    // Button: Quick Create POs (Legacy)
    report.page.add_inner_button(__("Quick Create Purchase Orders"), async function () {
      await createPurchaseOrdersQuick(report);
    }, __("Actions"));

    // Button: Auto-Select Lowest
    report.page.add_inner_button(__("Auto-Select Lowest Bidders"), async function () {
      await autoSelectLowest(report);
    }, __("Actions"));
  },
};

// ============================================
// Print Simple Comparison
// ============================================
async function printSimpleComparison(report) {
  const filters = frappe.query_report.get_values() || {};
  if (!filters.request_for_quotation) {
    frappe.msgprint("Please select a Request for Quotation first.");
    return;
  }

  // Get the print format name - EXACT match required
  const print_format = "Simple Supplier Comparison";
  const rfq_name = filters.request_for_quotation;
  
  // Build print URL with explicit format parameter
  const print_url = frappe.urllib.get_full_url(
    `/printview?`
    + `doctype=${encodeURIComponent("Request for Quotation")}`
    + `&name=${encodeURIComponent(rfq_name)}`
    + `&format=${encodeURIComponent(print_format)}`
    + `&no_letterhead=0`
    + `&trigger_print=1`
  );
  
  frappe.show_alert({
    message: __('Opening print preview...'),
    indicator: 'blue'
  }, 3);
  
  // Open in new window
  const print_window = window.open(print_url, '_blank');
  
  if (!print_window) {
    frappe.msgprint({
      title: __('Popup Blocked'),
      message: __('Please allow popups for this site to view the print format.'),
      indicator: 'orange'
    });
  }
}

// ============================================
// Create Meeting & Purchase Orders
// ============================================
async function createMeetingAndPOs(report) {
  const filters = frappe.query_report.get_values() || {};
  if (!filters.request_for_quotation) {
    frappe.msgprint("Please select a Request for Quotation first.");
    return;
  }

  // Get RFQ details
  const rfq = await frappe.db.get_doc('Request for Quotation', filters.request_for_quotation);
  
  // Get comparison data
  const result = await frappe.call({
    method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.execute",
    args: { filters },
  });

  const [columns, data, summary] = result.message || [[], [], {}];
  if (!data || !data.length) {
    frappe.msgprint("No data found for this RFQ.");
    return;
  }

  const supplierNames = Object.keys(summary);
  
  // Build selection dialog with project and date
  const fields = [
    {
      fieldtype: "Section Break",
      label: __("Purchase Order Details")
    },
    {
      fieldname: "project",
      label: __("Project"),
      fieldtype: "Link",
      options: "Project",
      default: rfq.project || "GE",
      reqd: 1,
      description: "Select the project for this purchase"
    },
    {
      fieldname: "required_date",
      label: __("Required By Date"),
      fieldtype: "Date",
      default: rfq.schedule_date || frappe.datetime.get_today(),
      reqd: 1,
      description: "Delivery date for all purchase orders"
    },
    {
      fieldtype: "Column Break"
    },
    {
      fieldname: "meeting_date",
      label: __("Meeting Date"),
      fieldtype: "Date",
      default: frappe.datetime.get_today(),
      reqd: 1
    },
    {
      fieldname: "meeting_time",
      label: __("Meeting Time"),
      fieldtype: "Time",
      default: "10:00:00",
      reqd: 1
    },
    {
      fieldtype: "Section Break",
      label: __("Supplier Selection for Each Item")
    }
  ];
  
  // Add item selection fields
  data.forEach(row => {
    const options = supplierNames.filter(s => {
      const rate = row[`${s}_rate`];
      return rate !== null && rate !== undefined;
    });
    
    if (options.length === 0) return;
    
    // Pre-select lowest
    let default_supplier = options[0];
    if (row.min_rate !== null) {
      options.forEach(s => {
        const rate = row[`${s}_rate`];
        if (Math.abs(rate - row.min_rate) < 0.01) {
          default_supplier = s;
        }
      });
    }
    
    fields.push({
      fieldtype: "Select",
      label: `${row.item_name} (Qty: ${row.qty})`,
      fieldname: `item_${row.item_code}`,
      options: options.join("\n"),
      default: default_supplier,
      reqd: 1,
      description: `Lowest: ${row[`${default_supplier}_rate_formatted`]}`
    });
  });

  // Add meeting notes section
  fields.push(
    {
      fieldtype: "Section Break",
      label: __("Meeting Notes")
    },
    {
      fieldname: "agenda",
      label: __("Agenda"),
      fieldtype: "Small Text",
      default: "Review of the Requests sent and the Quotation received from various suppliers."
    },
    /*
    {
      fieldname: "justification",
      label: __("Justification"),
      fieldtype: "Text Editor",
      default: rfq.justification || ""
    },
    */
    {
      fieldtype: "Section Break",
      label: __("Committee Members (Optional)")
    },
    {
      fieldname: "load_default_members",
      label: __("Load Default Committee Members"),
      fieldtype: "Check",
      default: 1,
      description: "Uncheck to add members manually after creating the meeting"
    }
  );

  const d = new frappe.ui.Dialog({
    title: __("Create Meeting and Purchase Orders"),
    fields: fields,
    size: "large",
    primary_action_label: __("Create Meeting"),
    primary_action: async function(values) {
      d.hide();
      await createMeetingDocument(values, data, filters.request_for_quotation);
    },
    secondary_action_label: __("Cancel")
  });

  d.show();
}

// ============================================
// Create Meeting Document
// ============================================
async function createMeetingDocument(values, data, rfq) {
  frappe.show_alert({
    message: __("Creating RFQ Meeting..."),
    indicator: "blue"
  });

  try {
    // Extract item selections
    const item_selections = [];
    data.forEach(row => {
      const fieldname = `item_${row.item_code}`;
      if (values[fieldname]) {
        item_selections.push({
          item_code: row.item_code,
          item_name: row.item_name,
          qty: row.qty,
          uom: row.uom,
          selected_supplier: values[fieldname]
        });
      }
    });

    // Get RFQ doc for company
    const rfq_doc = await frappe.db.get_doc('Request for Quotation', rfq);

    // Get default committee members from server if requested
    let committee_members = [];
    if (values.load_default_members) {
      const members_result = await frappe.call({
        method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.get_default_committee_members"
      });
      
      if (members_result.message) {
        committee_members = members_result.message;
      }
    }

    // Create meeting
    const meeting = await frappe.call({
      method: "frappe.client.insert",
      args: {
        doc: {
          doctype: "RFQ Meeting",
          request_for_quotation: rfq,
          company: rfq_doc.company,
          meeting_date: values.meeting_date,
          meeting_time: values.meeting_time,
          project: values.project,
          required_date: values.required_date,
          agenda: values.agenda,
          // justification: values.justification,
          committee_members: committee_members,
          item_selections: item_selections
        }
      }
    });

    const meeting_name = meeting.message.name;

    frappe.show_alert({
      message: __(`Meeting ${meeting_name} created successfully`),
      indicator: "green"
    }, 5);

    // Ask if user wants to submit immediately
    frappe.confirm(
      __("Meeting created."),
      async () => {
        // User chose not to submit, just open the meeting
        frappe.set_route("Form", "RFQ Meeting", meeting_name);
      }
    ); /*=> {
        try {
          await frappe.call({
            method: "frappe.client.submit",
            args: {
              doc: meeting.message
            }
          });

          frappe.show_alert({
            message: __("Meeting submitted and Purchase Orders created!"),
            indicator: "green"
          }, 10);

          // Open the meeting
          frappe.set_route("Form", "RFQ Meeting", meeting_name);
        } catch (error) {
          frappe.msgprint(__("Error submitting meeting: " + error.message));
          frappe.set_route("Form", "RFQ Meeting", meeting_name);
        }
      },
      () => {
        // User chose not to submit, just open the meeting
        frappe.set_route("Form", "RFQ Meeting", meeting_name);
      }
    ); */

  } catch (error) {
    frappe.msgprint(__("Error creating meeting: " + error.message));
  }
}

// ============================================
// Quick Create POs (Legacy - no meeting)
// ============================================
async function createPurchaseOrdersQuick(report) {
  const filters = frappe.query_report.get_values() || {};
  if (!filters.request_for_quotation) {
    frappe.msgprint("Please select a Request for Quotation first.");
    return;
  }

  // Get current data
  const result = await frappe.call({
    method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.execute",
    args: { filters },
  });

  const [columns, data, summary] = result.message || [[], [], {}];
  if (!data || !data.length) {
    frappe.msgprint("No data found for this RFQ.");
    return;
  }

  const supplierNames = Object.keys(summary);
  
  // Get RFQ details for defaults
  const rfq = await frappe.db.get_doc('Request for Quotation', filters.request_for_quotation);
  
  // Build selection dialog with project/date
  const fields = [
    {
      fieldtype: "Section Break",
      label: __("Purchase Order Settings")
    },
    {
      fieldname: "project",
      label: __("Project"),
      fieldtype: "Link",
      options: "Project",
      default: rfq.project || "GE",
      reqd: 1
    },
    {
      fieldname: "required_date",
      label: __("Required By Date"),
      fieldtype: "Date",
      default: rfq.schedule_date || frappe.datetime.get_today(),
      reqd: 1
    },
    {
      fieldtype: "Section Break",
      label: __("Select Supplier for Each Item")
    }
  ];
  
  data.forEach(row => {
    const options = supplierNames.filter(s => {
      const rate = row[`${s}_rate`];
      return rate !== null && rate !== undefined;
    });
    
    if (options.length === 0) return;
    
    // Pre-select lowest
    let default_supplier = options[0];
    if (row.min_rate !== null) {
      options.forEach(s => {
        const rate = row[`${s}_rate`];
        if (Math.abs(rate - row.min_rate) < 0.01) {
          default_supplier = s;
        }
      });
    }
    
    fields.push({
      fieldtype: "Select",
      label: `${row.item_name} (Qty: ${row.qty})`,
      fieldname: row.item_code,
      options: options.join("\n"),
      default: default_supplier,
      reqd: 1
    });
  });

  const d = new frappe.ui.Dialog({
    title: __("Select Supplier for Each Item"),
    fields: fields,
    size: "large",
    primary_action_label: __("Create Purchase Orders"),
    primary_action: async function(values) {
      d.hide();
      
      // Extract item selections
      const selections = {};
      data.forEach(row => {
        if (values[row.item_code]) {
          selections[row.item_code] = values[row.item_code];
        }
      });
      
      await proceedWithPurchaseOrders(
        selections, 
        filters.request_for_quotation,
        values.project,
        values.required_date
      );
    }
  });

  d.show();
}

// ============================================
// Auto-Select Lowest Bidders
// ============================================
async function autoSelectLowest(report) {
  const filters = frappe.query_report.get_values() || {};
  if (!filters.request_for_quotation) {
    frappe.msgprint("Please select a Request for Quotation first.");
    return;
  }

  const result = await frappe.call({
    method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.get_lowest_suppliers",
    args: { rfq: filters.request_for_quotation },
  });

  const data = result.message;
  if (!data) {
    frappe.msgprint("Error retrieving supplier data.");
    return;
  }

  if (Object.keys(data.ties).length > 0) {
    // Show dialog for tied items
    showTieDialog(data, filters.request_for_quotation);
  } else {
    // No ties, show confirmation
    const supplier_summary = {};
    Object.values(data.lowest_selections).forEach(s => {
      supplier_summary[s] = (supplier_summary[s] || 0) + 1;
    });
    
    const msg = Object.entries(supplier_summary)
      .map(([supplier, count]) => `${supplier}: ${count} item(s)`)
      .join("<br>");
    
    frappe.confirm(
      __(`Auto-selected lowest bidders:<br><br>${msg}<br><br>Proceed to create Purchase Orders?`),
      async () => {
        const rfq = await frappe.db.get_doc('Request for Quotation', filters.request_for_quotation);
        await proceedWithPurchaseOrders(
          data.lowest_selections, 
          filters.request_for_quotation,
          rfq.project || "GE",
          rfq.schedule_date || frappe.datetime.get_today()
        );
      }
    );
  }
}

// ============================================
// Show Dialog for Tied Items
// ============================================
function showTieDialog(data, rfq) {
  const fields = [];
  
  Object.keys(data.ties).forEach(item_code => {
    const tie = data.ties[item_code];
    fields.push({
      fieldtype: "Select",
      label: `${tie.item_name} (Rate: ${tie.rate})`,
      fieldname: item_code,
      options: tie.suppliers.join("\n"),
      reqd: 1,
      description: "Multiple suppliers quoted the same price"
    });
  });

  const d = new frappe.ui.Dialog({
    title: __("Select Supplier for Tied Items"),
    fields: fields,
    primary_action_label: __("Create Purchase Orders"),
    primary_action: async function(values) {
      // Merge auto-selected and user-selected
      const final_selections = { ...data.lowest_selections, ...values };
      d.hide();
      
      const rfq_doc = await frappe.db.get_doc('Request for Quotation', rfq);
      await proceedWithPurchaseOrders(
        final_selections, 
        rfq,
        rfq_doc.project || "GE",
        rfq_doc.schedule_date || frappe.datetime.get_today()
      );
    }
  });

  d.show();
}

// ============================================
// Proceed with PO Creation
// ============================================
async function proceedWithPurchaseOrders(selections, rfq, project, required_date) {
  frappe.show_alert({
    message: __("Creating Purchase Orders..."),
    indicator: "blue"
  });

  try {
    const result = await frappe.call({
      method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.create_purchase_orders",
      args: {
        rfq: rfq,
        supplier_selections: selections,
        project: project,
        required_date: required_date
      }
    });

    const pos = result.message || [];
    
    if (pos.length > 0) {
      frappe.show_alert({
        message: __(`Created ${pos.length} Purchase Order(s): ${pos.join(", ")}`),
        indicator: "green"
      }, 10);
      
      // Open first PO
      frappe.set_route("Form", "Purchase Order", pos[0]);
    } else {
      frappe.msgprint(__("No Purchase Orders were created."));
    }
  } catch (error) {
    frappe.msgprint(__("Error creating Purchase Orders: " + error.message));
  }
}