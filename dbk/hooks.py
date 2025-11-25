app_name = "dbk"
app_title = "DBK"
app_publisher = "Nidhin Venu"
app_description = "to contain all customisations"
app_email = "nidhin@enestsolutions.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "dbk",
# 		"logo": "/assets/dbk/logo.png",
# 		"title": "DBK",
# 		"route": "/dbk",
# 		"has_permission": "dbk.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/dbk/css/dbk.css"
# app_include_js = "/assets/dbk/js/dbk.js"
#app_include_js = [
#    "/assets/dbk/js/request_for_quotation_custom.js"
#]
# include js, css files in header of web template
# web_include_css = "/assets/dbk/css/dbk.css"
# web_include_js = "/assets/dbk/js/dbk.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "dbk/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
    "Material Request": "public/js/material_request.js",
    #"Request for Quotation": "dbk/public/js/request_for_quotation_custom.js"
    
}


# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "dbk/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "dbk.utils.jinja_methods",
# 	"filters": "dbk.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "dbk.install.before_install"
# after_install = "dbk.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "dbk.uninstall.before_uninstall"
# after_uninstall = "dbk.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "dbk.utils.before_app_install"
# after_app_install = "dbk.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "dbk.utils.before_app_uninstall"
# after_app_uninstall = "dbk.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "dbk.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }

permission_query_conditions = {
    "Stock Entry": "dbk.api.stock_entry.stock_entry_permission_query"
}

has_permission = {
    "Stock Entry": "dbk.api.stock_entry.stock_entry_has_permission"
}
# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events
doc_events = {
    "Purchase Order": {
        "autoname": "dbk.api.purchase_order.autoname",
        "before_submit": [
            "dbk.api.utils.update_approver"
        ]
    },

    "Stock Entry": {
        "on_update": [
            "dbk.api.stock_entry.share_stock_entry_on_review"
        ],
        "before_validate": [
            "dbk.api.stock_entry.before_save"
        ],
        "before_submit": [
            "dbk.api.stock_entry.check_receive_permission",
            "dbk.api.utils.update_approver",
        ],
    },

    "Material Request": {
        "before_save": [
            "dbk.api.material_request.sync_item_bin_qtys"
        ],
        "before_submit": [
            "dbk.api.utils.update_approver"
        ]
    },

    "Request for Quotation": {
        "before_submit": [
            "dbk.api.utils.update_approver"
        ]
    },

    "Supplier Quotation": {
        "before_submit": [
            "dbk.api.utils.update_approver"
        ]
    },

    "Purchase Receipt": {
        "before_submit": [
            "dbk.api.utils.update_approver"
        ]
    },

    "Purchase Invoice": {
        "before_submit": [
            "dbk.api.utils.update_approver"
        ]
    },

    "Supplier Quotation": {
        "before_submit": [
            "dbk.api.utils.update_approver"
        ]
    },


    # 🔥 NEW — Workflow approval tracking
    #"*": {
    #    "before_save": [
    #        "dbk.api.utils.capture_workflow_approver"
    #    ]
    #}
}




# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"dbk.tasks.all"
# 	],
# 	"daily": [
# 		"dbk.tasks.daily"
# 	],
# 	"hourly": [
# 		"dbk.tasks.hourly"
# 	],
# 	"weekly": [
# 		"dbk.tasks.weekly"
# 	],
# 	"monthly": [
# 		"dbk.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "dbk.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "dbk.event.get_events"
# }

# API endpoint for actual stock

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "dbk.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["dbk.utils.before_request"]
# after_request = ["dbk.utils.after_request"]

# Job Events
# ----------
# before_job = ["dbk.utils.before_job"]
# after_job = ["dbk.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"dbk.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# this is to test the hook get updaed through git