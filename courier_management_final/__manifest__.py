{
    "name": "Courier Management System",
    "version": "1.0",
    "summary": "Courier-style request -> internal request order flow with FinCodeMaster and transit hubs",
    "depends": ["sale", "stock", "account", "mail", "sale_management", "purchase", "fleet", "portal",
                "vendor_dispatch_portal_v2"],
    "data": [
        "security/ir.model.access.csv",
        "views/report_request_order.xml",  # load report first (important)
        "views/report_request_order_v2.xml",
        "views/handoffsviews.xml",
        "views/stocklotviews.xml",
        "views/partner_views.xml",
        'views/handoff_wizard.xml',
        "views/data_sequences.xml",
        "views/codeware_menus_views.xml",
        "views/account_move_inherit_views.xml",
        "views/account_payment_views.xml",
        'views/stock_picking_inherit_views.xml',
        'report/report_handoff_wizard.xml',
        'report/report_handoff_wizard_template.xml',
        "report/report_courier_handoff.xml",
        "report/report_courier_handoff_template.xml",
        "views/sale_order_awb_view.xml",
        "views/purchase_order_awb_view.xml",
        "views/sale_order_line_hide.xml",
    ],
    "application": True,
    "installable": True,
    'post_init_hook': 'post_init_hook',
}

# INAL CLARIFIED SOLUTION (The Right One For Your Case)
# ✔ Keep courier product line CREATED (as before).
# ✔ Let it be part of request.line, sale.order.line, and stock.move_line.
# ✔ Do NOT delete it. Do NOT skip creating it.
# ✔ Simply hide it from the UI using domain filter in the view.
# ✔ DO NOT change your button_validate.
# ✔ DO NOT change your consumption logic.
# ✔ AWB & Barcode will come EXACTLY like before during validation.


#
# Here is a clear, accurate summary of your exact requirements based on everything you explained:
#
# ✅ Your Functional Requirements (Courier Management System)
# 1. User starts by creating a Courier Request
#
# The request contains a destination ZIP code.
#
# Based on this ZIP code, the system automatically fetches a list of Transit Hubs (Contacts) from your ZIP Code Master.
#
# These contacts already have a boolean is_transit_hub but no custom transit hub model must be used (you removed it).
#
# ✅ 2. Sale Order Creation & Delivery Flow
#
# From the courier request, a Sale Order is created.
#
# The Sale Order Line corresponds to the courier request line.
#
# You confirm the Sale Order → Odoo creates a Delivery Order (Picking) from your warehouse.
#
# ✅ 3. The Delivery must NOT directly go to the customer
#
# Instead:
#
# ✔️ It MUST follow the transit route returned from ZIP Master:
#
# Example:
# Destination ZIP → [Hub A, Hub B, Hub C]
#
# Then the product must move:
#
# Warehouse → Hub A
#
# Hub A → Hub B
#
# Hub B → Hub C
#
# Hub C → Customer
#
# ✅ 4. Routing MUST happen automatically when validating each delivery
#
# When the warehouse validates the first delivery, it should auto-create the next hop to Hub A.
#
# When Hub A validates its hop, it should auto-create the hop to Hub B.
#
# When Hub B validates, auto-create next hop to Hub C.
#
# When Hub C validates, auto-create final hop to Customer.
#
# ⚠️ This is called staged hop creation.
# Only the next hop is created after the previous hop is validated.
#
# ✅ 5. No changes allowed to your ZIP Master or Transit Hub Master
#
# Your ZIP Master already links ZIP → Partner Contacts (Transit Hubs).
#
# You only want to use that.
#
# Do NOT modify ZIP Master, Transit Hub Master, or their structures.
#
# ✅ 6. Contacts are your Transit Hubs
#
# Hub records exist as contacts only.
#
# Each contact with is_transit_hub = True should get a stock.location automatically created (if missing), so Odoo can use it in stock moves.
#
# ✅ 7. Odoo Routing Must Happen Automatically
#
# When Odoo creates/validates the outgoing picking:
#
# It should redirect destination → first hub.
#
# Save all remaining hubs + customer as a planned route.
#
# On each validation (button_validate), the system should:
#
# Detect the next hub.
#
# Create the next picking.
#
# Chain pickings until final customer delivery is done.
#
# ✅ 8. Requirements for Tracking
#
# Each hop must be a real stock.picking.
#
# Each picking must:
#
# Link to the courier request.
#
# Link to previous and next hops (prev_hop_picking_id / next_hop_picking_id).
#
# Be visible to users at each respective hub.
#
# 🚀 In One Sentence
#
# Depending on the destination ZIP, your delivery flow must automatically break into multiple transit hops (Contacts as Hubs), where each hop is created only after validating the previous picking, until the product finally reaches the customer.
