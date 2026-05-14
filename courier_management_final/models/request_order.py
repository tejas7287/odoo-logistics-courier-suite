# -*- coding: utf-8 -*-
from odoo import models, fields


class CodewareRequestOrder(models.Model):
    _name = 'codeware.request.order'
    _description = 'Internal Request Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Order Reference', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('codeware.request.order') or 'RORD')

    request_id = fields.Many2one('codeware.request', 'Request', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', 'Customer', related='request_id.partner_id', store=True)
    source_hub_id = fields.Many2one('codeware.transithub', 'Source Hub', related='request_id.source_hub_id', store=True)
    dest_zip = fields.Char('Destination ZIP', related='request_id.dest_zip', store=True)
    city = fields.Char('City', related='request_id.city', store=True)
    state_name = fields.Char('State', related='request_id.state_name', store=True)
    total_amount = fields.Float('Total Amount', related='request_id.amount_total', store=True)

    sender_name = fields.Char(string='Sender Name')
    sender_address = fields.Text(string='Sender Address')
    customer_name = fields.Char(string='Customer Name')
    customer_address = fields.Text(string='Customer Address')

    # Only one stage for Request Order: confirmed and read-only
    state = fields.Selection([('confirmed', 'Confirmed')], string='State', default='confirmed', readonly=True)

    # Tracking + Barcode fields (added)
    tracking_number = fields.Char(string="Tracking Number", readonly=True)
    barcode_image = fields.Binary(string="Barcode", readonly=True)

    def action_print_pdf(self):
        """Generate PDF report for this request order (opens in new tab)."""
        self.ensure_one()
        report_name = 'courier_management_final.report_request_order'
        url = '/report/pdf/%s/%d?download=true' % (report_name, self.id)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }






















# # models/request_order.py
# from odoo import models, fields
#
#
# class CodewareRequestOrder(models.Model):
#     _name = 'codeware.request.order'
#     _description = 'Internal Request Order'
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#
#     name = fields.Char('Order Reference', required=True, copy=False,
#                        default=lambda self: self.env['ir.sequence'].next_by_code('codeware.request.order') or 'RORD')
#
#     request_id = fields.Many2one('codeware.request', 'Request', required=True, ondelete='cascade')
#     partner_id = fields.Many2one('res.partner', 'Customer', related='request_id.partner_id', store=True)
#     source_hub_id = fields.Many2one('codeware.transithub', 'Source Hub', related='request_id.source_hub_id', store=True)
#     dest_zip = fields.Char('Destination ZIP', related='request_id.dest_zip', store=True)
#     city = fields.Char('City', related='request_id.city', store=True)
#     state_name = fields.Char('State', related='request_id.state_name', store=True)
#     total_amount = fields.Float('Total Amount', related='request_id.amount_total', store=True)
#
#     sender_name = fields.Char(string='Sender Name')
#     sender_address = fields.Text(string='Sender Address')
#     customer_name = fields.Char(string='Customer Name')
#     customer_address = fields.Text(string='Customer Address')
#
#     # Only one stage for Request Order: confirmed and read-only
#     state = fields.Selection([('confirmed', 'Confirmed')], string='State', default='confirmed', readonly=True)
#
#     def action_print_pdf(self):
#         """Generate PDF report for this request order (opens in new tab)."""
#         self.ensure_one()
#         report_name = 'codeware_management.report_request_order'
#         url = '/report/pdf/%s/%d?download=true' % (report_name, self.id)
#         return {
#             'type': 'ir.actions.act_url',
#             'url': url,
#             'target': 'new',
#         }
