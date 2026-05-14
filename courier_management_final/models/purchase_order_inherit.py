# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import api, models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    awb_number = fields.Char("AWB Number", readonly=True)
    barcode_number = fields.Char("Barcode Number", readonly=True)
    sale_order_count = fields.Integer(
        string="Sale Orders",
        compute="_compute_sale_order_info",
        store=False,
    )
    sale_order_ids = fields.Many2many(
        "sale.order",
        string="Linked Sale Orders",
        compute="_compute_sale_order_info",
        store=False,
    )
    has_sale_order = fields.Boolean(
        string="Has Sale Order",
        compute="_compute_sale_order_info",
        store=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        orders = super(PurchaseOrder, self).create(vals_list)
        for order, vals in zip(orders, vals_list):
            awb = vals.get('awb_number') or getattr(order, 'awb_number', False)
            bar = vals.get('barcode_number') or getattr(order, 'barcode_number', False)
            if (awb or bar) and order.order_line:
                lines_to_update = order.order_line.filtered(
                    lambda l: (not l.awb_number and awb) or (not l.barcode_number and bar))
                if lines_to_update:
                    write_vals = {}
                    if awb:
                        write_vals['awb_number'] = awb
                    if bar:
                        write_vals['barcode_number'] = bar
                    if write_vals:
                        lines_to_update.sudo().write(write_vals)
        return orders

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        # propagate header AWB/barcode to lines that lack them (don't overwrite existing line values)
        propagate = set(vals.keys()) if isinstance(vals, dict) else set()
        if propagate & {'awb_number', 'barcode_number'}:
            for order in self:
                if 'awb_number' in propagate and getattr(order, 'awb_number', False):
                    lines = order.order_line.filtered(lambda l: not l.awb_number)
                    if lines:
                        lines.sudo().write({'awb_number': order.awb_number})
                if 'barcode_number' in propagate and getattr(order, 'barcode_number', False):
                    lines = order.order_line.filtered(lambda l: not l.barcode_number)
                    if lines:
                        lines.sudo().write({'barcode_number': order.barcode_number})
        return res

    def action_merge(self):
        """
        Merge selected RFQs:
         - Group RFQs by vendor/currency/destination
         - For each group, choose oldest RFQ as target
         - Move every line from other RFQs into the oldest RFQ (as separate lines)
         - Preserve per-line awb_number / barcode_number:
             * Prefer rfq_line.awb_number and rfq_line.barcode_number (line-level)
             * If line-level value missing, fallback to rfq header (rfq.awb_number)
        """
        rfq_to_merge = self.filtered(lambda r: r.state in ['draft', 'sent'])
        if len(rfq_to_merge) < 2:
            raise UserError(_("Please select at least two purchase orders with state RFQ and RFQ sent to merge."))

        rfqs_grouped = defaultdict(lambda: self.env['purchase.order'])
        for rfq in rfq_to_merge:
            key = self._prepare_grouped_data(rfq)
            rfqs_grouped[key] += rfq

        bunches_of_rfq_to_be_merge = list(rfqs_grouped.values())
        if all(len(rfq_bunch) == 1 for rfq_bunch in bunches_of_rfq_to_be_merge):
            raise UserError(_("In selected purchase order to merge these details must be same\nVendor, currency, destination, dropship address and agreement"))
        bunches_of_rfq_to_be_merge = [rfqs for rfqs in bunches_of_rfq_to_be_merge if len(rfqs) > 1]

        merged_rfq_ids = []

        for rfqs in bunches_of_rfq_to_be_merge:
            if len(rfqs) <= 1:
                continue

            oldest_rfq = min(rfqs, key=lambda r: r.date_order)
            if not oldest_rfq:
                continue

            rfqs_to_move = rfqs - oldest_rfq

            # Move lines from each RFQ to oldest_rfq
            for rfq in rfqs_to_move:
                for rfq_line in rfq.order_line:
                    # Fetch AWB/barcode preference:
                    # 1) prefer the line-level stored value (rfq_line.awb_number)
                    # 2) fallback to rfq header (rfq.awb_number) only if line empty
                    awb_val = rfq_line.awb_number or (getattr(rfq, 'awb_number', False) if rfq else False)
                    barcode_val = rfq_line.barcode_number or (getattr(rfq, 'barcode_number', False) if rfq else False)

                    # Write per-line stored values BEFORE moving the line
                    write_vals = {}
                    if awb_val:
                        write_vals['awb_number'] = awb_val
                    if barcode_val:
                        write_vals['barcode_number'] = barcode_val
                    if write_vals:
                        try:
                            rfq_line.sudo().write(write_vals)
                        except Exception:
                            _logger.exception("Failed to write awb/barcode to line %s (rfq %s)", rfq_line.id, rfq.name)

                    # Move the line to the oldest RFQ
                    try:
                        rfq_line.sudo().write({'order_id': oldest_rfq.id})
                    except Exception:
                        _logger.exception("Failed to move line %s to RFQ %s", rfq_line.id, oldest_rfq.id)

            # Merge origin and partner_ref fields into oldest RFQ
            all_origin = rfqs_to_move.mapped('origin')
            all_vendor_references = rfqs_to_move.mapped('partner_ref')

            oldest_rfq.origin = ', '.join(filter(None, [oldest_rfq.origin, *all_origin]))
            oldest_rfq.partner_ref = ', '.join(filter(None, [oldest_rfq.partner_ref, *all_vendor_references]))

            # Post messages about merge
            rfq_names = rfqs_to_move.mapped('name')
            merged_names = ", ".join(rfq_names)
            oldest_rfq_message = _("RFQ merged with %(oldest_rfq_name)s and %(cancelled_rfq)s", oldest_rfq_name=oldest_rfq.name, cancelled_rfq=merged_names)

            for rfq in rfqs_to_move:
                cancelled_rfq_message = _("RFQ merged with %s", oldest_rfq._get_html_link())
                try:
                    rfq.message_post(body=cancelled_rfq_message)
                except Exception:
                    _logger.exception("Failed to post merge message on RFQ %s", rfq.name)

            try:
                oldest_rfq.message_post(body=oldest_rfq_message)
            except Exception:
                _logger.exception("Failed to post merge message on oldest RFQ %s", oldest_rfq.name)

            # Cancel the merged RFQs (keep behaviour)
            rfqs_to_move.filtered(lambda r: r.state != 'cancel').button_cancel()

            # Hook for alternative logic if implemented in other modules
            try:
                oldest_rfq._merge_alternative_po(rfqs_to_move)
            except Exception:
                _logger.exception("Error in _merge_alternative_po hook for RFQ %s", oldest_rfq.name)

            merged_rfq_ids.append(oldest_rfq.id)

        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'list,kanban,form',
            'res_model': 'purchase.order',
        }
        if len(merged_rfq_ids) == 1:
            action['res_id'] = merged_rfq_ids[0]
            action['view_mode'] = 'form'
        else:
            action['name'] = _("Merged RFQs")
            action['domain'] = [('id', 'in', merged_rfq_ids)]
        return action

    @api.depends("order_line.sale_line_id.order_id", "order_line.product_id", "origin")
    def _compute_sale_order_info(self):
        """
        Robust compute that assigns sale_order_ids, sale_order_count and has_sale_order
        for every record in self (prevents 'Compute method failed to assign' errors).
        """
        SaleOrder = self.env["sale.order"]
        for rec in self:
            # direct mapping: sale_line_id -> order_id
            sale_orders = rec.order_line.mapped("sale_line_id.order_id")
            # try to resolve by origin tokens if none
            if not sale_orders and rec.origin:
                tokens = [t.strip() for t in str(rec.origin).split(",") if t.strip()]
                if tokens:
                    sale_orders = SaleOrder.search([("name", "in", tokens)], limit=50)
            # fallback: match by product presence
            if not sale_orders:
                product_ids = rec.order_line.mapped("product_id").filtered(bool).ids
                if product_ids:
                    sale_orders = SaleOrder.search([("order_line.product_id", "in", product_ids)], limit=50)

            # Always assign values for every record
            rec.sale_order_ids = sale_orders
            rec.sale_order_count = len(sale_orders)
            rec.has_sale_order = bool(sale_orders)

    def action_view_sale_orders(self):
        self.ensure_one()
        sale_orders = self.sale_order_ids

        if not sale_orders:
            return {
                "type": "ir.actions.act_window_close",
                "toast_message": "No related Sale Orders found.",
            }

        # Load action record safely
        action = (
                self.env.ref("sale.action_quotations_with_onboarding", False)
                or self.env.ref("sale.action_orders", False)
        )

        if action:
            action = action.read()[0]
        else:
            # fallback action dict
            action = {
                "type": "ir.actions.act_window",
                "name": "Sale Orders",
                "res_model": "sale.order",
            }

        # ALWAYS open form view
        action.update({
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "views": [(False, "form")],
        })

        # If only one SO → open it
        if len(sale_orders) == 1:
            action["res_id"] = sale_orders.id
        else:
            # If multiple SO → open the *first*, but keep others available with Next/Previous
            action["res_id"] = sale_orders[0].id

        return action


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # make sure per-line stored fields exist and are stored
    awb_number = fields.Char(string="AWB", store=True)
    barcode_number = fields.Char(string="Barcode", store=True)
























# from odoo import models, fields
# import logging
# from collections import defaultdict   # <-- FIX: ensure defaultdict is defined
# from collections import OrderedDict  # (not required but harmless if used later)
# from odoo.exceptions import UserError
# _logger = logging.getLogger(__name__)
#
#
# class PurchaseOrder(models.Model):
#     _inherit = "purchase.order"
#
    # awb_number = fields.Char("AWB Number", readonly=True)
    # barcode_number = fields.Char("Barcode Number", readonly=True)

#
#
#
# class PurchaseOrderLine(models.Model):
#     _inherit = "purchase.order.line"
#
#     # show parent's AWB on the line so the list view can display it
#     awb_number = fields.Char(
#         string="AWB",
#         related="order_id.awb_number",
#         readonly=True,
#         store=False,   # set True if you want to search/filter by AWB
#     )
#
#     barcode_number = fields.Char(
#         string="Barcode",
#         related="order_id.barcode_number",
#         readonly=True,
#         store=False,
#     )
