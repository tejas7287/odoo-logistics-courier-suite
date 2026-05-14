# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    codeware_request_id = fields.Many2one('codeware.request', string='Codeware Request', index=True, ondelete='set null')
