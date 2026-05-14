from odoo import models, fields, api


# ---------------------------------------------------------
# Partner Extension
# ---------------------------------------------------------
class ResPartner(models.Model):
    _inherit = 'res.partner'

    vendor_portal = fields.Boolean(
        string='Vendor Portal',
        help='Enable this contact to access the vendor portal.'
    )


# ---------------------------------------------------------
# Stock Picking Extension
# ---------------------------------------------------------
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ---------------------------
    # Vendor Dispatch Fields
    # ---------------------------
    vendor_dispatch_reference = fields.Char(string="Vendor Dispatch Reference")
    vendor_dispatch_date = fields.Date(string="Dispatch Date")
    vendor_dispatch_location_id = fields.Many2one(
        'stock.location',
        string='Dispatch Location'
    )
    # vendor_dispatch_location = fields.Char(
    #     string="Dispatch Location"
    # )
    vendor_expected_delivery_date = fields.Date(
        string='Expected Delivery Date'
    )


    vendor_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Assigned Carrier'
    )


    vendor_carrier_name = fields.Char(string="Carrier Name")
    vendor_tracking_number = fields.Char(string="Tracking Number")
    vendor_notes = fields.Text(string="Vendor Notes")
    vendor_invoice_number = fields.Char(string="Vendor Invoice Number")

    vendor_payment_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('done', 'Done'),
    ], string="Payment Status", default='pending')

    vendor_delivery_status = fields.Selection([
        ('pending', 'Pending Dispatch'),
        ('transit', 'In Transit'),
        ('delivered', 'Delivered'),
    ], string="Delivery Status", default='pending')

    vendor_purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        compute='_compute_vendor_purchase_order',
        store=True
    )

    vendor_sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        compute='_compute_vendor_sale_order',
        store=True
    )

    @api.depends('move_ids.sale_line_id.order_id')
    def _compute_vendor_sale_order(self):
        for picking in self:
            so = picking.move_ids.mapped('sale_line_id.order_id')
            picking.vendor_sale_order_id = so[:1] if so else False

    @api.depends('move_ids.purchase_line_id.order_id')
    def _compute_vendor_purchase_order(self):
        for picking in self:
            po = picking.move_ids.mapped('purchase_line_id.order_id')
            picking.vendor_purchase_order_id = po[:1] if po else False

    # ---------------------------------------------------------
    # Vendor Secure Update + Email Trigger
    # ---------------------------------------------------------
    # def _update_from_vendor_submission(self, vals):
    #     """
    #     Secure vendor write.
    #     Email is sent EVERY TIME vendor clicks submit.
    #     """
    #
    #     allowed = [
    #         'vendor_dispatch_reference',
    #         'vendor_dispatch_date',
    #         'vendor_dispatch_location_id',
    #         'vendor_expected_delivery_date',
    #         'vendor_carrier_id',
    #         'vendor_carrier_name',
    #         'vendor_tracking_number',
    #         'vendor_notes',
    #         'vendor_invoice_number',
    #         'vendor_payment_status',
    #         'vendor_delivery_status',
    #     ]
    #
    #     # Filter allowed values
    #     clean_vals = {k: v for k, v in vals.items() if k in allowed}
    #
    #     # Validate selection fields BEFORE write
    #     for sel in ['vendor_delivery_status', 'vendor_payment_status']:
    #         if sel in clean_vals:
    #             field = self._fields.get(sel)
    #             if field and field.selection:
    #                 allowed_keys = [k for k, _ in field.selection]
    #                 if clean_vals[sel] not in allowed_keys:
    #                     clean_vals.pop(sel)
    #
    #     if not clean_vals:
    #         return
    #
    #     # Single write
    #     self.sudo().write(clean_vals)
    #
    #     # -------------------------------------------------
    #     # EMAIL: SEND ON EVERY SUBMIT (NO CONDITIONS)
    #     # -------------------------------------------------
    #     template = self.env.ref(
    #         'vendor_dispatch_portal_v2.email_vendor_dispatch_confirmed',
    #         raise_if_not_found=False
    #     )
    #     if template:
    #         template.send_mail(self.id, force_send=True)

    def _update_from_vendor_submission(self, vals):
        """
        Secure vendor write.
        Email is sent EVERY TIME vendor clicks submit.
        Email is FORCED to CUSTOMER email.
        """

        allowed = [
            'vendor_dispatch_reference',
            'vendor_dispatch_date',
            'vendor_dispatch_location_id',
            'vendor_expected_delivery_date',
            'vendor_carrier_id',
            'vendor_carrier_name',
            'vendor_tracking_number',
            'vendor_notes',
            'vendor_invoice_number',
            'vendor_payment_status',
            'vendor_delivery_status',
        ]

        # -----------------------------------
        # 1️⃣ FILTER ALLOWED VALUES
        # -----------------------------------
        clean_vals = {k: v for k, v in vals.items() if k in allowed}

        # -----------------------------------
        # 2️⃣ VALIDATE SELECTION FIELDS
        # -----------------------------------
        for sel in ['vendor_delivery_status', 'vendor_payment_status']:
            if sel in clean_vals:
                field = self._fields.get(sel)
                allowed_keys = [k for k, _ in field.selection]
                if clean_vals[sel] not in allowed_keys:
                    clean_vals.pop(sel)

        if not clean_vals:
            return

        # -----------------------------------
        # 3️⃣ WRITE VALUES
        # -----------------------------------
        self.sudo().write(clean_vals)

        # -----------------------------------
        # 4️⃣ SEND EMAIL PER PICKING
        # -----------------------------------
        template = self.env.ref(
            'vendor_dispatch_portal_v2.email_vendor_dispatch_confirmed',
            raise_if_not_found=False
        )

        if not template:
            return

        for picking in self:
            # ✅ USE YOUR COMPUTED FIELD
            sale = picking.vendor_sale_order_id
            if not sale:
                continue

            # SAME LOGIC AS PORTAL PAGE
            customer = sale.partner_shipping_id or sale.partner_id
            if not customer or not customer.email:
                continue

            template.sudo().send_mail(
                picking.id,
                force_send=True,
                email_values={
                    'email_to': customer.email,  # ✅ CUSTOMER EMAIL
                    'partner_ids': [],  # 🚫 REMOVE VENDOR
                }
            )

# from odoo import models, fields,api
#
# class ResPartner(models.Model):
#     _inherit = 'res.partner'
#
#     vendor_portal = fields.Boolean(
#         string='Vendor Portal',
#         help='Enable this contact to access the vendor portal.'
#     )
#
#
# class StockPicking(models.Model):
#     _inherit = 'stock.picking'
#
#     vendor_dispatch_reference = fields.Char(string="Vendor Dispatch Reference")
#     vendor_dispatch_date = fields.Datetime(string="Dispatch Date")
#     vendor_carrier_name = fields.Char(string="Carrier Name")
#     vendor_tracking_number = fields.Char(string="Tracking Number")
#     vendor_notes = fields.Text(string="Vendor Notes")
#     vendor_invoice_number = fields.Char(string="Vendor Invoice Number")
#
#     vendor_payment_status = fields.Selection([
#         ('draft', 'Draft'),
#         ('pending', 'Pending'),
#         ('done', 'Done'),
#     ], string="Payment Status", default='pending')
#
#     vendor_delivery_status = fields.Selection([
#         ('pending', 'Pending Dispatch'),
#         ('transit', 'In Transit'),
#         ('delivered', 'Delivered'),
#     ], string="Delivery Status", default='pending')
#
#
#     def _update_from_vendor_submission(self, vals):
#         """Secure vendor write."""
#         allowed = [
#             'vendor_dispatch_reference',
#             'vendor_dispatch_date',
#             'vendor_carrier_name',
#             'vendor_tracking_number',
#             'vendor_notes',
#             'vendor_invoice_number',
#         'vendor_payment_status',
#         'vendor_delivery_status'
#         ]
#         clean_vals = {k: v for k, v in vals.items() if k in allowed}
#         self.sudo().write(clean_vals)
#
#         # Validate selection fields against field definitions to avoid ValueError
#         sel_fields = ['vendor_delivery_status', 'vendor_payment_status']
#         for sel in sel_fields:
#             if sel in clean_vals:
#                 # get allowed keys for this selection
#                 sel_info = self.fields_get([sel]).get(sel, {})
#                 selection = sel_info.get('selection') or []
#                 allowed_keys = [k for k, _ in selection]
#                 if clean_vals[sel] not in allowed_keys:
#                     # if incoming value is not allowed, remove it (or map it if you prefer)
#                     clean_vals.pop(sel, None)
#
#         if clean_vals:
#             self.sudo().write(clean_vals)
#
#
#
#
#
