from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    awb_number = fields.Char(string="AWB Number", index=True)
    delivery_order = fields.Char(string="Delivery Order", index=True)
    barcode_number = fields.Char(string="Barcode Number", index=True, help="Barcode / scanning number for this lot/serial")
    picking_id = fields.Many2one(
        'stock.picking',
        string="Linked Picking",
        readonly=True
    )
