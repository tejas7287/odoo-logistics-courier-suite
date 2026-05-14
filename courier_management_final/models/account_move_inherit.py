# -*- coding: utf-8 -*-
from odoo import models, _, api, fields
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ---- new UI helpers ----
    payment_count = fields.Integer(string='Payments', compute='_compute_linked_payments', store=False)
    primary_payment_id = fields.Many2one('account.payment', string='Primary Payment', compute='_compute_linked_payments', store=False)

    def _get_request_from_invoice(self, inv):
        """
        Robust request lookup for an invoice:
         1) invoice.sale_id.request_id
         2) invoice.request_ids (m2m)
         3) invoice.origin / invoice.invoice_origin -> match codeware.request.name (exact then ilike)
         4) invoice.origin / invoice.invoice_origin -> try to find sale.order by name/origin and use its request_id
        """
        # 1) via sale -> request
        try:
            if getattr(inv, 'sale_id', False) and getattr(inv.sale_id, 'request_id', False):
                return inv.sale_id.request_id
        except Exception:
            _logger.debug("Codeware: safe-check sale_id/request_id failed for invoice %s", getattr(inv, 'id', False))

        # 2) via direct many2many link
        try:
            if hasattr(inv, 'request_ids') and inv.request_ids:
                return inv.request_ids[0]
        except Exception:
            pass

        # get origin text if any
        origin = False
        try:
            origin = (getattr(inv, 'origin', False) or getattr(inv, 'invoice_origin', False)) or False
        except Exception:
            origin = False

        if origin:
            # 3a) exact match on request name
            try:
                req = self.env['codeware.request'].search([('name', '=', origin)], limit=1)
                if req:
                    _logger.info("Codeware: _get_request_from_invoice found request by exact name match origin='%s' -> %s", origin, req.id)
                    return req
            except Exception:
                pass
            # 3b) ilike match on request name
            try:
                req = self.env['codeware.request'].search([('name', 'ilike', origin)], limit=1)
                if req:
                    _logger.info("Codeware: _get_request_from_invoice found request by ilike origin='%s' -> %s", origin, req.id)
                    return req
            except Exception:
                pass

            # 4) Try to find related sale.order where origin or name matches invoice origin, then use sale.request_id
            try:
                Sale = self.env['sale.order']
                # exact on sale.name or sale.origin
                sale = Sale.search([('name', '=', origin)], limit=1)
                if not sale:
                    sale = Sale.search([('origin', '=', origin)], limit=1)
                # fallback ilike
                if not sale:
                    sale = Sale.search(['|', ('name', 'ilike', origin), ('origin', 'ilike', origin)], limit=1)
                if sale and getattr(sale, 'request_id', False):
                    _logger.info("Codeware: _get_request_from_invoice found sale %s by origin='%s' -> request %s", sale.id, origin, sale.request_id.id)
                    return sale.request_id
            except Exception:
                _logger.exception("Codeware: error while searching sale by origin for invoice %s origin=%s", getattr(inv, 'id', False), origin)

        # last resort: nothing found
        return False

    def action_post(self):
        """
        Keep base posting behaviour. Do NOT auto-reconcile payments here (user requested no auto-reconcile).
        """
        # call original posting
        res = super(AccountMove, self).action_post()
        # We deliberately DO NOT attempt to auto-reconcile or post payments here.
        return res

    def _compute_linked_payments(self):
        """Compute payment_count and primary_payment_id for UI display."""
        for inv in self:
            inv.payment_count = 0
            inv.primary_payment_id = False
            # find request (use your robust helper)
            req = self._get_request_from_invoice(inv)
            Payment = self.env['account.payment']
            payments = self.env['account.payment'].browse()

            if req:
                # 1) payments explicitly linked by codeware_request_id
                payments = Payment.search([('codeware_request_id', '=', req.id), ('partner_id', '=', inv.partner_id.id)], limit=0)
            if not payments:
                # 2) fallback: search by stable communication REQ/<request.name> if req exists
                if req:
                    comm = 'REQ/%s' % (getattr(req, 'name', ''))
                    payments = Payment.search([('communication', '=', comm), ('partner_id', '=', inv.partner_id.id)], limit=0)
            if not payments:
                # 3) fallback: payments that reference this invoice directly
                try:
                    payments = Payment.search([('invoice_ids', 'in', inv.id), ('partner_id', '=', inv.partner_id.id)], limit=0)
                except Exception:
                    payments = self.env['account.payment'].browse()
            inv.payment_count = len(payments)
            if payments:
                inv.primary_payment_id = payments[0]

    def action_register_payment(self):
        """
        Override invoice 'Pay' action so that:
        - If invoice is linked to a Codeware request and a payment exists created from that request,
          open that payment form (so the smart button appears) instead of showing register-payment popup.
        - Otherwise fallback to standard behavior.
        IMPORTANT: this does NOT post or reconcile automatically. It only opens the payment form for inspection.
        """
        self.ensure_one()
        _logger.info("Codeware: action_register_payment called for invoice %s (partner=%s)", self.id, self.partner_id.id)

        # find request robustly
        req = self._get_request_from_invoice(self)
        _logger.info("Codeware: request lookup for invoice %s -> %s", self.id, getattr(req, 'id', False))

        if not req:
            _logger.info("Codeware: no related codeware request found, fallback to standard payment popup")
            return super(AccountMove, self).action_register_payment()

        # 1) Preferred: find payment with codeware_request_id on account.payment (explicit)
        Payment = self.env['account.payment']
        payment = Payment.search([
            ('codeware_request_id', '=', req.id),
            ('partner_id', '=', self.partner_id.id),
            ('company_id', '=', self.company_id.id),
        ], order='id asc', limit=1)

        # 2) Fallback: find via stable communication 'REQ/<request.name>'
        if not payment:
            comm = 'REQ/%s' % (getattr(req, 'name', ''))
            try:
                payment = Payment.search([('communication', '=', comm), ('partner_id', '=', self.partner_id.id)], limit=1)
            except Exception:
                payment = False

        # 3) Another fallback: payments that include this invoice in invoice_ids
        if not payment:
            try:
                payment = Payment.search([('invoice_ids', 'in', self.id), ('partner_id', '=', self.partner_id.id)], limit=1)
            except Exception:
                payment = False

        if not payment:
            _logger.info("Codeware: no payment found for request %s (partner=%s) via any method", req.id, self.partner_id.id)
            return super(AccountMove, self).action_register_payment()

        _logger.info("Codeware: found payment %s for request %s (state=%s). Opening payment form (no auto-post/reconcile).",
                     payment.id, req.id, payment.state)

        # Open payment form for user inspection (no auto-post/reconciliation)
        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
        }

    def action_open_payments(self):
        """
        Open payments associated with this invoice:
        1) Payments linked to the related codeware.request
        2) Payments using stable reference REQ/<request.name> (via payment_reference)
        3) Payments directly linked to this invoice
        """
        self.ensure_one()
        Payment = self.env['account.payment']
        payments = Payment.browse()

        # --- Find Codeware Request ---
        req = self._get_request_from_invoice(self)

        if req:
            # 1) Payments explicitly linked by M2O field
            payments = Payment.search([
                ('codeware_request_id', '=', req.id),
                ('partner_id', '=', self.partner_id.id)
            ])

            # 2) Fallback using payment_reference (Odoo 16–19 standard field)
            if not payments:
                ref = 'REQ/%s' % (getattr(req, 'name', ''))
                payments = Payment.search([
                    ('payment_reference', '=', ref),
                    ('partner_id', '=', self.partner_id.id)
                ])

        # 3) Fallback: invoice-linked payments
        if not payments:
            payments = Payment.search([
                ('invoice_ids', 'in', self.id),
                ('partner_id', '=', self.partner_id.id)
            ])

        # --- Return UI Actions ---
        if not payments:
            return {'type': 'ir.actions.act_window_close'}

        if len(payments) == 1:
            return {
                'name': _('Payment'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'res_id': payments.id,
                'view_mode': 'form',
                'target': 'current',
            }

        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'domain': [('id', 'in', payments.ids)],
            'view_mode': 'tree,form',
            'target': 'current',
        }
