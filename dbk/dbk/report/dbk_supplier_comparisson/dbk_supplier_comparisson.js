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
            th, td { border: 1px solid #000; padding: 5px; text-align: center; }
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

/*
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

  formatter: function (value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);

    // Highlight lowest rate
    if (column.fieldname && column.fieldname.endsWith("_rate")) {
      const supplier_rate_fields = Object.keys(row).filter((key) =>
        key.endsWith("_rate")
      );

      const all_rates = supplier_rate_fields
        .map((key) => row[key])
        .filter((r) => r != null && r > 0);

      if (all_rates.length > 0) {
        const min_rate = Math.min(...all_rates);
        const this_rate = row[column.fieldname];

        if (this_rate === min_rate) {
          value = `<div style="background-color:#d4edda; color:#155724; font-weight:600; border-radius:4px; padding:2px;">${value}</div>`;
        }
      }
    }

    return value;
  },

  onload: function (report) {
    // Add Print Button
    report.page.add_inner_button(
      __("Print DBK Comparison Format"),
      function () {
        const data = frappe.query_report.data || [];
        const columns = frappe.query_report.columns || [];
        const filters = frappe.query_report.get_values() || {};

        if (!data.length) {
          frappe.msgprint("No data to print.");
          return;
        }

        // Dynamically extract supplier names
        //const supplierNames = columns
        //  .filter((col) => col.fieldname && col.fieldname.endsWith("_rate"))
        //  .map((col) => col.label);

		const supplierNames = [...new Set(Object.keys(data[0]).filter(k => k.endsWith("_rate")).map(k => k.replace("_rate", "")))];


        // Determine lowest bidder(s)
        const lowestBidders = new Set();
        data.forEach((row) => {
          const rateFields = Object.keys(row).filter((k) =>
            k.endsWith("_rate")
          );
          const allRates = rateFields
            .map((key) => row[key])
            .filter((r) => r != null && r > 0);

          if (allRates.length > 0) {
            const minRate = Math.min(...allRates);
            rateFields.forEach((key) => {
              if (row[key] === minRate) {
                const supplierLabel = columns.find(
                  (col) => col.fieldname === key
                )?.label;
                if (supplierLabel) lowestBidders.add(supplierLabel);
              }
            });
          }
        });

        let lowestBidderText = "";
        if (lowestBidders.size === 1) {
          lowestBidderText = Array.from(lowestBidders)[0];
        } else if (lowestBidders.size > 1) {
          // Multiple lowest bidders — underline for physical filling
          lowestBidderText = Array.from(lowestBidders)
            .map((s) => `<u>${s}</u>`)
            .join(", ");
        } else {
          lowestBidderText = "__________________________";
        }

        // Generate printable HTML
        let html = `
          <html>
          <head>
            <title>QuotationComparison - ${filters.request_for_quotation || ""}</title>
            <style>
              body { font-family: Arial, sans-serif; margin: 30px; font-size: 13px; }
              h2, h4 { text-align: center; margin: 0; }
              table { width: 100%; border-collapse: collapse; margin-top: 15px; }
              th, td { border: 1px solid #000; padding: 6px; text-align: center; }
              th { background: #f8f8f8; font-weight: 600; }
              td:first-child { text-align: left; }
              .highlight-min { background-color: #d4edda; font-weight: bold; }
              .footer-note { margin-top: 10px; font-size: 11px; color: #555; text-align: left; }
              .signature-section { margin-top: 40px; font-size: 12px; width: 100%; }
              .signature-section table { width: 100%; border-collapse: collapse; font-size: 12px; }
              .signature-section td { border: 1px solid #000; padding: 8px; vertical-align: top; }
              .signature-section td.empty { border: none; width: 4%; }
              .minutes { margin-top: 25px; font-size: 13px; line-height: 1.6; text-align: justify; }
              .minutes h4 { text-align: center; margin-bottom: 10px; text-decoration: underline; }
              .justify-section { margin-top: 20px; font-size: 13px; }
              .justify-section table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }
              .justify-section td { padding: 4px; text-align: left; }
            </style>
          </head>
          <body>
            <h2>${filters.company || ""}</h2>
            <h4>Quotation Comparison</h4>

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
                  ${columns.map((col) => `<th>${col.label || ""}</th>`).join("")}
                </tr>
              </thead>
              <tbody>
        `;

        data.forEach((row) => {
          const rateFields = Object.keys(row).filter((k) => k.endsWith("_rate"));
          const allRates = rateFields
            .map((key) => row[key])
            .filter((r) => r != null && r > 0);
          const minRate = allRates.length ? Math.min(...allRates) : null;

          html += "<tr>";
          columns.forEach((col) => {
            const val = row[col.fieldname] ?? "";
            const isMin = col.fieldname.endsWith("_rate") && val === minRate;
            html += `<td class="${isMin ? "highlight-min" : ""}">${val || "-"}</td>`;
          });
          html += "</tr>";
        });

        // Justification + Approval section
        html += `
              </tbody>
            </table>
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

            <div class="footer-note">
              <p><i>Highlighted cells (green) indicate the lowest quoted rates per item.</i></p>
            </div>
		           
        `;

        const printWindow = window.open("", "_blank");
        printWindow.document.write(html);
        printWindow.document.close();
        printWindow.print();
      }
    );
  },
};

*/