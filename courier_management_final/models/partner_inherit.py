# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_transit_hub = fields.Boolean(
        string="Is Transit Hub",
        help="Check if this partner is a transit hub. Used by FinCode hub selection.",
        default=False,
        index=True,
        domain="[('is_transit_hub','=', True)]",
    )
    portal_location_id = fields.Many2one(
        'stock.location',
        string="Assigned Delivery Location",
        help="Portal user will see deliveries whose destination is this location"
    )
    vendor_ack_count = fields.Integer(
        string="Acknowledged Deliveries Count",
        default=0
    )
