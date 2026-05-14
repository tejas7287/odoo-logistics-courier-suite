# transit_hub.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TransitHub(models.Model):
    _name = 'codeware.transithub'
    _description = 'Transit Hub'
    # Make pincode the record identity so imports can match by pincode easily
    _rec_name = 'pincode'

    name = fields.Char('Hub Name', required=True)
    hub_code = fields.Char('Hub Code', index=True)
    sequence = fields.Integer('Sequence', default=10, help='Lower comes earlier in route')
    location = fields.Char('Location')
    stock_location_id = fields.Many2one('stock.location', 'Stock Location')
    pincode = fields.Char(string='PIN code', required=True)

    _sql_constraints = [
        ('pincode_uniq', 'unique(pincode)', 'PIN code must be unique for each Transit Hub!'),
    ]

    def name_get(self):
        """Friendly display: show 'PIN - Hub Name' in relations"""
        res = []
        for rec in self:
            display = rec.pincode or rec.hub_code or rec.name or ''
            if rec.pincode and rec.name:
                display = u"%s - %s" % (rec.pincode, rec.name)
            res.append((rec.id, display))
        return res






























# from tokenize import String
#
# from odoo import models, fields, api, _
#
# class TransitHub(models.Model):
#     _name = 'codeware.transithub'
#     _description = 'Transit Hub'
#     _rec_name = 'pincode'
#
#
#     name = fields.Char('Hub Name', required=True)
#     hub_code = fields.Char('Hub Code')
#     sequence = fields.Integer('Sequence', default=10, help='Lower comes earlier in route')
#     location = fields.Char('Location')
#     stock_location_id = fields.Many2one('stock.location', 'Stock Location')
#
#     pincode = fields.Char(string='PIN code')
#






















# from tokenize import String
#
# from odoo import models, fields, api, _
#
# class TransitHub(models.Model):
#     _name = 'codeware.transithub'
#     _description = 'Transit Hub'
#
#     name = fields.Char('Hub Name', required=True)
#     hub_code = fields.Char('Hub Code')
#     sequence = fields.Integer('Sequence', default=10, help='Lower comes earlier in route')
#     location = fields.Char('Location')
#     stock_location_id = fields.Many2one('stock.location', 'Stock Location')
#
#     pincode = fields.Integer(string='PIN code')