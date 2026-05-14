# -*- coding: utf-8 -*-
from zeep.xsd import String

from odoo import models, fields, api,_
from odoo.exceptions import UserError
from odoo.orm.decorators import readonly


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    receiver_name = fields.Char("Ship To Name")
    receiver_phone = fields.Char("Ship To  Phone")
    receiver_address = fields.Text("Ship To Address")
    receiver_zip = fields.Char("Ship To ZIP")
    picking_serviced_by_id = fields.Char("Serviced By")
    awb_number = fields.Char(string="AWB Number", index=True, copy=False)
    barcode_number = fields.Char(string="Barcode Number", index=True, copy=False)
    priority_type = fields.Selection(
        [
            ('Standard', 'Standard'),
            ('express', 'Express'),
        ],
        string="Priority Type",readonly=True
    )
    delivery_description = fields.Char(string="Delivery Description")
    handoff_ref=fields.Char(String="Handoff Reference",readonly=True)
    def button_validate(self):
        # keep your existing validation logic intact (do not change)
        res = super().button_validate()

        for pick in self:

            pick_write_vals = {}
            for ml in pick.move_line_ids:
                lot = ml.lot_id
                if not lot:
                    continue

                if not lot.delivery_order:
                    lot.delivery_order = pick.name

                if not getattr(lot, 'picking_id', False):
                    lot.picking_id = pick.id

                if lot.awb_number and not pick.awb_number:
                    pick_write_vals['awb_number'] = lot.awb_number

                if lot.barcode_number and not pick.barcode_number:
                    pick_write_vals['barcode_number'] = lot.barcode_number

            if pick_write_vals:
                pick.sudo().write(pick_write_vals)

            if pick.sale_id:
                sale_vals = {}
                if pick.awb_number:
                    sale_vals['awb_number'] = pick.awb_number
                if pick.barcode_number:
                    sale_vals['barcode_number'] = pick.barcode_number
                if sale_vals:
                    pick.sale_id.sudo().write(sale_vals)

            if pick.sale_id:
                po = self.env['purchase.order'].search([('origin', '=', pick.sale_id.name)], limit=1)
                if po:
                    po_vals = {}
                    if pick.awb_number:
                        po_vals['awb_number'] = pick.awb_number
                    if pick.barcode_number:
                        po_vals['barcode_number'] = pick.barcode_number
                    if po_vals:
                        po.sudo().write(po_vals)

        return res



class StockMove(models.Model):
    _inherit = 'stock.move'

    is_courier_hidden = fields.Boolean(store=True, compute="_compute_is_courier_hidden")

    @api.depends('product_id', 'sale_line_id.is_courier_hidden')
    def _compute_is_courier_hidden(self):
        for move in self:
            if move.sale_line_id and move.sale_line_id.is_courier_hidden:
                move.is_courier_hidden = True
                continue

            courier_company = self.env['codeware.courier.company'].search([
                ('courier_product_id', '=', move.product_id.id)
            ], limit=1)

            move.is_courier_hidden = bool(courier_company and not courier_company.internal)