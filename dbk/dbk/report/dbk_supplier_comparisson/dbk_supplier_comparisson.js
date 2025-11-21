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

  onload: function (report) {
    report.page.add_inner_button(__("Print DBK Comparison Format"), async function () {
      const filters = frappe.query_report.get_values() || {};
      if (!filters.request_for_quotation) {
        frappe.msgprint("Please select a Request for Quotation first.");
        return;
      }

      // 🟩 Fetch report data including summary and schedule_date
      const result = await frappe.call({
        method: "dbk.dbk.report.dbk_supplier_comparisson.dbk_supplier_comparisson.execute",
        args: { filters },
      });

      const [columns, data, summary, schedule_date] = result.message || [[], [], {}, null];
      if (!data || !data.length) {
        frappe.msgprint("No data found for this RFQ.");
        return;
      }

      // 🟦 Extract supplier names dynamically
      const supplierNames = [...new Set(Object.keys(data[0])
        .filter(k => k.endsWith("_rate"))
        .map(k => k.replace("_rate", "")))];

      // 🟩 Determine lowest bidders
      const lowestBidders = new Set();
      data.forEach(row => {
        const rateFields = Object.keys(row).filter(k => k.endsWith("_rate"));
        const rates = rateFields.map(k => row[k]).filter(r => r && r > 0);
        if (rates.length) {
          const min = Math.min(...rates);
          rateFields.forEach(k => {
            if (row[k] === min) lowestBidders.add(k.replace("_rate", ""));
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

      // 🟨 Build table rows
      let htmlRows = "";
      data.forEach(row => {
        const rateFields = Object.keys(row).filter(k => k.endsWith("_rate"));
        const rates = rateFields.map(k => row[k]).filter(r => r && r > 0);
        const min = rates.length ? Math.min(...rates) : null;

        htmlRows += "<tr>";
        columns.forEach(col => {
          const val = row[col.fieldname] ?? "-";
          const highlight = col.fieldname.endsWith("_rate") && val === min;
          htmlRows += `<td class="${highlight ? "highlight-min" : ""}">${val}</td>`;
        });
        htmlRows += "</tr>";
      });

      // 🟩 Summary totals and supplier info
      let summaryHtml = `<table><tr><th>Details</th>${supplierNames.map(s => `<th>${s}</th>`).join("")}</tr>`;
      const fields = ["subtotal", "taxes", "total", "payment_terms", "contact_person", "contact_number"];
      const labels = ["Sub-total", "Taxes (if any)", "TOTAL", "Terms of Payment", "Contact Person / No", ""];

      labels.forEach((label, idx) => {
        if (!label) return;
        summaryHtml += `<tr><td><strong>${label}</strong></td>`;
        supplierNames.forEach(name => {
          const info = summary[name] || {};
          const field = fields[idx];
          summaryHtml += `<td>${info?.[field] || "-"}</td>`;
        });
        summaryHtml += "</tr>";
      });

      // 🕓 Delivery Schedule Row
      summaryHtml += `<tr><td><strong>Delivery Schedule</strong></td><td colspan="${supplierNames.length}">${schedule_date || "-"}</td></tr>`;
      summaryHtml += "</table>";

      // 🟧 Full printable HTML
      const html = `
        <html>
        <head>
          <title>Supplier Comparison - ${filters.request_for_quotation}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 25px; font-size: 13px; }
            h2, h4 { text-align: center; margin: 0; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #000; padding: 5px; text-align: right; }
            th { background: #f8f8f8; font-weight: 600; }
            td:first-child { text-align: left; }
            .highlight-min { background-color: #d4edda; font-weight: bold; }
            .justify-section, .signature-section { margin-top: 30px; }
            .signature-section td { border: 1px solid #000; padding: 6px; }
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
            <thead><tr>${columns.map(c => `<th>${c.label}</th>`).join("")}</tr></thead>
            <tbody>${htmlRows}</tbody>
          </table>

          ${summaryHtml}

          <div class="justify-section">
            <p><strong>Justification:</strong> ${lowestBidderText} is preferred for having offered lowest prices.</p>
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
                <td>………………………</td>
                <td>…………………………</td>
                <td>…………………………</td>
              </tr>
            </table>
          </div>

          <div style="margin-top:10px; font-size:11px;">
            <i>Highlighted cells indicate the lowest quoted rate per item.</i>
          </div>
        </body>
        </html>
      `;

      // 🖨️ Print popup
      const printWin = window.open("", "_blank");
      printWin.document.write(html);
      printWin.document.close();
      printWin.print();
    });
  },
};

