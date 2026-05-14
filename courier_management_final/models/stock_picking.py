from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    picking_serviced_by_id = fields.Many2one(
        'codeware.courier.company',
        related='sale_id.serviced_by_id',
        store=True,
        string="Serviced By"
    )
