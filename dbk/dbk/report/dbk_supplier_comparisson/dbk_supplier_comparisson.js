// File: dbk/public/js/dbk_supplier_comparisson.js

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
    // Button: Print DBK Comparison Format
    report.page.add_inner_button(__("Print Comparison"), async function () {
      await printComparison(report);
    });

    // Button: Create Purchase Orders
    report.page.add_inner_button(__("Create Purchase Orders"), async function () {
      await createPurchaseOrders(report);
    }, __("Actions"));

    // Button: Auto-Select Lowest
    report.page.add_inner_button(__("Auto-Select Lowest Bidders"), async function () {
      await autoSelectLowest(report);
    }, __("Actions"));
  },
};

// ============================================
// Print Comparison Function
// ============================================
async function printComparison(report) {
  const filters = frappe.query_report.get_values() || {};
  if (!filters.request_for_quotation) {
    frappe.msgprint("Please select a Request for Quotation first.");
    return;
  }

  const result = await frappe.call({
    method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.execute",
    args: { filters },
  });

  const [columns, data, summary, schedule_date] = result.message || [[], [], {}, null];
  if (!data || !data.length) {
    frappe.msgprint("No data found for this RFQ.");
    return;
  }

  // Extract supplier names
  const supplierNames = Object.keys(summary);

  // Determine lowest bidders
  const lowestBidders = new Set();
  data.forEach(row => {
    if (row.min_rate !== null && row.min_rate !== undefined) {
      supplierNames.forEach(supplier => {
        const rate = row[`${supplier}_rate`];
        if (rate !== null && rate !== undefined && Math.abs(rate - row.min_rate) < 0.01) {
          lowestBidders.add(supplier);
        }
      });
    }
  });

  let lowestBidderText = "";
  if (lowestBidders.size === 1) {
    lowestBidderText = Array.from(lowestBidders)[0];
  } else if (lowestBidders.size > 1) {
    lowestBidderText = Array.from(lowestBidders).map(s => `<u>${s}</u>`).join(", ");
  } else {
    lowestBidderText = "__________________________";
  }

  // Build table rows
  let htmlRows = "";
  data.forEach((row, idx) => {
    htmlRows += "<tr>";
    htmlRows += `<td>${idx + 1}</td>`;
    htmlRows += `<td>${row.item_name || "-"}</td>`;
    htmlRows += `<td>${row.qty || "-"}</td>`;
    
    supplierNames.forEach(supplier => {
      const rate = row[`${supplier}_rate`];
      const formatted = row[`${supplier}_rate_formatted`] || "-";
      const isMin = rate !== null && row.min_rate !== null && Math.abs(rate - row.min_rate) < 0.01;
      htmlRows += `<td style="text-align:right;" class="${isMin ? "highlight-min" : ""}">${formatted}</td>`;
    });
    
    htmlRows += "</tr>";
  });

  // Summary totals 
let summaryHtml = `<table>
  <tr>
    <th style="text-align:center;">Details</th>
    ${supplierNames.map(s => `<th style="text-align:center;">${s}</th>`).join("")}
  </tr>`;

const fields = ["subtotal", "taxes", "total","payment_terms", "contact_person", "contact_number"];
const labels = ["Sub-total", "Taxes (if any)", "TOTAL", "Terms of Payment", "Contact Person", "Contact Number"];


labels.forEach((label, idx) => {

  // Determine alignment based on column index
  let alignment = idx < 3 ? "right" : "left";

  summaryHtml += `
    <tr>
      <td style="text-align:center;"><strong>${label}</strong></td>
      ${supplierNames.map(name => {
        const info = summary[name] || {};
        const field = fields[idx];
        return `<td style="text-align:${alignment};">${info?.[field] || "-"}</td>`;
      }).join("")}
    </tr>`;
});

// Get justification from first supplier (it's the same for all)
const firstSupplier = supplierNames[0];
const justification = summary[firstSupplier]?.justification || "";

// Add as a row in the summary table
if (justification && justification.trim()) {
  const escapedJustification = $('<div>').text(justification).html();  // ✅ Define it here
  
  summaryHtml += `
    <tr>
      <td style="text-align:center;"><strong>Committee's Recommendation and Conclusion:</strong></td>
      <td colspan="${supplierNames.length}" style="text-align:left; padding: 10px;">
        ${escapedJustification}
      </td>
    </tr>`;
}
summaryHtml += `</table>`;


  summaryHtml += `<tr><td><strong>Delivery Schedule</strong></td><td colspan="${supplierNames.length}">${schedule_date || "-"}</td></tr>`;
  summaryHtml += "</table>";

  // Full printable HTML
  const html = `
    <html>
    <head>
      <title>Supplier Comparison - ${filters.request_for_quotation}</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 25px; font-size: 13px; }
        h2, h4 { text-align: center; margin: 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th { border: 1px solid #000; padding: 5px; text-align: center; }
        td { border: 1px solid #000; padding: 5px;}
        th { background: #f8f8f8; font-weight: 600; }
        td:first-child { text-align: left; }
        .highlight-min { background-color: #d4edda; font-weight: bold; }
        .minutes { margin: 20px 0; }
      </style>
    </head>
    <body>
      <h2>${filters.company || ""}</h2>
      <h4>Quotation Comparison - ${filters.request_for_quotation}</h4>
      
      <div class="minutes">
        <h4>MINUTES OF THE COMMITTEE MEETING ON BIDS ANALYSIS SUMMARY AND SELECTION</h4>
        <p><strong>Date:</strong> ____________________ at __________</p>
        <p><strong>MEMBERS PRESENT</strong></p>
        <ol>
          <li>Francis Mbiu</li>
          <li>Silas Njiru</li>
          <li>Judy Wamalwa</li>
        </ol>
        <p><strong>AGENDA</strong></p>
        <p>Review of the Requests sent and the Quotation received from various suppliers.</p>
        <p>The Quotations were received from ${supplierNames.join(", ") || "__________________________"}.</p>
        <p>The committee members discussed and agreed on the following as shown in the table below:</p>
        <p style="text-align:center; font-weight:bold;">BIDS ANALYSIS SUMMARY (BAS)</p>
      </div>
      
      <table>
        <thead>
          <tr>
            <th>Sl No</th>
            <th>Item</th>
            <th>Qty</th>
            ${supplierNames.map(s => `<th>${s} Rate</th>`).join("")}
          </tr>
        </thead>
        <tbody>${htmlRows}</tbody>
      </table>

      ${summaryHtml}


      <div style="margin-top:30px;">
        <p><strong>System's Analysis:</strong> ${lowestBidderText} has offered lowest prices.</p>
        
        <p>The above conclusions are correct and we testify to that:</p>
        <table>
          <tr>
            <td><strong>Name</strong></td>
            <td>Francis Mbiu</td>
            <td>Silas Njiru</td>
            <td>Judy Wamalwa</td>
          </tr>
          <tr>
            <td><strong>Position</strong></td>
            <td>Administrator</td>
            <td>Academic Dean</td>
            <td>Supply & Logistics</td>
          </tr>
          <tr>
            <td><strong>Sign</strong></td>
            <td>…………………</td>
            <td>……………………</td>
            <td>……………………</td>
          </tr>
        </table>
      </div>

      <div style="margin-top:10px; font-size:11px;">
        <i>Highlighted cells indicate the lowest quoted rate per item.</i>
      </div>
    </body>
    </html>
  `;

  const printWin = window.open("", "_blank");
  printWin.document.write(html);
  printWin.document.close();
  printWin.print();
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
    // No ties, proceed directly
    proceedWithPurchaseOrders(data.lowest_selections, filters.request_for_quotation);
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
      reqd: 1
    });
  });

  const d = new frappe.ui.Dialog({
    title: __("Select Supplier for Tied Items"),
    fields: fields,
    primary_action_label: __("Create Purchase Orders"),
    primary_action: function(values) {
      // Merge auto-selected and user-selected
      const final_selections = { ...data.lowest_selections, ...values };
      d.hide();
      proceedWithPurchaseOrders(final_selections, rfq);
    }
  });

  d.show();
}

// ============================================
// Create Purchase Orders
// ============================================
async function createPurchaseOrders(report) {
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
  
  // Build selection dialog
  const fields = [];
  
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
    primary_action_label: __("Create Purchase Orders"),
    primary_action: async function(values) {
      d.hide();
      await proceedWithPurchaseOrders(values, filters.request_for_quotation);
    }
  });

  d.show();
}

// ============================================
// Proceed with PO Creation
// ============================================
async function proceedWithPurchaseOrders(selections, rfq) {
  frappe.show_alert({
    message: __("Creating Purchase Orders..."),
    indicator: "blue"
  });

  try {
    const result = await frappe.call({
      method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.create_purchase_orders",
      args: {
        rfq: rfq,
        supplier_selections: selections
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