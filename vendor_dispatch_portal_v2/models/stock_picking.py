from odoo import models,fields,api
from datetime import timedelta


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
        compute="_compute_customer_tracking",
        string="Sale Order"
    )

    customer_ordered_on = fields.Datetime(
        compute="_compute_customer_tracking",
        string="Ordered On"
    )

    customer_expected_on = fields.Date(
        compute="_compute_customer_tracking",
        string="Expected Delivery"
    )
    delivery_acknowledged = fields.Boolean(
        string="Delivery Acknowledged",
        default=False,
        copy=False
    )
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

    # def _compute_customer_tracking(self):
    #     for picking in self:
    #         sale = picking.sale_id
    #
    #         # -------------------------
    #         # SALE ORDER REF
    #         # -------------------------
    #         picking.customer_sale_order = (
    #             sale.name if sale else picking.origin or 'N/A'
    #         )
    #
    #         # -------------------------
    #         # ORDERED DATE
    #         # -------------------------
    #         if sale and sale.date_order:
    #             picking.customer_ordered_on = sale.date_order
    #             picking.customer_expected_on = (
    #                     sale.date_order.date() + timedelta(days=12)
    #             )
    #         else:
    #             picking.customer_ordered_on = False
    #             picking.customer_expected_on = False
    #
    #         # =========================
    #         # DEFAULT → ORDERED
    #         # =========================
    #         picking.customer_tracking_status = 'Ordered'
    #         picking.customer_last_location = 'Order Confirmed'
    #
    #         # =========================
    #         # ONLY AFTER VALIDATION
    #         # =========================
    #         if picking.state == 'done':
    #             picking.customer_tracking_status = 'In Transit'
    #             picking.customer_last_location = (
    #                 picking.location_id.complete_name
    #                 if picking.location_id else 'In Transit'
    #             )

    def _compute_customer_tracking(self):
        for picking in self:
            sale = picking.sale_id

            # --------------------------------------------------
            # SALE ORDER REFERENCE
            # --------------------------------------------------
            picking.customer_sale_order = (
                sale.name if sale else picking.origin or 'N/A'
            )

            # --------------------------------------------------
            # ORDERED DATE + EXPECTED DELIVERY
            # --------------------------------------------------
            if sale and sale.date_order:
                picking.customer_ordered_on = sale.date_order
                picking.customer_expected_on = (
                        sale.date_order.date() + timedelta(days=12)
                )
            else:
                picking.customer_ordered_on = False
                picking.customer_expected_on = False

            # --------------------------------------------------
            # DEFAULT → ORDERED
            # --------------------------------------------------
            picking.customer_tracking_status = 'Ordered'
            picking.customer_last_location = 'Order Confirmed'

            # --------------------------------------------------
            # FIND ALL RELATED PICKINGS (ADMIN + PORTAL CREATED)
            # --------------------------------------------------
            related_pickings = self.env['stock.picking'].sudo().search([
                '|',
                ('id', '=', picking.id),
                ('origin', '=', picking.name),
            ])

            # --------------------------------------------------
            # FINAL DELIVERY CHECK
            # --------------------------------------------------
            delivered_pickings = related_pickings.filtered(
                lambda p:
                p.state == 'done'
                and p.location_dest_id
                and p.location_dest_id.usage == 'customer'
            )

            if delivered_pickings:
                picking.customer_tracking_status = 'Delivered'
                picking.customer_last_location = 'Delivered to Customer'
                continue

            # --------------------------------------------------
            # IN TRANSIT CHECK
            # --------------------------------------------------
            in_transit_pickings = related_pickings.filtered(
                lambda p: p.state == 'done'
            )

            if in_transit_pickings:
                last = in_transit_pickings.sorted('date_done')[-1]
                picking.customer_tracking_status = 'In Transit'
                picking.customer_last_location = (
                    last.location_dest_id.complete_name
                    if last.location_dest_id else 'In Transit'
                )

            # 🚫 NO DELIVERED LOGIC NOW (AS YOU REQUESTED)

    def write(self, vals):
        res = super().write(vals)

        if vals.get('portal_acknowledged') is True:
            self.filtered(
                lambda p: not p.delivery_acknowledged
            ).write({
                'delivery_acknowledged': True
            })

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



















