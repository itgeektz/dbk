# File: dbk/api/rfq_events.py
"""
API endpoints for creating calendar events from Request for Quotation
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def create_event_from_rfq(rfq_name, subject, event_category, starts_on, ends_on=None, 
                          all_day=0, send_reminder=1, description=None, participants=None):
    """
    Create a calendar event linked to an RFQ
    
    Args:
        rfq_name: Name of the Request for Quotation
        subject: Event subject/title
        event_category: Meeting, Call, Email, Other
        starts_on: Start date/time
        ends_on: End date/time (optional)
        all_day: Whether it's an all-day event
        send_reminder: Whether to send reminder
        description: Event description
        participants: JSON string of participant employees
    """
    try:
        # Verify RFQ exists
        if not frappe.db.exists("Request for Quotation", rfq_name):
            return {
                "success": False,
                "message": _("Request for Quotation {0} not found").format(rfq_name)
            }
        
        # Get RFQ document for additional details
        rfq_doc = frappe.get_doc("Request for Quotation", rfq_name)
        
        # Parse participants if string
        if isinstance(participants, str):
            try:
                # MultiSelect returns comma-separated values
                participants = [p.strip() for p in participants.split(',') if p.strip()]
            except:
                participants = []
        elif isinstance(participants, list):
            # If already a list, ensure all items are strings
            participants = [str(p).strip() for p in participants if p]
        else:
            participants = []
        
        # Create Event document
        event = frappe.new_doc("Event")
        event.subject = subject
        event.ref_doctype = "Request for Quotation"
        event.document_refrence = rfq_name
        event.event_category = event_category
        event.event_type = "Public"  # Public so all participants can see
        event.starts_on = starts_on
        event.all_day = int(all_day)
        event.send_reminder = int(send_reminder)
        event.status = "Open"
        
        # Set end time if provided and not all-day
        if ends_on and not all_day:
            event.ends_on = ends_on
        elif all_day:
            # For all-day events, set ends_on to end of day
            event.ends_on = frappe.utils.add_days(starts_on, 1)
        
        # Set description
        if description:
            event.description = description
        
        # Add event participants from employees
        if participants:
            for emp in participants:
                # Clean the employee name
                emp_name = str(emp).strip()
                
                if emp_name and frappe.db.exists("Employee", emp_name):
                    event.append("event_participants", {
                        "reference_doctype": "Employee",
                        "reference_docname": emp_name
                    })
        
        # Add RFQ suppliers as participants (optional)
        if hasattr(rfq_doc, 'suppliers') and rfq_doc.suppliers:
            for supplier in rfq_doc.suppliers:
                if supplier.contact and frappe.db.exists("Contact", supplier.contact):
                    event.append("event_participants", {
                        "reference_doctype": "Contact",
                        "reference_docname": supplier.contact
                    })
        
        # Set color based on category
        event.color = get_event_color(event_category)
        
        # Insert the event
        event.insert(ignore_permissions=False)
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _("Event created successfully"),
            "event_name": event.name
        }
        
    except frappe.PermissionError:
        return {
            "success": False,
            "message": _("You don't have permission to create events")
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Event from RFQ Error")
        return {
            "success": False,
            "message": _("Error creating event: {0}").format(str(e))
        }


def get_event_color(event_category):
    """Get color code for event category"""
    colors = {
        "Meeting": "#4CAF50",      # Green
        "Call": "#2196F3",         # Blue
        "Sent/Received Email": "#FF9800",  # Orange
        "Other": "#9C27B0"         # Purple
    }
    return colors.get(event_category, "#607D8B")  # Default gray


@frappe.whitelist()
def get_events_for_rfq(rfq_name):
    """
    Get all events linked to a specific RFQ
    
    Args:
        rfq_name: Name of the Request for Quotation
    
    Returns:
        List of events with details
    """
    try:
        events = frappe.get_all(
            "Event",
            filters={
                "ref_doctype": "Request for Quotation",
                "document_refrence": rfq_name
            },
            fields=[
                "name", "subject", "starts_on", "ends_on", 
                "event_category", "status", "all_day", 
                "description", "color"
            ],
            order_by="starts_on desc"
        )
        
        # Get participants for each event
        for event in events:
            participants = frappe.get_all(
                "Event Participants",
                filters={"parent": event.name},
                fields=["reference_doctype", "reference_docname"]
            )
            event["participants"] = participants
            event["participant_count"] = len(participants)
        
        return {
            "success": True,
            "events": events,
            "count": len(events)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Events for RFQ Error")
        return {
            "success": False,
            "message": str(e),
            "events": []
        }


@frappe.whitelist()
def update_event_status(event_name, status):
    """
    Update event status (Open/Closed/Cancelled)
    
    Args:
        event_name: Name of the event
        status: New status
    """
    try:
        if not frappe.db.exists("Event", event_name):
            return {
                "success": False,
                "message": _("Event not found")
            }
        
        event = frappe.get_doc("Event", event_name)
        event.status = status
        event.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _("Event status updated to {0}").format(status)
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def create_event_quick(rfq_name, days_from_now=1):
    """
    Quick event creation with minimal inputs
    Creates an event 'days_from_now' days ahead
    
    Args:
        rfq_name: Name of the RFQ
        days_from_now: How many days from now to schedule (default: 1)
    """
    try:
        rfq_doc = frappe.get_doc("Request for Quotation", rfq_name)
        
        # Calculate start time
        start_datetime = frappe.utils.add_days(frappe.utils.now_datetime(), int(days_from_now))
        # Set to 10:00 AM
        start_datetime = start_datetime.replace(hour=10, minute=0, second=0)
        
        # Calculate end time (2 hours later)
        end_datetime = frappe.utils.add_hours(start_datetime, 2)
        
        # Create event
        event = frappe.new_doc("Event")
        event.subject = f"Meeting: RFQ - {rfq_name}"
        event.ref_doctype = "Request for Quotation"
        event.document_refrence = rfq_name
        event.event_category = "Meeting"
        event.event_type = "Public"
        event.starts_on = start_datetime
        event.ends_on = end_datetime
        event.send_reminder = 1
        event.status = "Open"
        event.color = "#4CAF50"
        
        # Add description
        event.description = f"""Meeting for Request for Quotation: {rfq_name}
        
Company: {rfq_doc.company}
Transaction Date: {rfq_doc.transaction_date}
Schedule Date: {rfq_doc.schedule_date or 'Not set'}

Total Items: {len(rfq_doc.items) if rfq_doc.items else 0}
Total Suppliers: {len(rfq_doc.suppliers) if rfq_doc.suppliers else 0}
"""
        
        event.insert()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _("Quick event created"),
            "event_name": event.name,
            "starts_on": start_datetime
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Quick Event Creation Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_employee_from_user(user=None):
    """Get employee linked to current user"""
    if not user:
        user = frappe.session.user
    
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    return employee