from odoo import models,fields,api


class StockPicking(models.Model):
    _inherit = "stock.picking"
    vendor_portal_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('done', 'Done'),
        ],
        string="Portal Status",
        default='draft',
        copy=False
    )
    portal_acknowledged = fields.Boolean(
        string="Acknowledged in Portal",
        default=False
    )
    customer_tracking_status = fields.Char(
        compute='_compute_customer_tracking',
        string='Customer Tracking Status'
    )

    customer_last_location = fields.Char(
        compute='_compute_customer_tracking',
        string='Last Known Location'
    )

    customer_sale_order = fields.Char(
        compute='_compute_customer_tracking',
        string='Sale Order'
    )


    def _compute_customer_tracking(self):
        for picking in self:
            # -------------------------
            # Sale Order
            # -------------------------
            picking.customer_sale_order = (
                picking.sale_id.name or picking.origin or 'N/A'
            )

            # -------------------------
            # Defaults
            # -------------------------
            picking.customer_tracking_status = 'In Transit'
            picking.customer_last_location = 'Not yet dispatched'

            # -------------------------
            # Latest completed movement
            # -------------------------
            move_line = self.env['stock.move.line'].search(
                [
                    ('picking_id', '=', picking.id),
                    ('state', '=', 'done'),
                ],
                order='date desc',
                limit=1
            )

            if move_line:
                dest_location = move_line.location_dest_id
                picking.customer_last_location = dest_location.complete_name

                # -------------------------
                # Status decision
                # -------------------------
                if dest_location.usage == 'customer':
                    picking.customer_tracking_status = 'Ready to Deliver'
                else:
                    picking.customer_tracking_status = 'In Transit'




















    def button_validate(self):
        skip_backorder = True  # optimistic default

        # --------------------------------------------------
        # PHASE 1: Detect shortages WITHOUT changing anything
        # --------------------------------------------------
        for picking in self:
            if picking.picking_type_code != "outgoing":
                continue

            for move in picking.move_ids:
                product = move.product_id
                template = product.product_tmpl_id

                available_qty = product.with_context(
                    location=move.location_id.id
                ).qty_available

                # Shortage exists
                if available_qty < move.product_uom_qty:
                    # 🚨 Non-dropship product → MUST show wizard
                    if not template.enable_dropship:
                        skip_backorder = False
                        break
            if not skip_backorder:
                break

        # --------------------------------------------------
        # PHASE 2: Apply dropship logic (SAFE now)
        # --------------------------------------------------
        for picking in self:
            if picking.picking_type_code != "outgoing":
                continue

            for move in picking.move_ids:
                template = move.product_id.product_tmpl_id

                if not template.enable_dropship:
                    continue

                available_qty = move.product_id.with_context(
                    location=move.location_id.id
                ).qty_available

                deliver_qty = min(move.product_uom_qty, available_qty)

                # Clamp ONLY dropship products
                move.product_uom_qty = deliver_qty

                for line in move.move_line_ids:
                    line.qty_done = deliver_qty

        # --------------------------------------------------
        # PHASE 3: Validate conditionally
        # --------------------------------------------------
        if skip_backorder:
            res = super(
                StockPicking,
                self.with_context(skip_backorder=True)
            ).button_validate()
        else:
            # 🔔 Wizard WILL appear
            res = super().button_validate()

        # --------------------------------------------------
        # PHASE 4: Relaunch dropship procurement
        # --------------------------------------------------
        for picking in self:
            sale = picking.sale_id
            if not sale:
                continue

            for line in sale.order_line:
                template = line.product_id.product_tmpl_id

                if template.enable_dropship and line.qty_delivered < line.product_uom_qty:
                    line._action_launch_stock_rule()

        return res



class StockMove(models.Model):
    _inherit = "stock.move"

    def _compute_is_quantity_done_editable(self):
        super()._compute_is_quantity_done_editable()

        for move in self:
            # Only outgoing deliveries
            if move.picking_type_id.code != 'outgoing':
                continue

            product = move.product_id
            if not product:
                continue

            # 🔒 Lock quantity for dropship-enabled products
            # if product.product_tmpl_id.enable_dropship:
            #     move.is_quantity_done_editable = False



















#
# from odoo import models
#
#
# class StockPicking(models.Model):
#     _inherit = "stock.picking"
#
#     def button_validate(self):
#         res = super().button_validate()
#
#         for picking in self:
#             if picking.picking_type_code != "outgoing":
#                 continue
#
#             sale = picking.sale_id
#             if not sale:
#                 continue
#
#             for line in sale.order_line:
#                 product = line.product_id
#                 template = product.product_tmpl_id
#
#                 if not template.enable_dropship:
#                     continue
#
#                 delivered = line.qty_delivered
#                 ordered = line.product_uom_qty
#
#                 # 🔥 Remaining qty exists
#                 if delivered < ordered:
#                     # Force procurement for remaining qty
#                     line._action_launch_stock_rule()
#
#         return res
#
