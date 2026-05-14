from odoo import models, fields,api
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    request_id = fields.Many2one('codeware.request')
    x_barcode = fields.Char()
    delivery_hub_id = fields.Many2one('codeware.transithub')
    fincode_id = fields.Many2one('codeware.fincode')
    awb_number = fields.Char("AWB Number")
    barcode_number = fields.Char("Barcode Number")
    # Ensure your fields are defined
    hide_ecommerce_info = fields.Boolean(
        compute="_compute_hide_ecommerce_info",
        store=False  # Dynamic calculation for real-time UI response
    )

    @api.depends('request_id', 'order_line.product_id', 'order_line.product_id.qty_available')
    def _compute_hide_ecommerce_info(self):
        for rec in self:
            # Condition 1: Hide if request_id is present
            if rec.request_id:
                rec.hide_ecommerce_info = True
                continue

            # Default: Show the group (not hidden)
            res = False

            for line in rec.order_line:
                if not line.product_id:
                    continue

                is_dropship = line.product_id.product_tmpl_id.enable_dropship
                qty = line.product_id.qty_available

                # Condition 2: ONLY hide if it is a dropship product AND stock is 0 or less
                if is_dropship and qty <= 0:
                    res = True
                    break  # Stop and hide the group immediately

            rec.hide_ecommerce_info = res


from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    request_line_id = fields.Many2one('codeware.request.line')

    is_courier_hidden = fields.Boolean(string="Hidden Courier Line", compute="_compute_is_courier_hidden", store=True)

    def create(self, vals):
        line = super().create(vals)
        if line.request_line_id:
            super(SaleOrderLine, line).write({
                'price_unit': line.request_line_id.price_subtotal
            })
        return line

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            if line.request_line_id:
                super(SaleOrderLine, line).write({
                    'price_unit': line.request_line_id.price_subtotal
                })
        return res

    @api.depends('product_id')
    def _compute_is_courier_hidden(self):
        for line in self:
            courier_company = self.env['codeware.courier.company'].search([
                ('courier_product_id', '=', line.product_id.id)
            ], limit=1)

            # rule:
            # internal = True  → visible (False)
            # internal = False → hide    (True)
            line.is_courier_hidden = bool(courier_company and not courier_company.internal)




#
# # from odoo import models, fields
# #
# # class SaleOrder(models.Model):
# #     _inherit = 'sale.order'
# #
# #     request_id = fields.Many2one('codeware.request')
# #     x_barcode = fields.Char()
# #     delivery_hub_id = fields.Many2one('codeware.transithub')
# #     fincode_id = fields.Many2one('codeware.fincode')
# #
# #
# # class SaleOrderLine(models.Model):
# #     _inherit = 'sale.order.line'
# #
# #     request_line_id = fields.Many2one('codeware.request.line')
# #
# #     request_subtotal = fields.Float(
# #         string="Request Subtotal",
# #         related="request_line_id.price_subtotal",
# #         store=True,
# #         readonly=True,
# #     )
# #
# #     # Override unit_price compute to use request_subtotal
# #     def _compute_price_unit(self):
# #         super()._compute_price_unit()
# #         for line in self:
# #             if line.request_line_id:
# #                 line.price_unit = line.request_line_id.price_subtotal