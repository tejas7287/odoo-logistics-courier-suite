# -*- coding: utf-8 -*-
"""
Merged codeware_request.py - final fixed (tracking & barcode removed from codeware.request only)
- Safe phone helper _get_partner_phone
- name_search that works when res.partner.mobile is absent
- Transient helper Many2one fields for phone dropdown (store=False)
- All onchange and label_map use safe accessor
- No DB schema changes, no migrations
"""
from email.policy import default

from zeep.xsd import String

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
import logging
import re
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


def _normalize_digits(s):
    if not s:
        return ''
    return re.sub(r'\D', '', s)


def _get_partner_phone(partner):
    """
    Return partner.mobile if present and truthy else partner.phone if present else ''.
    Uses getattr to avoid AttributeError on databases that don't have 'mobile'.
    """
    if not partner:
        return ''
    mobile = getattr(partner, 'mobile', False)
    if mobile:
        return mobile
    phone = getattr(partner, 'phone', False)
    if phone:
        return phone
    return ''


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        """
        Robust phone-aware name_search that works even if res.partner.mobile is missing.

        Behavior:
        - If the query contains digits, treat it as phone lookup:
          1) Try exact normalized-digit match using SQL (only referencing columns that exist).
          2) Prefix-match (starts-with) using ORM ilike on phone and mobile only if present.
          3) Fallback to default name_search (positional call to super).
        - For phone-derived results, return phone-only labels (mobile preferred) so the dropdown shows numbers.
        - If no digits in query, call default name_search.
        """
        args = args or []
        q = (name or '').strip()
        results = []
        seen = set()

        def _append(partners, label_map=None):
            nonlocal results, seen, limit
            for p in partners:
                if p.id in seen:
                    continue
                seen.add(p.id)
                if label_map and p.id in label_map:
                    label = label_map[p.id]
                else:
                    label = p.name_get()[0][1]
                results.append((p.id, label))
                if len(results) >= limit:
                    break

        # whether mobile column exists on this DB
        has_mobile = 'mobile' in self.env['res.partner']._fields

        # If query contains digits => phone-centric search
        if q and any(ch.isdigit() for ch in q):
            norm = ''.join(ch for ch in q if ch.isdigit())

            # 1) Exact normalized match using SQL (guard mobile usage)
            if norm:
                try:
                    cr = self.env.cr
                    if has_mobile:
                        sql = """
                            SELECT id,
                                   COALESCE(NULLIF(mobile, ''), NULLIF(phone, ''), '') as num
                            FROM res_partner
                            WHERE (regexp_replace(COALESCE(mobile, ''), '\\D', '', 'g') = %s)
                               OR (regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') = %s)
                            LIMIT %s
                        """
                        cr.execute(sql, (norm, norm, int(limit)))
                    else:
                        sql = """
                            SELECT id,
                                   COALESCE(NULLIF(phone, ''), '') as num
                            FROM res_partner
                            WHERE (regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') = %s)
                            LIMIT %s
                        """
                        cr.execute(sql, (norm, int(limit)))
                    rows = cr.fetchall()
                    if rows:
                        exact_ids = [r[0] for r in rows]
                        partners_exact = self.browse(exact_ids)
                        label_map = {r[0]: (r[1] or '') for r in rows}
                        _append(partners_exact, label_map=label_map)
                except Exception:
                    _logger.exception("name_search: exact normalized SQL failed.")

            # 2) Prefix-match (ilike) on mobile/phone (use mobile only if exists)
            if len(results) < limit:
                remaining = limit - len(results)
                pattern = norm + '%'
                if has_mobile:
                    partners_prefix = self.search(
                        expression.AND([args, ['|', ('mobile', 'ilike', pattern), ('phone', 'ilike', pattern)]]),
                        limit=remaining
                    )
                else:
                    partners_prefix = self.search(
                        expression.AND([args, [('phone', 'ilike', pattern)]]),
                        limit=remaining
                    )
                # build label map safely using helper
                label_map = {p.id: _get_partner_phone(p) for p in partners_prefix}
                _append(partners_prefix, label_map=label_map)

            # 3) fallback to default name_search (positional call)
            if len(results) < limit:
                name_results = super(ResPartner, self).name_search(name, args, operator, limit)
                for pid, pname in name_results:
                    if pid not in seen:
                        seen.add(pid)
                        results.append((pid, pname))
                        if len(results) >= limit:
                            break

            return results[:limit]

        # Non-digit queries: default behaviour
        return super(ResPartner, self).name_search(name, args, operator, limit)


class CodewareRequest(models.Model):
    _name = 'codeware.request'
    _description = 'Request Form (Quotation-like)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ---- basic fields ----
    name = fields.Char(
        string='Request Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('codeware.request') or 'New'
    )
    partner_id = fields.Many2one('res.partner', string='Customer', required=False)

    source_hub_id = fields.Many2one(
        'codeware.transithub',
        string='Source Hub',
        default=lambda self: self._default_source_hub(),
        readonly=True
    )

    # Keep sender_name but user asked to avoid auto-filling it (still present)
    sender_name = fields.Char(string='Sender Name')
    sender_address = fields.Text(string='Sender Address')

    # Keep DB Char columns (no DB change)
    sender_phone = fields.Char(string='Sender Phone')

    # Transient helper for sender phone — provides dropdown-by-phone (no DB column)
    sender_phone_partner = fields.Many2one(
        'res.partner',
        string='Sender Phone Number',
        store=False,
        help='Helper dropdown: select contact by phone/mobile (typing digits filters).'
    )

    # Receiver fields — keep your existing naming
    receiver_id = fields.Many2one('res.partner', string='Ship To')
    customer_name = fields.Char(string='Reciever Name')
    customer_address = fields.Text(string='Ship To Address')

    receiver_phone = fields.Char(string='Ship To Phone')

    # Transient helper for receiver phone — provides dropdown-by-phone (no DB column)
    receiver_phone_partner = fields.Many2one(
        'res.partner',
        string='Receiver Phone Number',
        store=False,
        help='Helper dropdown for receiver phone.'
    )

    delivery_description = fields.Char(string="Delivery Description")

    # ADDED BY SUMITH PATIL PRIORITY Type
    priority_type = fields.Selection([
        ('Standard', 'Standard'),
        ('express', 'Express'),
    ], string="Priority Type",
        compute="_compute_priority_type_from_lines",
        store=True,
        readonly=False,
        # default='Standard'
    )

    @api.depends('line_ids.priority')
    def _compute_priority_type_from_lines(self):
        for rec in self:
            # If ANY line is express → request is express
            has_express = any(
                line.priority == 'express'
                for line in rec.line_ids
            )

            if has_express:
                rec.priority_type = 'express'
            else:
                # If no express lines → keep empty
                rec.priority_type = 'Standard'

    @api.onchange('line_ids')
    def _onchange_line_ids_priority(self):
        for rec in self:
            has_express = any(
                line.priority == 'express'
                for line in rec.line_ids
            )
            rec.priority_type = 'express' if has_express else "Standard"








    zip_input = fields.Char(
        string='Source ZipCode',
        default='540001',
        readonly=False,
    )
    dest_fincode_id = fields.Many2one('codeware.fincode', string='Destination ZipCode')
    dest_zip = fields.Char(string='Destination ZIP', related='dest_fincode_id.name', readonly=True, store=True)
    city = fields.Char(string='City', readonly=True, store=True)
    state_name = fields.Char(string='State', readonly=True, store=True)
    base_price = fields.Float(string='Base Price', store=True,
                              help="Base price pulled from FinCode (can be overridden)",
                              default=0.0)
    # transit_hub_ids = fields.Many2many('codeware.transithub', string='Transit Hubs', readonly=True, store=True)
    transit_hub_ids = fields.Many2many(
        'res.partner',
        string='Transit Hubs',
        relation='codeware_request_res_partner_rel',  # optional: set relation name
        column1='request_id',
        column2='partner_id',
        domain=[('is_transit_hub', '=', True)],
        help='Transit hub contacts',

    )
    # -------------------------------------------------------------------------
    # PRICING INPUTS (your logic)
    # -------------------------------------------------------------------------
    weight = fields.Float(string="Weight (KG)")
    distance = fields.Float(string="Distance (KM)")


    subtotal = fields.Float(string="Subtotal", compute="_compute_amounts", store=True)

    weight_cost = fields.Float(string="Weight Cost", compute="_compute_amounts", store=True)
    distance_cost = fields.Float(string="Distance Cost", compute="_compute_amounts", store=True)
    priority_cost = fields.Float(string="Priority Cost", compute="_compute_amounts", store=True)

    line_ids = fields.One2many('codeware.request.line', 'request_id', string='Price Lines')
    amount_total = fields.Float(string='Total Amount', compute='_compute_total', store=True)
    is_fully_paid = fields.Boolean(
        string='Is Fully Paid',
        compute='_compute_is_fully_paid',
        store=False,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Quotation Sent'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', tracking=True)

    request_order_id = fields.Many2one('codeware.request.order', string='Request Order', readonly=True, copy=False)
    request_order_count = fields.Integer(string='Request Orders', compute='_compute_request_order_count', store=True)
    tracking_number = fields.Char(
        compute="_compute_tracking_number",
        store=False,
        readonly=True,
    )

    # FINCODE -> REQUEST mapping
    FINCODE_TO_REQUEST_MAP = {
        'name': ('dest_zip', 'simple'),
        'city': ('city', 'simple'),
        'state': ('state_name', 'simple'),
        'base_price': ('base_price', 'simple'),
        'hub_ids': ('transit_hub_ids', 'm2m'),
        'final_transit_hub_id': ('final_transit_hub', 'many2one'),

    }
    serviced_by_id = fields.Many2one(
        'codeware.courier.company',
        string="Serviced By",
        readonly=True
    )

    # Links to sale & invoices (persisted fields)
    sale_id = fields.Many2one('sale.order', string="Sale Order", readonly=True, copy=False)
    invoice_ids = fields.Many2many('account.move', string="Invoices", readonly=True, copy=False)

    # ==== PAYMENT LINKS ====
    payment_ids = fields.Many2many(
        'account.payment',
        string='Payments',
        readonly=True,
        copy=False
    )

    primary_payment_id = fields.Many2one(
        'account.payment',
        string='Primary Payment',
        readonly=True,
        copy=False,
    )

    # ----- UI helper fields (counts) -----
    sale_count = fields.Integer(string='Sales', compute='_compute_link_counts', store=False)
    payment_count = fields.Integer(string='Payments', compute='_compute_link_counts', store=False)
    is_courier_hidden = fields.Boolean(string="Hidden Courier Line", compute="_compute_is_courier_hidden", store=True)
    final_transit_hub = fields.Many2one(
        'res.partner',
        string='Final Transit Hub',
        domain=[('is_transit_hub', '=', True)],
        readonly=True,
        store=True,
    )

    # helper to choose last hub defensively
    def _select_final_hub_from_fincode(self, fin):
        """
        Return a res.partner (single) chosen as 'final' hub from fin.hub_ids.
        Strategy:
          - if hub_ids has 'sequence' field, use sorted('sequence') and pick last
          - else pick last element of the recordset (best-effort)
        """
        if not fin or not getattr(fin, 'hub_ids', False):
            return False
        hubs = fin.hub_ids
        # if hubs empty
        if not hubs:
            return False
        # prefer explicit 'sequence' if available
        if 'sequence' in hubs._fields:
            try:
                ordered = hubs.sorted('sequence')
                return ordered and ordered[-1] or False
            except Exception:
                # fallback below
                pass
        # fallback: pick last partner in recordset
        try:
            return hubs[-1]
        except Exception:
            return hubs[:1]  # at least return something




    @api.depends('line_ids')
    def _compute_is_courier_hidden(self):
        for rec in self:
            rec.is_courier_hidden = False

    # ----------------- computes -----------------
    @api.depends('request_order_id')
    def _compute_request_order_count(self):
        for rec in self:
            rec.request_order_count = 1 if rec.request_order_id else 0

    @api.depends('sale_id', 'payment_ids')
    def _compute_link_counts(self):
        for rec in self:
            rec.sale_count = 1 if rec.sale_id else 0
            rec.payment_count = len(rec.payment_ids or [])

    @api.depends("sale_id")
    def _compute_tracking_number(self):
        for rec in self:
            rec.tracking_number = False

            if not rec.sale_id:
                continue

            # Find picking by sale_id
            pickings = rec.env["stock.picking"].search([
                ("sale_id", "=", rec.sale_id.id)
            ], limit=1)

            if pickings:
                rec.tracking_number = pickings.tracking_number or False

    # ----------------- onchanges -----------------
    @api.onchange('zip_input')
    def _onchange_zip_input(self):
        for rec in self:
            if rec.zip_input:
                fin = self.env['codeware.fincode'].search([('name', '=', rec.zip_input)], limit=1)
                if fin:
                    rec.dest_fincode_id = fin.id
                    rec.city = fin.city
                    rec.state_name = fin.state
                    if not rec.base_price and fin.base_price:
                        rec.base_price = fin.base_price
                    rec.transit_hub_ids = [(6, 0, fin.hub_ids.ids)] if hasattr(fin, 'hub_ids') else [(6, 0, [])]
                else:
                    rec.dest_fincode_id = False
            else:
                rec.dest_fincode_id = False



    @api.onchange('dest_fincode_id')
    def _onchange_dest_fincode_id(self):
        for rec in self:
            if not rec.dest_fincode_id:
                rec.city = False
                rec.state_name = False
                rec.transit_hub_ids = [(6, 0, [])]
                rec.serviced_by_id = False
                rec.final_transit_hub = False
                continue

            fin = rec.dest_fincode_id
            if not rec.base_price and getattr(fin, 'base_price', False):
                rec.base_price = fin.base_price
            rec.city = fin.city or False
            rec.state_name = fin.state or False
            rec.serviced_by_id = fin.serviced_by_id.id if getattr(fin, 'serviced_by_id', False) else False

            # DIRECT copy of partner hubs (works because both sides are res.partner)
            if getattr(fin, 'hub_ids', False):
                rec.transit_hub_ids = [(6, 0, fin.hub_ids.ids)]
            else:
                rec.transit_hub_ids = [(6, 0, [])]

            # NEW: set the final_transit_hub to the last hub in fin.hub_ids (defensively)
            selected_final = self._select_final_hub_from_fincode(fin)
            rec.final_transit_hub = selected_final.id if selected_final else False

    # ----------------- validation helper -----------------
    def _validate_before_send_or_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Please add at least one Price Line before proceeding."))
            if not rec.partner_id:
                raise ValidationError(_("Please select a Customer before proceeding."))
            # if not rec.source_hub_id:
            #     raise ValidationError(_("Please select a Source Hub before proceeding."))
            if not rec.dest_fincode_id:
                raise ValidationError(_("Please select Destination FinCode (ZIP) before proceeding."))
            if not rec.sender_name or not rec.sender_address:
                raise ValidationError(_("Please fill Sender Name and Sender Address before proceeding."))
            if not rec.customer_name or not rec.customer_address:
                raise ValidationError(_("Please fill Customer Name and Customer Address before proceeding."))

    def action_send_quotation(self):
        self._validate_before_send_or_confirm()
        for rec in self:
            rec.state = 'sent'
            try:
                rec.message_post(body=_("Quotation sent."))
            except Exception:
                pass
        return True



    def action_confirm(self):
        """
        Confirm the request without destructive cleanup of "courier-like" lines by name.
        - Do NOT remove lines that only look like courier products by name/code.
        - If a courier mapping exists (rec.serviced_by_id.courier_product_id), ensure exactly
          one hidden request line for THAT exact product exists; but do NOT delete other lines.
        - Create request.order, sale.order and sale lines as before.
        """
        self._validate_before_send_or_confirm()

        for rec in self:
            # 🔴 PAYMENT VALIDATION (BLOCK CONFIRM)
            if not rec.is_fully_paid:
                raise ValidationError(_(
                    "Payment is not completed.\n"
                    "Please register and post the payment before confirming this request."
                ))

        for rec in self:
            courier = rec.serviced_by_id

            def _line_qty(line):
                for attr in ('qty', 'quantity', 'product_uom_qty', 'qty_done', 'product_qty'):
                    val = getattr(line, attr, None)
                    if val not in (None, False):
                        try:
                            return float(val)
                        except Exception:
                            return val
                return 1.0

            # ----------------------------
            # If courier mapped and product exists: ensure we have one hidden courier request line only,
            # but DO NOT delete other lines that merely "look" like courier through name/code.
            # ----------------------------
            if courier and getattr(courier, 'courier_product_id', False):
                courier_prod = courier.courier_product_id

                # require tracking on the courier product (unchanged)
                if getattr(courier_prod, 'tracking', None) not in ('serial', 'lot'):
                    raise ValidationError(_(
                        "Courier product '%s' must be serial/lot tracked. Please set Inventory → Tracking on the product."
                    ) % (courier_prod.display_name,))

                # Find an existing request line that references the exact courier product
                existing_prod_lines = rec.line_ids.filtered(
                    lambda l: getattr(l, 'product_id', False) and l.product_id.id == courier_prod.id)

                # If none exists, create one hidden; if one exists, leave it (do not delete any other lines)
                if not existing_prod_lines:
                    try:
                        rl_vals = {
                            'request_id': rec.id,
                            'product_id': courier_prod.id,
                            'unit_price': getattr(courier_prod, 'list_price',
                                                  getattr(courier_prod, 'lst_price', 0.0)) or 0.0,
                            'is_courier_hidden': True,
                        }
                        new_request_line = self.env['codeware.request.line'].sudo().create(rl_vals)
                    except Exception as e:
                        raise ValidationError(_("Failed to create courier request line: %s") % e)

                    if not new_request_line or not new_request_line.exists():
                        raise ValidationError(_("Failed to create courier request line for request %s") % rec.name)

                # If there are existing lines for the exact courier product, ensure they are marked hidden
                else:
                    try:
                        existing_prod_lines.sudo().write({'is_courier_hidden': True})
                    except Exception:
                        # non-fatal; continue
                        _logger.exception("Failed to mark existing courier request line hidden for request %s", rec.id)

            # Do NOT delete other "courier-like" lines by name — leave them as-is

            # Ensure the form cache is invalidated so UI sees updated one2many contents
            try:
                rec.invalidate_cache()
            except Exception:
                pass

            # ----------------------------
            # Create or confirm request.order (unchanged)
            # ----------------------------
            if not rec.request_order_id:
                ro_vals = {
                    'request_id': rec.id,
                    'sender_name': rec.sender_name,
                    'sender_address': rec.sender_address,
                    'customer_name': rec.customer_name,
                    'customer_address': rec.customer_address,
                    'state': 'confirmed',
                }
                ro = self.env['codeware.request.order'].sudo().create(ro_vals)
                if not ro:
                    raise ValidationError(_("Failed to create request.order for request %s") % rec.name)
                rec.request_order_id = ro.id
            else:
                rec.request_order_id.sudo().write({'state': 'confirmed'})

            # ----------------------------
            # Create Sale Order (quotation)
            # ----------------------------
            partner = rec.partner_id
            if not partner:
                raise ValidationError(_("Customer is missing — cannot create Sale Order."))

            sale_vals = {
                'partner_id': partner.id,
                'origin': rec.name,
                'request_id': rec.id,
                'delivery_hub_id': getattr(rec, 'source_hub_id', False) and rec.source_hub_id.id or False,
                'fincode_id': getattr(rec, 'dest_fincode_id', False) and rec.dest_fincode_id.id or False,
            }
            sale = self.env['sale.order'].sudo().create(sale_vals)
            if not sale or not sale.exists():
                raise ValidationError(_("Failed to create Sale Order for request %s") % rec.name)

            # Assign serviced_by to all pickings created from this sale (best-effort)
            for pick in sale.picking_ids:
                try:
                    pick.sudo().write({'picking_serviced_by_id': rec.serviced_by_id.id})
                except Exception:
                    pass

            # ----------------------------
            # Create sale lines from request lines - create courier sale line hidden where it exactly matches
            # ----------------------------
            courier_prod_id = courier.courier_product_id.id if courier and getattr(courier, 'courier_product_id',
                                                                                   False) else False

            for line in rec.line_ids:
                qty = _line_qty(line)

                # If this line references the exact courier product -> create hidden sale line mapped to request line
                if courier_prod_id and getattr(line, 'product_id', False) and line.product_id.id == courier_prod_id:
                    # create mapping sale line but DO NOT delete anything else
                    try:
                        sl_vals = {
                            'order_id': sale.id,
                            'product_id': line.product_id.id,
                            'name': getattr(line.product_id, 'name', False) or '',
                            'product_uom_qty': qty,
                            'price_unit': getattr(line, 'unit_price', 0.0),
                            'request_line_id': line.id,
                            'is_courier_hidden': True,
                        }
                        self.env['sale.order.line'].sudo().create(sl_vals)
                    except Exception:
                        _logger.exception("Failed to create hidden sale.order.line for courier product on request %s",
                                          rec.id)
                    continue

                # Normal sale line
                try:
                    self.env['sale.order.line'].sudo().create({
                        'order_id': sale.id,
                        'product_id': getattr(line, 'product_id', False) and line.product_id.id or False,
                        'name': getattr(line, 'product_id', False) and line.product_id.name or (line.name or ''),
                        'product_uom_qty': qty,
                        'price_unit': getattr(line, 'unit_price', 0.0),
                        'request_line_id': line.id,
                    })
                except Exception:
                    _logger.exception("Failed to create sale.order.line for request %s, line %s", rec.id,
                                      getattr(line, 'id', False))

            # link sale to request defensively
            try:
                sale.sudo().write({'request_id': rec.id})
            except Exception:
                pass
            rec.sale_id = sale.id

            # ----------------------------
            # Mark exact courier-related rows hidden (only where product matches exactly)
            # ----------------------------
            if courier and getattr(courier, 'courier_product_id', False):
                prod_id = courier.courier_product_id.id

                # mark request lines for this request (only exact matches)
                try:
                    rec.line_ids.filtered(
                        lambda l: getattr(l, 'product_id', False) and l.product_id.id == prod_id).sudo().write(
                        {'is_courier_hidden': True})
                except Exception:
                    pass

                # mark sale lines on this sale (only exact matches)
                try:
                    sale.order_line.filtered(
                        lambda l: getattr(l, 'product_id', False) and l.product_id.id == prod_id).sudo().write(
                        {'is_courier_hidden': True})
                except Exception:
                    pass

                # mark moves for this sale (so picking view domain will hide them) for exact matches only
                try:
                    moves = self.env['stock.move'].sudo().search([
                        ('sale_line_id.order_id', '=', sale.id),
                        ('product_id', '=', prod_id),
                    ])
                    if moves:
                        moves.sudo().write({'is_courier_hidden': True})
                except Exception:
                    pass

            # Finalize request state and post a short debug message
            rec.state = 'confirmed'
            try:
                hidden_ids = rec.line_ids.filtered(lambda l: getattr(l, 'is_courier_hidden', False)).ids
                msg = "Request confirmed. courier: %s; sale: %s; hidden_lines: %s" % (
                    bool(courier and getattr(courier, 'courier_product_id', False)),
                    sale.name if sale else 'N/A',
                    ','.join(str(i) for i in hidden_ids),
                )
                rec.message_post(body=_(msg))
            except Exception:
                pass

        return True

    # working one
    # def action_confirm(self):
    #     """
    #     Robust confirm: ensure courier request/sale lines are created hidden and related moves are flagged.
    #     Behavior:
    #       - remove any existing courier-like request lines (defensive)
    #       - create exactly one hidden courier request.line (is_courier_hidden = True)
    #       - create sale.order (quotation) and sale.order.lines, creating the courier sale line as hidden
    #       - mark related sale.order.line and stock.move records hidden (so view domain hides them)
    #       - invalidate cache so UI immediately reflects the DB changes
    #     """
    #     self._validate_before_send_or_confirm()
    #
    #     for rec in self:
    #         courier = rec.serviced_by_id
    #
    #         def _is_courier_like(line):
    #             p = getattr(line, 'product_id', None)
    #             if not p:
    #                 return False
    #             dc = (p.default_code or '').upper()
    #             nm = (p.name or '').upper()
    #             return any(token in dc or token in nm for token in ('AWBN', 'DHL', 'UPS', 'FEDEX', 'COURIER'))
    #
    #         def _line_qty(line):
    #             for attr in ('qty', 'quantity', 'product_uom_qty', 'qty_done', 'product_qty'):
    #                 val = getattr(line, attr, None)
    #                 if val not in (None, False):
    #                     try:
    #                         return float(val)
    #                     except Exception:
    #                         return val
    #             return 1.0
    #
    #         # ----------------------------
    #         # If courier mapped and product exists: ensure we have one hidden courier request line only
    #         # ----------------------------
    #         if courier and getattr(courier, 'courier_product_id', False):
    #             courier_prod = courier.courier_product_id
    #
    #             # require tracking on the courier product
    #             if getattr(courier_prod, 'tracking', None) not in ('serial', 'lot'):
    #                 raise ValidationError(_(
    #                     "Courier product '%s' must be serial/lot tracked. Please set Inventory → Tracking on the product."
    #                 ) % (courier_prod.display_name,))
    #
    #             # --- remove any courier-like lines that are not the desired product
    #             if rec.line_ids:
    #                 to_remove = rec.line_ids.filtered(
    #                     lambda l: _is_courier_like(l) and (not l.product_id or l.product_id.id != courier_prod.id)
    #                 )
    #                 if to_remove:
    #                     to_remove.sudo().unlink()
    #
    #             # --- remove any existing lines for this courier product (defensive)
    #             existing_prod_lines = rec.line_ids.filtered(
    #                 lambda l: l.product_id and l.product_id.id == courier_prod.id)
    #             if existing_prod_lines:
    #                 existing_prod_lines.sudo().unlink()
    #
    #             # --- create one fresh hidden courier request line
    #             try:
    #                 rl_vals = {
    #                     'request_id': rec.id,
    #                     'product_id': courier_prod.id,
    #                     'unit_price': getattr(courier_prod, 'list_price',
    #                                           getattr(courier_prod, 'lst_price', 0.0)) or 0.0,
    #                     'is_courier_hidden': True,
    #                 }
    #                 new_request_line = self.env['codeware.request.line'].sudo().create(rl_vals)
    #             except Exception as e:
    #                 raise ValidationError(_("Failed to create courier request line: %s") % e)
    #
    #             if not new_request_line or not new_request_line.exists():
    #                 raise ValidationError(_("Failed to create courier request line for request %s") % rec.name)
    #
    #         else:
    #             # courier not set or no mapped product: remove any courier-like lines (cleanup)
    #             if rec.line_ids:
    #                 to_unlink = rec.line_ids.filtered(lambda l: _is_courier_like(l))
    #                 if to_unlink:
    #                     to_unlink.sudo().unlink()
    #
    #         # Ensure the form cache is invalidated so UI sees updated one2many contents
    #         try:
    #             rec.invalidate_cache()
    #         except Exception:
    #             # not critical if this fails, but best-effort
    #             pass
    #
    #         # ----------------------------
    #         # Create or confirm request.order (unchanged)
    #         # ----------------------------
    #         if not rec.request_order_id:
    #             ro_vals = {
    #                 'request_id': rec.id,
    #                 'sender_name': rec.sender_name,
    #                 'sender_address': rec.sender_address,
    #                 'customer_name': rec.customer_name,
    #                 'customer_address': rec.customer_address,
    #                 'state': 'confirmed',
    #             }
    #             ro = self.env['codeware.request.order'].sudo().create(ro_vals)
    #             if not ro:
    #                 raise ValidationError(_("Failed to create request.order for request %s") % rec.name)
    #             rec.request_order_id = ro.id
    #         else:
    #             rec.request_order_id.sudo().write({'state': 'confirmed'})
    #
    #         # ----------------------------
    #         # Create Sale Order (quotation)
    #         # ----------------------------
    #         partner = rec.partner_id
    #         if not partner:
    #             raise ValidationError(_("Customer is missing — cannot create Sale Order."))
    #
    #         sale_vals = {
    #             'partner_id': partner.id,
    #             'origin': rec.name,
    #             'request_id': rec.id,
    #             'delivery_hub_id': getattr(rec, 'source_hub_id', False) and rec.source_hub_id.id or False,
    #             'fincode_id': getattr(rec, 'dest_fincode_id', False) and rec.dest_fincode_id.id or False,
    #         }
    #         sale = self.env['sale.order'].sudo().create(sale_vals)
    #         if not sale or not sale.exists():
    #             raise ValidationError(_("Failed to create Sale Order for request %s") % rec.name)
    #
    #         # Assign serviced_by to all pickings created from this sale (best-effort)
    #         for pick in sale.picking_ids:
    #             try:
    #                 pick.sudo().write({'picking_serviced_by_id': rec.serviced_by_id.id})
    #             except Exception:
    #                 pass
    #
    #         # ----------------------------
    #         # Create sale lines from request lines - create courier sale line hidden where applicable
    #         # ----------------------------
    #         courier_prod_id = courier.courier_product_id.id if courier and getattr(courier, 'courier_product_id',
    #                                                                                False) else False
    #
    #         for line in rec.line_ids:
    #             qty = _line_qty(line)
    #
    #             # If this line is courier product -> create hidden sale line mapped to request line
    #             if courier_prod_id and line.product_id and line.product_id.id == courier_prod_id:
    #                 # delete any existing sale lines for same mapping (defensive)
    #                 existing_sl = self.env['sale.order.line'].sudo().search([
    #                     ('order_id', '=', sale.id),
    #                     ('product_id', '=', line.product_id.id),
    #                     ('request_line_id', '=', line.id),
    #                 ])
    #                 if existing_sl:
    #                     existing_sl.sudo().unlink()
    #
    #                 sl_vals = {
    #                     'order_id': sale.id,
    #                     'product_id': line.product_id.id,
    #                     'name': line.product_id.name,
    #                     'product_uom_qty': qty,
    #                     'price_unit': line.unit_price,
    #                     'request_line_id': line.id,
    #                     'is_courier_hidden': True,
    #                 }
    #                 new_sl = self.env['sale.order.line'].sudo().create(sl_vals)
    #                 if not new_sl or not new_sl.exists():
    #                     raise ValidationError(_("Failed to create hidden sale.order.line for courier product %s") % (
    #                         line.product_id.display_name,))
    #                 continue
    #
    #             # Normal sale line
    #             try:
    #                 self.env['sale.order.line'].sudo().create({
    #                     'order_id': sale.id,
    #                     'product_id': line.product_id.id,
    #                     'name': line.product_id.name,
    #                     'product_uom_qty': qty,
    #                     'price_unit': line.unit_price,
    #                     'request_line_id': line.id,
    #                 })
    #             except Exception:
    #                 # non-critical: ignore single-line create failures
    #                 pass
    #
    #         # link sale to request defensively
    #         try:
    #             sale.sudo().write({'request_id': rec.id})
    #         except Exception:
    #             pass
    #         rec.sale_id = sale.id
    #
    #         # ----------------------------
    #         # DEFENSIVE: ensure any courier-related rows are flagged hidden
    #         # ----------------------------
    #         if courier and getattr(courier, 'courier_product_id', False):
    #             prod_id = courier.courier_product_id.id
    #
    #             # mark request lines for this request
    #             try:
    #                 rec.line_ids.filtered(lambda l: l.product_id and l.product_id.id == prod_id).sudo().write(
    #                     {'is_courier_hidden': True})
    #             except Exception:
    #                 pass
    #
    #             # mark sale lines on this sale
    #             try:
    #                 sale.order_line.filtered(lambda l: l.product_id and l.product_id.id == prod_id).sudo().write(
    #                     {'is_courier_hidden': True})
    #             except Exception:
    #                 pass
    #
    #             # mark moves for this sale (so picking view domain will hide them)
    #             try:
    #                 moves = self.env['stock.move'].sudo().search([
    #                     ('sale_line_id.order_id', '=', sale.id),
    #                     ('product_id', '=', prod_id),
    #                 ])
    #                 if moves:
    #                     moves.sudo().write({'is_courier_hidden': True})
    #             except Exception:
    #                 pass
    #
    #         # Finalize request state and post a short debug message
    #         rec.state = 'confirmed'
    #         try:
    #             hidden_ids = rec.line_ids.filtered(lambda l: getattr(l, 'is_courier_hidden', False)).ids
    #             msg = "Request confirmed. courier: %s; sale: %s; hidden_lines: %s" % (
    #                 bool(courier and getattr(courier, 'courier_product_id', False)),
    #                 sale.name if sale else 'N/A',
    #                 ','.join(str(i) for i in hidden_ids),
    #             )
    #             rec.message_post(body=_(msg))
    #         except Exception:
    #             pass
    #
    #     return True

    # -------------------------
    def action_create_payment(self, amount=None, journal_id=None):
        """
        Create & POST a payment immediately and open its form view.
        """
        self.ensure_one()

        if not self.partner_id:
            raise ValidationError(_("Please set a Customer before creating a payment."))

        amt = amount if amount is not None else (getattr(self, 'amount_total', 0.0) or 0.0)
        if float(amt) <= 0:
            raise ValidationError(_("Payment amount must be positive."))

        journal = None
        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
        else:
            journal = self.env['account.journal'].search(
                [('type', 'in', ['bank', 'cash']), ('company_id', '=', self.env.company.id)],
                limit=1)
        if not journal:
            raise ValidationError(_("No bank or cash journal found. Please configure one."))

        company_id = None
        try:
            if hasattr(self, 'company_id') and getattr(self, 'company_id'):
                company_id = self.company_id.id
        except Exception:
            company_id = None
        if not company_id:
            company_id = self.env.company.id

        candidate_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_id.id,
            'amount': float(amt),
            'journal_id': journal.id,
            'company_id': company_id,
            'communication': 'REQ/%s' % (getattr(self, 'name', '')),
            'payment_reference': _('Payment for %s') % (getattr(self, 'name', self.partner_id.name)),
        }

        try:
            pm = self.env.ref('account.account_payment_method_manual_in', raise_if_not_found=False)
            if pm:
                candidate_vals['payment_method_id'] = pm.id
        except Exception:
            pass

        Payment = self.env['account.payment'].sudo()
        allowed_fields = set(Payment._fields.keys())
        safe_vals = {k: v for k, v in candidate_vals.items() if k in allowed_fields}

        try:
            payment = Payment.create(safe_vals)
        except Exception as e:
            _logger.exception("Failed to create payment for request %s: %s", getattr(self, 'id', False), e)
            raise UserError(_("Failed to create payment: %s") % e)

        try:
            if hasattr(payment, 'action_post'):
                payment.action_post()
            else:
                payment.post()
        except Exception as e:
            _logger.exception("Failed to post payment %s for request %s: %s", getattr(payment, 'id', False),
                              getattr(self, 'id', False), e)
            raise UserError(_("Payment was created but posting failed: %s") % e)

        try:
            if 'codeware_request_id' in payment._fields:
                payment.sudo().write({'codeware_request_id': self.id})
        except Exception:
            _logger.exception("Failed writing codeware_request_id on payment %s", getattr(payment, 'id', False))

        try:
            to_write = {}
            if 'payment_ids' in self._fields:
                to_write['payment_ids'] = [(4, payment.id)]
            if 'primary_payment_id' in self._fields:
                to_write['primary_payment_id'] = payment.id
            if to_write:
                self.sudo().write(to_write)
        except Exception:
            _logger.exception("Failed to link payment %s to request %s", getattr(payment, 'id', False),
                              getattr(self, 'id', False))

        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
        }

    # -------------------------
    def _reconcile_payment_with_invoice(self, invoice):
        self.ensure_one()
        if not invoice or invoice.state != 'posted':
            return False

        reconciled_any = False

        posted_payments = self.payment_ids.filtered(lambda p: p.state in ('posted', 'reconciled'))
        if not posted_payments:
            post_domain = [('state', 'in', ('posted', 'reconciled')), ('partner_id', '=', self.partner_id.id)]
            if hasattr(self.env['account.payment'], 'codeware_request_id'):
                post_domain.append(('codeware_request_id', '=', self.id))
            posted_payments = self.env['account.payment'].search(post_domain)

        inv_receivable_lines = invoice.line_ids.filtered(lambda l: l.account_id.user_type_id.type == 'receivable')

        if not posted_payments or not inv_receivable_lines:
            return False

        for pay in posted_payments:
            try:
                payment_move_lines = self.env['account.move.line']
                if hasattr(pay, 'move_id') and pay.move_id:
                    payment_move_lines = pay.move_id.line_ids.filtered(
                        lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
                elif hasattr(pay, 'line_ids'):
                    payment_move_lines = pay.line_ids.filtered(
                        lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
            except Exception:
                _logger.exception("Error finding move lines for payment %s", pay.id)
                continue

            for inv_line in inv_receivable_lines:
                candidates = payment_move_lines.filtered(
                    lambda l: l.account_id == inv_line.account_id and l.partner_id == inv_line.partner_id)
                if not candidates:
                    candidates = payment_move_lines.filtered(lambda l: l.partner_id == inv_line.partner_id)

                if not candidates:
                    continue

                lines_to_reconcile = candidates | inv_line
                try:
                    if hasattr(lines_to_reconcile, 'reconcile'):
                        lines_to_reconcile.reconcile()
                        reconciled_any = True
                    else:
                        first_candidate = candidates[:1]
                        if first_candidate and hasattr(first_candidate, 'reconcile'):
                            (first_candidate | inv_line).reconcile()
                            reconciled_any = True
                except Exception:
                    _logger.exception("Failed to reconcile invoice %s line %s with payment %s", invoice.id, inv_line.id,
                                      pay.id)
                    continue

        return reconciled_any

    # -------------------------
    def action_view_request_order(self):
        self.ensure_one()
        if not self.request_order_id:
            return {
                'name': 'Request Orders',
                'type': 'ir.actions.act_window',
                'res_model': 'codeware.request.order',
                'view_mode': 'list,form',
                'domain': [('request_id', '=', self.id)],
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Request Order',
            'res_model': 'codeware.request.order',
            'view_mode': 'form',
            'res_id': self.request_order_id.id,
            'target': 'current',
        }

    def action_print_request(self):
        self.ensure_one()
        return self.env.ref('courier_management_final.action_report_request_order_v2').report_action(self)

    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            try:
                if rec.dest_fincode_id or rec.zip_input:
                    rec.apply_fincode_to_request()
            except Exception:
                _logger.exception("Error applying fincode on create for request %s", rec.id)
        return records

    def write(self, vals):
        _logger.debug("codeware.request: incoming write on ids=%s vals=%s", self.ids, vals)
        skip_apply = bool(self.env.context.get('_skip_apply_fincode', False))

        res = super().write(vals)

        if not skip_apply:
            try:
                apply_needed = False
                if 'dest_fincode_id' in vals or 'zip_input' in vals:
                    apply_needed = True
                for rec in self:
                    if apply_needed or rec.dest_fincode_id:
                        rec.with_context(_skip_apply_fincode=True).apply_fincode_to_request()
            except Exception:
                _logger.exception("Error post-write applying fincode for requests %s", self.ids)
        return res

    @api.constrains('zip_input')
    def _check_zip_input(self):
        for rec in self:
            if rec.zip_input and not (rec.zip_input.isdigit() and len(rec.zip_input) == 6):
                raise ValidationError(_("ZIP must be exactly 6 digits."))

    @api.constrains('dest_zip')
    def _check_dest_zip(self):
        for rec in self:
            if rec.dest_zip and not (rec.dest_zip.isdigit() and len(rec.dest_zip) == 6):
                raise ValidationError(_("Destination ZIP must be exactly 6 digits."))

    # -------------------------
    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_id:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'name': _('Sale Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_payments(self):
        self.ensure_one()
        Payment = self.env['account.payment']
        payments = self.payment_ids
        if not payments:
            comm = 'REQ/%s' % (getattr(self, 'name', ''))
            payments = Payment.search([('communication', '=', comm), ('partner_id', '=', self.partner_id.id)])
        if not payments:
            return {'type': 'ir.actions.act_window_close'}
        if len(payments) == 1:
            payment = payments[0]
            return {
                'name': _('Payment'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'res_id': payment.id,
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

    @api.depends('payment_ids.state')
    def _compute_is_fully_paid(self):
        for rec in self:
            paid = False
            for p in rec.payment_ids:
                if p.state in ('posted', 'reconciled', 'paid'):
                    paid = True
                    break
            rec.is_fully_paid = paid

    # -------------------------
    def _default_source_hub(self):
        return self.env['codeware.transithub'].search([('name', '=', 'Calabar Hub')], limit=1).id

    # -------------------------
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            p = rec.partner_id
            if not p:
                return

            # Always fill name
            rec.sender_name = p.name

            # Always fill PHONE correctly (THIS FIXES YOUR ISSUE)
            rec.sender_phone = _get_partner_phone(p)

            # Always fill address
            rec.sender_address = (
                f"{p.street or ''}\n"
                f"{p.city or ''}\n"
                f"{(p.state_id.name if p.state_id else '')}\n"
                f"{p.zip or ''}"
            )

            # Also reflect partner_id into the helper dropdown
            rec.sender_phone_partner = p

    @api.onchange('receiver_id')
    def _onchange_receiver_id(self):
        for rec in self:
            if rec.receiver_id:
                rec.customer_name = rec.receiver_id.name
                rec.receiver_phone = _get_partner_phone(rec.receiver_id)
                rec.customer_address = (
                    f"{rec.receiver_id.street or ''}\n"
                    f"{rec.receiver_id.city or ''}\n"
                    f"{(rec.receiver_id.state_id.name if rec.receiver_id.state_id else '')}\n"
                    f"{rec.receiver_id.zip or ''}"
                )
                rec.receiver_phone_partner = rec.receiver_id

    @api.onchange('receiver_phone')
    def _onchange_receiver_phone(self):
        for rec in self:
            if not rec.receiver_phone:
                continue
            Partner = self.env['res.partner']
            # Prefer exact matches on phone and mobile (mobile checked safely)
            domain = [('phone', '=', rec.receiver_phone)]
            if 'mobile' in Partner._fields:
                domain = ['|', ('phone', '=', rec.receiver_phone), ('mobile', '=', rec.receiver_phone)]
            partner = Partner.search(domain, limit=1)
            if partner:
                rec.receiver_id = partner
                rec.customer_name = partner.name
                rec.customer_address = (
                    f"{partner.street or ''}\n"
                    f"{partner.city or ''}\n"
                    f"{(partner.state_id.name if partner.state_id else '')}\n"
                    f"{partner.zip or ''}"
                )
                rec.receiver_phone_partner = partner

    # -------------------------
    # Transient helper onchanges for phone dropdowns (no DB change)
    @api.onchange('sender_phone_partner')
    def _onchange_sender_phone_partner(self):
        for rec in self:
            p = rec.sender_phone_partner
            if p:
                rec.partner_id = p
                rec.sender_phone = _get_partner_phone(p)
                rec.sender_address = (
                    f"{p.street or ''}\n"
                    f"{p.city or ''}\n"
                    f"{(p.state_id.name if p.state_id else '')}\n"
                    f"{p.zip or ''}"
                )

    @api.onchange('receiver_phone_partner')
    def _onchange_receiver_phone_partner(self):
        for rec in self:
            p = rec.receiver_phone_partner
            if p:
                rec.receiver_id = p
                rec.receiver_phone = _get_partner_phone(p)
                rec.customer_name = p.name
                rec.customer_address = (
                    f"{p.street or ''}\n"
                    f"{p.city or ''}\n"
                    f"{(p.state_id.name if p.state_id else '')}\n"
                    f"{p.zip or ''}"
                )

    # ---------- Fincode persistence helpers ----------
    def _copy_fincode_fields_to_vals(self, fincode):
        """Build vals using FINCODE_TO_REQUEST_MAP first, then copy same-named compatible fields."""
        if not fincode or not fincode.exists():
            return {}
        vals = {}
        ignore_names = {'id', 'create_uid', 'create_date', 'write_uid', 'write_date', 'display_name'}
        supported_types = {
            'char', 'text', 'integer', 'float', 'boolean',
            'selection', 'date', 'datetime', 'many2one', 'many2many'
        }

        for fin_name, map_info in getattr(self, 'FINCODE_TO_REQUEST_MAP', {}).items():
            try:
                target_field = map_info[0] if isinstance(map_info, (list, tuple)) else map_info
            except Exception:
                target_field = map_info
            if not target_field or target_field not in self._fields:
                _logger.debug("Fincode mapping: target field %s not present on request model; skipping", target_field)
                continue
            if fin_name not in fincode._fields:
                _logger.debug("Fincode mapping: source field %s not present on fincode; skipping", fin_name)
                continue

            fmeta = fincode._fields[fin_name]
            ftype = fmeta.type
            if ftype not in supported_types:
                _logger.debug("Fincode mapping: unsupported type %s for field %s; skipping", ftype, fin_name)
                continue

            try:
                if ftype in ('char', 'text', 'selection', 'date', 'datetime', 'integer', 'float', 'boolean'):
                    vals[target_field] = getattr(fincode, fin_name) or False
                elif ftype == 'many2one':
                    rel = getattr(fincode, fin_name)
                    vals[target_field] = rel.id if rel else False
                elif ftype == 'many2many':
                    relset = getattr(fincode, fin_name)
                    ids = relset.ids if relset else []
                    vals[target_field] = [(6, 0, ids)]
                _logger.debug("Mapped fin.%s -> req.%s = %s", fin_name, target_field, vals.get(target_field))
            except Exception:
                _logger.exception("Failed to map fin.%s -> req.%s", fin_name, target_field)

        for fname, fmeta in fincode._fields.items():
            if fname in ignore_names:
                continue
            if fname in getattr(self, 'FINCODE_TO_REQUEST_MAP', {}):
                continue
            if fname not in self._fields:
                continue
            if fname in vals:
                continue
            ftype = fmeta.type
            if ftype not in supported_types:
                continue
            try:
                if ftype in ('char', 'text', 'selection', 'date', 'datetime', 'integer', 'float', 'boolean'):
                    vals[fname] = getattr(fincode, fname) or False
                elif ftype == 'many2one':
                    rel = getattr(fincode, fname)
                    vals[fname] = rel.id if rel else False
                elif ftype == 'many2many':
                    relset = getattr(fincode, fname)
                    ids = relset.ids if relset else []
                    vals[fname] = [(6, 0, ids)]
                _logger.debug("Copied fin.%s -> req.%s = %s", fname, fname, vals.get(fname))
            except Exception:
                _logger.exception("Failed to copy field %s from fincode %s", fname, getattr(fincode, 'id', False))
        return vals

    def apply_fincode_to_request(self, fincode=None):
        for rec in self:
            fin = None
            if fincode:
                try:
                    if isinstance(fincode, int):
                        fin = self.env['codeware.fincode'].browse(int(fincode))
                    else:
                        fin = fincode
                except Exception:
                    fin = None

            if not fin and getattr(rec, 'dest_fincode_id', False):
                fin = rec.dest_fincode_id
            if not fin:
                zip_val = getattr(rec, 'zip_input', False) or getattr(rec, 'dest_zip', False) or False
                if zip_val:
                    fin = self.env['codeware.fincode'].search([('name', '=', zip_val)], limit=1)

            if not fin or not fin.exists():
                _logger.debug("apply_fincode_to_request: no fincode for request %s (zip=%s, dest_fincode=%s)", rec.id,
                              getattr(rec, 'zip_input', False), getattr(rec, 'dest_fincode_id', False))
                continue

            vals = rec._copy_fincode_fields_to_vals(fin)
            if 'dest_fincode_id' in rec._fields and fin.id:
                vals['dest_fincode_id'] = fin.id

            if not vals:
                _logger.debug("apply_fincode_to_request: no vals built for request %s from fincode %s", rec.id, fin.id)
                continue

            try:
                rec.with_context(_skip_apply_fincode=True).sudo().write(vals)
                _logger.info("apply_fincode_to_request: wrote fields %s to request %s from fincode %s",
                             list(vals.keys()), rec.id, fin.id)
            except Exception:
                _logger.exception("apply_fincode_to_request: failed to write vals for request %s from fincode %s",
                                  rec.id, fin.id)
        return True

    # PRICING RULE
    @api.depends('weight', 'distance', 'priority_type')
    def _compute_amounts(self):
        Weight = self.env['codeware.weight.pricelist']
        Distance = self.env['codeware.distance.pricelist']
        Priority = self.env['codeware.priority.pricelist']

        for rec in self:
            rec.weight_cost = 0.0
            rec.distance_cost = 0.0
            rec.priority_cost = 0.0
            rec.subtotal = 0.0

            # -- WEIGHT --
            if rec.weight is not None:
                try:
                    w = float(rec.weight)
                except Exception:
                    w = None
                if w is not None:
                    w_domain = [
                        ('min_weight', '<=', w),
                        ('max_weight', '>=', w),
                        ('status', '=', 'active')
                    ]
                    w_rec = Weight.search(w_domain, limit=1, order='min_weight asc')
                    if w_rec:
                        rec.weight_cost = w_rec.cost
                    else:
                        _logger.debug("No weight pricelist match for weight=%s (domain=%s)", w, w_domain)

            # -- DISTANCE --
            if rec.distance is not None:
                try:
                    d = float(rec.distance)
                except Exception:
                    d = None
                if d is not None:
                    d_domain = [
                        ('min_distance', '<=', d),
                        ('max_distance', '>=', d),
                        ('status', '=', 'active')
                    ]
                    d_rec = Distance.search(d_domain, limit=1, order='min_distance asc')
                    if d_rec:
                        rec.distance_cost = d_rec.cost
                    else:
                        _logger.debug("No distance pricelist match for distance=%s (domain=%s)", d, d_domain)

            # -- PRIORITY --
            if rec.priority_type:
                p_domain = [
                    ('priority_type', '=', rec.priority_type),
                    ('status', '=', 'active')
                ]
                p_rec = Priority.search(p_domain, limit=1)
                if p_rec:
                    rec.priority_cost = p_rec.cost
                else:
                    _logger.debug("No priority pricelist match for priority=%s", rec.priority_type)

            # -- SUBTOTAL --
            rec.subtotal = (rec.weight_cost or 0.0) + (rec.distance_cost or 0.0) + (rec.priority_cost or 0.0)
            _logger.debug(
                "Computed costs for request %s: weight=%s cost=%s, distance=%s cost=%s, priority=%s cost=%s, subtotal=%s",
                rec.id, rec.weight, rec.weight_cost, rec.distance, rec.distance_cost, rec.priority_type,
                rec.priority_cost, rec.subtotal)

    @api.depends('line_ids.price_subtotal', 'base_price', 'subtotal')
    def _compute_total(self):
        for rec in self:
            base = rec.base_price or 0.0
            lines_total = sum(rec.line_ids.mapped('price_subtotal')) if rec.line_ids else 0.0
            rec.amount_total = base + (rec.subtotal or 0.0) + lines_total





















# # -*- coding: utf-8 -*-
# """
# Merged codeware_request.py - final fixed (tracking & barcode removed from codeware.request only)
# - Safe phone helper _get_partner_phone
# - name_search that works when res.partner.mobile is absent
# - Transient helper Many2one fields for phone dropdown (store=False)
# - All onchange and label_map use safe accessor
# - No DB schema changes, no migrations
# """
#
# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError, UserError
# from odoo.osv import expression
# import logging
# import re
# from odoo.tools.float_utils import float_round
#
# _logger = logging.getLogger(__name__)
#
#
# def _normalize_digits(s):
#     if not s:
#         return ''
#     return re.sub(r'\D', '', s)
#
#
# def _get_partner_phone(partner):
#     """
#     Return partner.mobile if present and truthy else partner.phone if present else ''.
#     Uses getattr to avoid AttributeError on databases that don't have 'mobile'.
#     """
#     if not partner:
#         return ''
#     mobile = getattr(partner, 'mobile', False)
#     if mobile:
#         return mobile
#     phone = getattr(partner, 'phone', False)
#     if phone:
#         return phone
#     return ''
#
#
# class ResPartner(models.Model):
#     _inherit = "res.partner"
#
#     @api.model
#     def name_search(self, name, args=None, operator='ilike', limit=100):
#         """
#         Robust phone-aware name_search that works even if res.partner.mobile is missing.
#
#         Behavior:
#         - If the query contains digits, treat it as phone lookup:
#           1) Try exact normalized-digit match using SQL (only referencing columns that exist).
#           2) Prefix-match (starts-with) using ORM ilike on phone and mobile only if present.
#           3) Fallback to default name_search (positional call to super).
#         - For phone-derived results, return phone-only labels (mobile preferred) so the dropdown shows numbers.
#         - If no digits in query, call default name_search.
#         """
#         args = args or []
#         q = (name or '').strip()
#         results = []
#         seen = set()
#
#         def _append(partners, label_map=None):
#             nonlocal results, seen, limit
#             for p in partners:
#                 if p.id in seen:
#                     continue
#                 seen.add(p.id)
#                 if label_map and p.id in label_map:
#                     label = label_map[p.id]
#                 else:
#                     label = p.name_get()[0][1]
#                 results.append((p.id, label))
#                 if len(results) >= limit:
#                     break
#
#         # whether mobile column exists on this DB
#         has_mobile = 'mobile' in self.env['res.partner']._fields
#
#         # If query contains digits => phone-centric search
#         if q and any(ch.isdigit() for ch in q):
#             norm = ''.join(ch for ch in q if ch.isdigit())
#
#             # 1) Exact normalized match using SQL (guard mobile usage)
#             if norm:
#                 try:
#                     cr = self.env.cr
#                     if has_mobile:
#                         sql = """
#                             SELECT id,
#                                    COALESCE(NULLIF(mobile, ''), NULLIF(phone, ''), '') as num
#                             FROM res_partner
#                             WHERE (regexp_replace(COALESCE(mobile, ''), '\\D', '', 'g') = %s)
#                                OR (regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') = %s)
#                             LIMIT %s
#                         """
#                         cr.execute(sql, (norm, norm, int(limit)))
#                     else:
#                         sql = """
#                             SELECT id,
#                                    COALESCE(NULLIF(phone, ''), '') as num
#                             FROM res_partner
#                             WHERE (regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') = %s)
#                             LIMIT %s
#                         """
#                         cr.execute(sql, (norm, int(limit)))
#                     rows = cr.fetchall()
#                     if rows:
#                         exact_ids = [r[0] for r in rows]
#                         partners_exact = self.browse(exact_ids)
#                         label_map = {r[0]: (r[1] or '') for r in rows}
#                         _append(partners_exact, label_map=label_map)
#                 except Exception:
#                     _logger.exception("name_search: exact normalized SQL failed.")
#
#             # 2) Prefix-match (ilike) on mobile/phone (use mobile only if exists)
#             if len(results) < limit:
#                 remaining = limit - len(results)
#                 pattern = norm + '%'
#                 if has_mobile:
#                     partners_prefix = self.search(
#                         expression.AND([args, ['|', ('mobile', 'ilike', pattern), ('phone', 'ilike', pattern)]]),
#                         limit=remaining
#                     )
#                 else:
#                     partners_prefix = self.search(
#                         expression.AND([args, [('phone', 'ilike', pattern)]]),
#                         limit=remaining
#                     )
#                 # build label map safely using helper
#                 label_map = {p.id: _get_partner_phone(p) for p in partners_prefix}
#                 _append(partners_prefix, label_map=label_map)
#
#             # 3) fallback to default name_search (positional call)
#             if len(results) < limit:
#                 name_results = super(ResPartner, self).name_search(name, args, operator, limit)
#                 for pid, pname in name_results:
#                     if pid not in seen:
#                         seen.add(pid)
#                         results.append((pid, pname))
#                         if len(results) >= limit:
#                             break
#
#             return results[:limit]
#
#         # Non-digit queries: default behaviour
#         return super(ResPartner, self).name_search(name, args, operator, limit)
#
#
# class CodewareRequest(models.Model):
#     _name = 'codeware.request'
#     _description = 'Request Form (Quotation-like)'
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#
#     # ---- basic fields ----
#     name = fields.Char(
#         string='Request Reference',
#         required=True,
#         copy=False,
#         readonly=True,
#         default=lambda self: self.env['ir.sequence'].next_by_code('codeware.request') or 'New'
#     )
#     partner_id = fields.Many2one('res.partner', string='Customer', required=False)
#
#     source_hub_id = fields.Many2one(
#         'codeware.transithub',
#         string='Source Hub',
#         default=lambda self: self._default_source_hub(),
#         readonly=True
#     )
#
#     # Keep sender_name but user asked to avoid auto-filling it (still present)
#     sender_name = fields.Char(string='Sender Name')
#     sender_address = fields.Text(string='Sender Address')
#
#     # Keep DB Char columns (no DB change)
#     sender_phone = fields.Char(string='Sender Phone')
#
#     # Transient helper for sender phone — provides dropdown-by-phone (no DB column)
#     sender_phone_partner = fields.Many2one(
#         'res.partner',
#         string='Sender Phone Number',
#         store=False,
#         help='Helper dropdown: select contact by phone/mobile (typing digits filters).'
#     )
#
#     # Receiver fields — keep your existing naming
#     receiver_id = fields.Many2one('res.partner', string='Receiver')
#     customer_name = fields.Char(string='Reciever Name')
#     customer_address = fields.Text(string='Reciever Address')
#
#     receiver_phone = fields.Char(string='Receiver Phone')
#
#     # Transient helper for receiver phone — provides dropdown-by-phone (no DB column)
#     receiver_phone_partner = fields.Many2one(
#         'res.partner',
#         string='Receiver Phone Number',
#         store=False,
#         help='Helper dropdown for receiver phone.'
#     )
#
#     zip_input = fields.Char(
#         string='Source ZipCode',
#         default='540001',
#         readonly=False,
#     )
#     dest_fincode_id = fields.Many2one('codeware.fincode', string='Destination ZipCode')
#     dest_zip = fields.Char(string='Destination ZIP', related='dest_fincode_id.name', readonly=True, store=True)
#     city = fields.Char(string='City', readonly=True, store=True)
#     state_name = fields.Char(string='State', readonly=True, store=True)
#     base_price = fields.Float(string='Base Price', store=True,
#                               help="Base price pulled from FinCode (can be overridden)",
#                               default=0.0)
#     transit_hub_ids = fields.Many2many('codeware.transithub', string='Transit Hubs', readonly=True, store=True)
#
#     # -------------------------------------------------------------------------
#     # PRICING INPUTS (your logic)
#     # -------------------------------------------------------------------------
#     weight = fields.Float(string="Weight (KG)")
#     distance = fields.Float(string="Distance (KM)")
#     priority_type = fields.Selection([
#         ('normal', 'Normal'),
#         ('express', 'Express'),
#         ('urgent', 'Urgent')
#     ], string="Priority Type")
#
#     subtotal = fields.Float(string="Subtotal", compute="_compute_amounts", store=True)
#
#     weight_cost = fields.Float(string="Weight Cost", compute="_compute_amounts", store=True)
#     distance_cost = fields.Float(string="Distance Cost", compute="_compute_amounts", store=True)
#     priority_cost = fields.Float(string="Priority Cost", compute="_compute_amounts", store=True)
#
#     line_ids = fields.One2many('codeware.request.line', 'request_id', string='Price Lines')
#     amount_total = fields.Float(string='Total Amount', compute='_compute_total', store=True)
#     is_fully_paid = fields.Boolean(
#         string='Is Fully Paid',
#         compute='_compute_is_fully_paid',
#         store=False,
#     )
#     state = fields.Selection([
#         ('draft', 'Draft'),
#         ('sent', 'Quotation Sent'),
#         ('confirmed', 'Confirmed'),
#     ], string='Status', default='draft', tracking=True)
#
#     request_order_id = fields.Many2one('codeware.request.order', string='Request Order', readonly=True, copy=False)
#     request_order_count = fields.Integer(string='Request Orders', compute='_compute_request_order_count', store=True)
#     tracking_number = fields.Char(
#         compute="_compute_tracking_number",
#         store=False,
#         readonly=True,
#     )
#
#     # FINCODE -> REQUEST mapping
#     FINCODE_TO_REQUEST_MAP = {
#         'name': ('dest_zip', 'simple'),
#         'city': ('city', 'simple'),
#         'state': ('state_name', 'simple'),
#         'base_price': ('base_price', 'simple'),
#         'hub_ids': ('transit_hub_ids', 'm2m'),
#     }
#     serviced_by_id = fields.Many2one(
#         'codeware.courier.company',
#         string="Serviced By",
#         readonly=True
#     )
#
#     # Links to sale & invoices (persisted fields)
#     sale_id = fields.Many2one('sale.order', string="Sale Order", readonly=True, copy=False)
#     invoice_ids = fields.Many2many('account.move', string="Invoices", readonly=True, copy=False)
#
#     # ==== PAYMENT LINKS ====
#     payment_ids = fields.Many2many(
#         'account.payment',
#         string='Payments',
#         readonly=True,
#         copy=False
#     )
#
#     primary_payment_id = fields.Many2one(
#         'account.payment',
#         string='Primary Payment',
#         readonly=True,
#         copy=False,
#     )
#
#     # ----- UI helper fields (counts) -----
#     sale_count = fields.Integer(string='Sales', compute='_compute_link_counts', store=False)
#     payment_count = fields.Integer(string='Payments', compute='_compute_link_counts', store=False)
#
#     # ----------------- computes -----------------
#     @api.depends('request_order_id')
#     def _compute_request_order_count(self):
#         for rec in self:
#             rec.request_order_count = 1 if rec.request_order_id else 0
#
#     @api.depends('sale_id', 'payment_ids')
#     def _compute_link_counts(self):
#         for rec in self:
#             rec.sale_count = 1 if rec.sale_id else 0
#             rec.payment_count = len(rec.payment_ids or [])
#
#     @api.depends("sale_id")
#     def _compute_tracking_number(self):
#         for rec in self:
#             rec.tracking_number = False
#
#             if not rec.sale_id:
#                 continue
#
#             # Find picking by sale_id
#             pickings = rec.env["stock.picking"].search([
#                 ("sale_id", "=", rec.sale_id.id)
#             ], limit=1)
#
#             if pickings:
#                 rec.tracking_number = pickings.tracking_number or False
#
#     # ----------------- onchanges -----------------
#     @api.onchange('zip_input')
#     def _onchange_zip_input(self):
#         for rec in self:
#             if rec.zip_input:
#                 fin = self.env['codeware.fincode'].search([('name', '=', rec.zip_input)], limit=1)
#                 if fin:
#                     rec.dest_fincode_id = fin.id
#                     rec.city = fin.city
#                     rec.state_name = fin.state
#                     if not rec.base_price and fin.base_price:
#                         rec.base_price = fin.base_price
#                     rec.transit_hub_ids = [(6, 0, fin.hub_ids.ids)] if hasattr(fin, 'hub_ids') else [(6, 0, [])]
#                 else:
#                     rec.dest_fincode_id = False
#             else:
#                 rec.dest_fincode_id = False
#
#     @api.onchange('dest_fincode_id')
#     def _onchange_dest_fincode_id(self):
#         for rec in self:
#             if rec.dest_fincode_id:
#                 fin = rec.dest_fincode_id
#
#                 # existing logic
#                 if not rec.base_price and fin.base_price:
#                     rec.base_price = fin.base_price
#                 rec.city = fin.city
#                 rec.state_name = fin.state
#                 rec.transit_hub_ids = [(6, 0, fin.hub_ids.ids)] if hasattr(fin, 'hub_ids') else [(6, 0, [])]
#
#                 # NEW: autofill service provider
#                 rec.serviced_by_id = fin.serviced_by_id.id if fin.serviced_by_id else False
#
#             else:
#                 rec.city = False
#                 rec.state_name = False
#                 rec.transit_hub_ids = [(6, 0, [])]
#                 rec.serviced_by_id = False
#
#     # @api.onchange('dest_fincode_id')
#     # def _onchange_dest_fincode_id(self):
#     #     for rec in self:
#     #         if rec.dest_fincode_id:
#     #             fin = rec.dest_fincode_id
#     #             if not rec.base_price and fin.base_price:
#     #                 rec.base_price = fin.base_price
#     #             rec.city = fin.city
#     #             rec.state_name = fin.state
#     #             rec.transit_hub_ids = [(6, 0, fin.hub_ids.ids)] if hasattr(fin, 'hub_ids') else [(6, 0, [])]
#     #         else:
#     #             rec.city = False
#     #             rec.state_name = False
#     #             rec.transit_hub_ids = [(6, 0, [])]
#
#     # ----------------- validation helper -----------------
#     def _validate_before_send_or_confirm(self):
#         for rec in self:
#             if not rec.line_ids:
#                 raise ValidationError(_("Please add at least one Price Line before proceeding."))
#             if not rec.partner_id:
#                 raise ValidationError(_("Please select a Customer before proceeding."))
#             # if not rec.source_hub_id:
#             #     raise ValidationError(_("Please select a Source Hub before proceeding."))
#             if not rec.dest_fincode_id:
#                 raise ValidationError(_("Please select Destination FinCode (ZIP) before proceeding."))
#             if not rec.sender_name or not rec.sender_address:
#                 raise ValidationError(_("Please fill Sender Name and Sender Address before proceeding."))
#             if not rec.customer_name or not rec.customer_address:
#                 raise ValidationError(_("Please fill Customer Name and Customer Address before proceeding."))
#
#     def action_send_quotation(self):
#         self._validate_before_send_or_confirm()
#         for rec in self:
#             rec.state = 'sent'
#             try:
#                 rec.message_post(body=_("Quotation sent."))
#             except Exception:
#                 pass
#         return True
#
#     # def action_confirm(self):
#     #     """
#     #     Confirm the request:
#     #     - create request.order (existing logic)
#     #     - create a Sale Order in QUOTATION state (do NOT confirm it here)
#     #     Note: tracking & barcode generation removed from this model (kept in request.order if present).
#     #     """
#     #     self._validate_before_send_or_confirm()
#     #
#     #     for rec in self:
#     #         if not rec.request_order_id:
#     #             ro_vals = {
#     #                 'request_id': rec.id,
#     #                 'sender_name': rec.sender_name,
#     #                 'sender_address': rec.sender_address,
#     #                 'customer_name': rec.customer_name,
#     #                 'customer_address': rec.customer_address,
#     #                 'state': 'confirmed',
#     #             }
#     #             ro = self.env['codeware.request.order'].create(ro_vals)
#     #             rec.request_order_id = ro.id
#     #         else:
#     #             rec.request_order_id.sudo().write({'state': 'confirmed'})
#     #
#     #         partner = rec.partner_id
#     #         if not partner:
#     #             raise ValidationError("Customer is missing — cannot create Sale Order.")
#     #
#     #         sale_vals = {
#     #             'partner_id': partner.id,
#     #             'origin': rec.name,
#     #             'request_id': rec.id,
#     #             'delivery_hub_id': rec.source_hub_id.id,
#     #             'fincode_id': rec.dest_fincode_id.id,
#     #
#     #         }
#     #         sale = self.env['sale.order'].create(sale_vals)
#     #
#     #         # Assign serviced_by to all pickings created from this sale
#     #         for pick in sale.picking_ids:
#     #             pick.picking_serviced_by_id = rec.serviced_by_id.id
#     #
#     #         service_product = rec._get_service_product()
#     #         for line in rec.line_ids:
#     #             self.env['sale.order.line'].create({
#     #                 'order_id': sale.id,
#     #                 'product_id': line.product_id.id,
#     #                 'name': line.product_id.name,
#     #                 'product_uom_qty': 1,
#     #                 'price_unit': line.unit_price,
#     #                 'request_line_id': line.id,
#     #             })
#     #
#     #         try:
#     #             sale.write({'request_id': rec.id})
#     #         except Exception:
#     #             pass
#     #         rec.sale_id = sale.id
#     #
#     #         rec.state = 'confirmed'
#     #         try:
#     #             rec.message_post(body=_("Request confirmed."))
#     #         except Exception:
#     #             pass
#     #
#     #     return True
#
#     def action_confirm(self):
#         """
#         Confirm the request:
#         - create request.order (existing logic)
#         - create a Sale Order in QUOTATION state (do NOT confirm it here)
#         Note: tracking & barcode generation removed from this model (kept in request.order if present).
#         """
#         self._validate_before_send_or_confirm()
#
#         for rec in self:
#
#             # ----------------------------
#             # Backend-only: ensure exactly one courier request line
#             # ----------------------------
#             courier = rec.serviced_by_id
#
#             def _find_courier_product(courier_rec):
#                 """Find courier product using mapping or fallbacks."""
#                 if not courier_rec:
#                     return False
#
#                 Product = self.env['product.product']
#
#                 # 1) direct mapping on courier company
#                 prod = getattr(courier_rec, 'courier_product_id', False)
#                 if prod:
#                     return prod
#
#                 name_up = (courier_rec.name or '').upper()
#
#                 # 2) fallback by default_code
#                 if 'DHL' in name_up:
#                     p = Product.search([('default_code', 'ilike', 'DHL_AWBN')], limit=1)
#                     if p:
#                         return p
#
#                 if 'UPS' in name_up:
#                     p = Product.search([('default_code', 'ilike', 'UPS_AWBN')], limit=1)
#                     if p:
#                         return p
#
#                 # 3) fallback by product name match
#                 if 'DHL' in name_up:
#                     p = Product.search([('name', 'ilike', 'DHL')], limit=1)
#                     if p:
#                         return p
#
#                 if 'UPS' in name_up:
#                     p = Product.search([('name', 'ilike', 'UPS')], limit=1)
#                     if p:
#                         return p
#
#                 return False
#
#             def _is_courier_like(line):
#                 """Identify courier-like request lines."""
#                 p = line.product_id
#                 if not p:
#                     return False
#
#                 dc = (p.default_code or '').upper()
#                 nm = (p.name or '').upper()
#
#                 return any(token in dc or token in nm for token in ('AWBN', 'DHL', 'UPS'))
#
#             # Remove courier-like lines that don't match the current courier
#             desired_product = False
#             if courier and (courier.name or '').strip().lower() != 'cserve':
#                 desired_product = _find_courier_product(courier)
#
#             if rec.line_ids:
#                 lines_to_remove = rec.line_ids.filtered(
#                     lambda l: _is_courier_like(l) and
#                               (not desired_product or l.product_id.id != desired_product.id)
#                 )
#                 if lines_to_remove:
#                     try:
#                         lines_to_remove.unlink()
#                     except Exception:
#                         import logging
#                         _logger = logging.getLogger(__name__)
#                         _logger.warning(
#                             "Could not unlink some courier-like request lines for request %s",
#                             rec.name
#                         )
#
#             # Ensure exactly one courier line (if not Cserve)
#             if courier and (courier.name or '').strip().lower() != 'cserve':
#
#                 courier_prod = _find_courier_product(courier)
#                 if not courier_prod:
#                     raise ValidationError(
#                         _("Courier '%s' must have a configured courier product (e.g. DHL_AWBN or UPS_AWBN).")
#                         % (courier.name or '')
#                     )
#
#                 existing_line = rec.line_ids.filtered(
#                     lambda l: l.product_id and l.product_id.id == courier_prod.id
#                 )
#
#                 if not existing_line:
#                     line_vals = {
#                         'request_id': rec.id,
#                         'product_id': courier_prod.id,
#                         'unit_price': (
#                             courier_prod.lst_price
#                             if hasattr(courier_prod, 'lst_price') and courier_prod.lst_price is not None
#                             else courier_prod.list_price if hasattr(courier_prod, 'list_price') else 0.0
#                         ),
#                         # 'quantity': 1,  # add back if your model requires quantity
#                     }
#
#                     try:
#                         self.env['codeware.request.line'].create(line_vals)
#                     except Exception as e:
#                         raise ValidationError(
#                             _("Failed to create courier request line for %s: %s") % (rec.name, e)
#                         )
#
#             else:
#                 # Courier is Cserve or empty: remove all courier-like lines
#                 if rec.line_ids:
#                     to_unlink = rec.line_ids.filtered(_is_courier_like)
#                     if to_unlink:
#                         try:
#                             to_unlink.unlink()
#                         except Exception:
#                             pass
#
#             # ----------------------------
#             # Create request.order
#             # ----------------------------
#             if not rec.request_order_id:
#                 ro_vals = {
#                     'request_id': rec.id,
#                     'sender_name': rec.sender_name,
#                     'sender_address': rec.sender_address,
#                     'customer_name': rec.customer_name,
#                     'customer_address': rec.customer_address,
#                     'state': 'confirmed',
#                 }
#                 ro = self.env['codeware.request.order'].create(ro_vals)
#                 rec.request_order_id = ro.id
#             else:
#                 rec.request_order_id.sudo().write({'state': 'confirmed'})
#
#             # ----------------------------
#             # Create Sale Order (quotation)
#             # ----------------------------
#             partner = rec.partner_id
#             if not partner:
#                 raise ValidationError("Customer is missing — cannot create Sale Order.")
#
#             sale_vals = {
#                 'partner_id': partner.id,
#                 'origin': rec.name,
#                 'request_id': rec.id,
#                 'delivery_hub_id': rec.source_hub_id.id,
#                 'fincode_id': rec.dest_fincode_id.id,
#             }
#
#             sale = self.env['sale.order'].create(sale_vals)
#
#             # Assign serviced_by to pickings
#             for pick in sale.picking_ids:
#                 pick.picking_serviced_by_id = rec.serviced_by_id.id
#
#             # Create sale lines
#             for line in rec.line_ids:
#                 self.env['sale.order.line'].create({
#                     'order_id': sale.id,
#                     'product_id': line.product_id.id,
#                     'name': line.product_id.name,
#                     'product_uom_qty': 1,
#                     'price_unit': line.unit_price,
#                     'request_line_id': line.id,
#                 })
#
#             # Link Sale Order back to request
#             try:
#                 sale.write({'request_id': rec.id})
#             except Exception:
#                 pass
#
#             rec.sale_id = sale.id
#             rec.state = 'confirmed'
#
#             try:
#                 rec.message_post(body=_("Request confirmed."))
#             except Exception:
#                 pass
#
#         return True
#
#     def _get_service_product(self):
#         product = self.env['product.product'].search([('default_code', '=', 'REQUEST_SERVICE')], limit=1)
#         if not product:
#             product = self.env['product.product'].create({
#                 'name': 'Request Service Charge',
#                 'default_code': 'REQUEST_SERVICE',
#                 'type': 'service',
#                 'invoice_policy': 'order',
#                 'sale_ok': True,
#             })
#         return product
#
#     # -------------------------
#     def action_create_payment(self, amount=None, journal_id=None):
#         """
#         Create & POST a payment immediately and open its form view.
#         """
#         self.ensure_one()
#
#         if not self.partner_id:
#             raise ValidationError(_("Please set a Customer before creating a payment."))
#
#         amt = amount if amount is not None else (getattr(self, 'amount_total', 0.0) or 0.0)
#         if float(amt) <= 0:
#             raise ValidationError(_("Payment amount must be positive."))
#
#         journal = None
#         if journal_id:
#             journal = self.env['account.journal'].browse(journal_id)
#         else:
#             journal = self.env['account.journal'].search(
#                 [('type', 'in', ['bank', 'cash']), ('company_id', '=', self.env.company.id)],
#                 limit=1)
#         if not journal:
#             raise ValidationError(_("No bank or cash journal found. Please configure one."))
#
#         company_id = None
#         try:
#             if hasattr(self, 'company_id') and getattr(self, 'company_id'):
#                 company_id = self.company_id.id
#         except Exception:
#             company_id = None
#         if not company_id:
#             company_id = self.env.company.id
#
#         candidate_vals = {
#             'payment_type': 'inbound',
#             'partner_type': 'customer',
#             'partner_id': self.partner_id.id,
#             'amount': float(amt),
#             'journal_id': journal.id,
#             'company_id': company_id,
#             'communication': 'REQ/%s' % (getattr(self, 'name', '')),
#             'payment_reference': _('Payment for %s') % (getattr(self, 'name', self.partner_id.name)),
#         }
#
#         try:
#             pm = self.env.ref('account.account_payment_method_manual_in', raise_if_not_found=False)
#             if pm:
#                 candidate_vals['payment_method_id'] = pm.id
#         except Exception:
#             pass
#
#         Payment = self.env['account.payment'].sudo()
#         allowed_fields = set(Payment._fields.keys())
#         safe_vals = {k: v for k, v in candidate_vals.items() if k in allowed_fields}
#
#         try:
#             payment = Payment.create(safe_vals)
#         except Exception as e:
#             _logger.exception("Failed to create payment for request %s: %s", getattr(self, 'id', False), e)
#             raise UserError(_("Failed to create payment: %s") % e)
#
#         try:
#             if hasattr(payment, 'action_post'):
#                 payment.action_post()
#             else:
#                 payment.post()
#         except Exception as e:
#             _logger.exception("Failed to post payment %s for request %s: %s", getattr(payment, 'id', False),
#                               getattr(self, 'id', False), e)
#             raise UserError(_("Payment was created but posting failed: %s") % e)
#
#         try:
#             if 'codeware_request_id' in payment._fields:
#                 payment.sudo().write({'codeware_request_id': self.id})
#         except Exception:
#             _logger.exception("Failed writing codeware_request_id on payment %s", getattr(payment, 'id', False))
#
#         try:
#             to_write = {}
#             if 'payment_ids' in self._fields:
#                 to_write['payment_ids'] = [(4, payment.id)]
#             if 'primary_payment_id' in self._fields:
#                 to_write['primary_payment_id'] = payment.id
#             if to_write:
#                 self.sudo().write(to_write)
#         except Exception:
#             _logger.exception("Failed to link payment %s to request %s", getattr(payment, 'id', False),
#                               getattr(self, 'id', False))
#
#         return {
#             'name': _('Payment'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'account.payment',
#             'view_mode': 'form',
#             'res_id': payment.id,
#             'target': 'current',
#         }
#
#     # -------------------------
#     def _reconcile_payment_with_invoice(self, invoice):
#         self.ensure_one()
#         if not invoice or invoice.state != 'posted':
#             return False
#
#         reconciled_any = False
#
#         posted_payments = self.payment_ids.filtered(lambda p: p.state in ('posted', 'reconciled'))
#         if not posted_payments:
#             post_domain = [('state', 'in', ('posted', 'reconciled')), ('partner_id', '=', self.partner_id.id)]
#             if hasattr(self.env['account.payment'], 'codeware_request_id'):
#                 post_domain.append(('codeware_request_id', '=', self.id))
#             posted_payments = self.env['account.payment'].search(post_domain)
#
#         inv_receivable_lines = invoice.line_ids.filtered(lambda l: l.account_id.user_type_id.type == 'receivable')
#
#         if not posted_payments or not inv_receivable_lines:
#             return False
#
#         for pay in posted_payments:
#             try:
#                 payment_move_lines = self.env['account.move.line']
#                 if hasattr(pay, 'move_id') and pay.move_id:
#                     payment_move_lines = pay.move_id.line_ids.filtered(
#                         lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
#                 elif hasattr(pay, 'line_ids'):
#                     payment_move_lines = pay.line_ids.filtered(
#                         lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
#             except Exception:
#                 _logger.exception("Error finding move lines for payment %s", pay.id)
#                 continue
#
#             for inv_line in inv_receivable_lines:
#                 candidates = payment_move_lines.filtered(
#                     lambda l: l.account_id == inv_line.account_id and l.partner_id == inv_line.partner_id)
#                 if not candidates:
#                     candidates = payment_move_lines.filtered(lambda l: l.partner_id == inv_line.partner_id)
#
#                 if not candidates:
#                     continue
#
#                 lines_to_reconcile = candidates | inv_line
#                 try:
#                     if hasattr(lines_to_reconcile, 'reconcile'):
#                         lines_to_reconcile.reconcile()
#                         reconciled_any = True
#                     else:
#                         first_candidate = candidates[:1]
#                         if first_candidate and hasattr(first_candidate, 'reconcile'):
#                             (first_candidate | inv_line).reconcile()
#                             reconciled_any = True
#                 except Exception:
#                     _logger.exception("Failed to reconcile invoice %s line %s with payment %s", invoice.id, inv_line.id,
#                                       pay.id)
#                     continue
#
#         return reconciled_any
#
#     # -------------------------
#     def action_view_request_order(self):
#         self.ensure_one()
#         if not self.request_order_id:
#             return {
#                 'name': 'Request Orders',
#                 'type': 'ir.actions.act_window',
#                 'res_model': 'codeware.request.order',
#                 'view_mode': 'list,form',
#                 'domain': [('request_id', '=', self.id)],
#                 'target': 'current',
#             }
#         return {
#             'type': 'ir.actions.act_window',
#             'name': 'Request Order',
#             'res_model': 'codeware.request.order',
#             'view_mode': 'form',
#             'res_id': self.request_order_id.id,
#             'target': 'current',
#         }
#
#     def action_print_request(self):
#         self.ensure_one()
#         return self.env.ref('courier_management_final.action_report_request_order_v2').report_action(self)
#
#     # -------------------------
#     @api.model_create_multi
#     def create(self, vals_list):
#         records = super().create(vals_list)
#         for rec in records:
#             try:
#                 if rec.dest_fincode_id or rec.zip_input:
#                     rec.apply_fincode_to_request()
#             except Exception:
#                 _logger.exception("Error applying fincode on create for request %s", rec.id)
#         return records
#
#     def write(self, vals):
#         _logger.debug("codeware.request: incoming write on ids=%s vals=%s", self.ids, vals)
#         skip_apply = bool(self.env.context.get('_skip_apply_fincode', False))
#
#         res = super().write(vals)
#
#         if not skip_apply:
#             try:
#                 apply_needed = False
#                 if 'dest_fincode_id' in vals or 'zip_input' in vals:
#                     apply_needed = True
#                 for rec in self:
#                     if apply_needed or rec.dest_fincode_id:
#                         rec.with_context(_skip_apply_fincode=True).apply_fincode_to_request()
#             except Exception:
#                 _logger.exception("Error post-write applying fincode for requests %s", self.ids)
#         return res
#
#     @api.constrains('zip_input')
#     def _check_zip_input(self):
#         for rec in self:
#             if rec.zip_input and not (rec.zip_input.isdigit() and len(rec.zip_input) == 6):
#                 raise ValidationError(_("ZIP must be exactly 6 digits."))
#
#     @api.constrains('dest_zip')
#     def _check_dest_zip(self):
#         for rec in self:
#             if rec.dest_zip and not (rec.dest_zip.isdigit() and len(rec.dest_zip) == 6):
#                 raise ValidationError(_("Destination ZIP must be exactly 6 digits."))
#
#     # -------------------------
#     def action_open_sale_order(self):
#         self.ensure_one()
#         if not self.sale_id:
#             return {'type': 'ir.actions.act_window_close'}
#         return {
#             'name': _('Sale Order'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'sale.order',
#             'res_id': self.sale_id.id,
#             'view_mode': 'form',
#             'target': 'current',
#         }
#
#     def action_open_payments(self):
#         self.ensure_one()
#         Payment = self.env['account.payment']
#         payments = self.payment_ids
#         if not payments:
#             comm = 'REQ/%s' % (getattr(self, 'name', ''))
#             payments = Payment.search([('communication', '=', comm), ('partner_id', '=', self.partner_id.id)])
#         if not payments:
#             return {'type': 'ir.actions.act_window_close'}
#         if len(payments) == 1:
#             payment = payments[0]
#             return {
#                 'name': _('Payment'),
#                 'type': 'ir.actions.act_window',
#                 'res_model': 'account.payment',
#                 'res_id': payment.id,
#                 'view_mode': 'form',
#                 'target': 'current',
#             }
#         return {
#             'name': _('Payments'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'account.payment',
#             'domain': [('id', 'in', payments.ids)],
#             'view_mode': 'tree,form',
#             'target': 'current',
#         }
#
#     @api.depends('payment_ids.state')
#     def _compute_is_fully_paid(self):
#         for rec in self:
#             paid = False
#             for p in rec.payment_ids:
#                 if p.state in ('posted', 'reconciled', 'paid'):
#                     paid = True
#                     break
#             rec.is_fully_paid = paid
#
#     # -------------------------
#     def _default_source_hub(self):
#         return self.env['codeware.transithub'].search([('name', '=', 'Calabar Hub')], limit=1).id
#
#     # -------------------------
#     @api.onchange('partner_id')
#     def _onchange_partner_id(self):
#         for rec in self:
#             p = rec.partner_id
#             if not p:
#                 return
#
#             # Always fill name
#             rec.sender_name = p.name
#
#             # Always fill PHONE correctly (THIS FIXES YOUR ISSUE)
#             rec.sender_phone = _get_partner_phone(p)
#
#             # Always fill address
#             rec.sender_address = (
#                 f"{p.street or ''}\n"
#                 f"{p.city or ''}\n"
#                 f"{(p.state_id.name if p.state_id else '')}\n"
#                 f"{p.zip or ''}"
#             )
#
#             # Also reflect partner_id into the helper dropdown
#             rec.sender_phone_partner = p
#
#     @api.onchange('receiver_id')
#     def _onchange_receiver_id(self):
#         for rec in self:
#             if rec.receiver_id:
#                 rec.customer_name = rec.receiver_id.name
#                 rec.receiver_phone = _get_partner_phone(rec.receiver_id)
#                 rec.customer_address = (
#                     f"{rec.receiver_id.street or ''}\n"
#                     f"{rec.receiver_id.city or ''}\n"
#                     f"{(rec.receiver_id.state_id.name if rec.receiver_id.state_id else '')}\n"
#                     f"{rec.receiver_id.zip or ''}"
#                 )
#                 rec.receiver_phone_partner = rec.receiver_id
#
#     @api.onchange('receiver_phone')
#     def _onchange_receiver_phone(self):
#         for rec in self:
#             if not rec.receiver_phone:
#                 continue
#             Partner = self.env['res.partner']
#             # Prefer exact matches on phone and mobile (mobile checked safely)
#             domain = [('phone', '=', rec.receiver_phone)]
#             if 'mobile' in Partner._fields:
#                 domain = ['|', ('phone', '=', rec.receiver_phone), ('mobile', '=', rec.receiver_phone)]
#             partner = Partner.search(domain, limit=1)
#             if partner:
#                 rec.receiver_id = partner
#                 rec.customer_name = partner.name
#                 rec.customer_address = (
#                     f"{partner.street or ''}\n"
#                     f"{partner.city or ''}\n"
#                     f"{(partner.state_id.name if partner.state_id else '')}\n"
#                     f"{partner.zip or ''}"
#                 )
#                 rec.receiver_phone_partner = partner
#
#     # -------------------------
#     # Transient helper onchanges for phone dropdowns (no DB change)
#     @api.onchange('sender_phone_partner')
#     def _onchange_sender_phone_partner(self):
#         for rec in self:
#             p = rec.sender_phone_partner
#             if p:
#                 rec.partner_id = p
#                 rec.sender_phone = _get_partner_phone(p)
#                 rec.sender_address = (
#                     f"{p.street or ''}\n"
#                     f"{p.city or ''}\n"
#                     f"{(p.state_id.name if p.state_id else '')}\n"
#                     f"{p.zip or ''}"
#                 )
#
#     @api.onchange('receiver_phone_partner')
#     def _onchange_receiver_phone_partner(self):
#         for rec in self:
#             p = rec.receiver_phone_partner
#             if p:
#                 rec.receiver_id = p
#                 rec.receiver_phone = _get_partner_phone(p)
#                 rec.customer_name = p.name
#                 rec.customer_address = (
#                     f"{p.street or ''}\n"
#                     f"{p.city or ''}\n"
#                     f"{(p.state_id.name if p.state_id else '')}\n"
#                     f"{p.zip or ''}"
#                 )
#
#     # ---------- Fincode persistence helpers ----------
#     def _copy_fincode_fields_to_vals(self, fincode):
#         """Build vals using FINCODE_TO_REQUEST_MAP first, then copy same-named compatible fields."""
#         if not fincode or not fincode.exists():
#             return {}
#         vals = {}
#         ignore_names = {'id', 'create_uid', 'create_date', 'write_uid', 'write_date', 'display_name'}
#         supported_types = {
#             'char', 'text', 'integer', 'float', 'boolean',
#             'selection', 'date', 'datetime', 'many2one', 'many2many'
#         }
#
#         for fin_name, map_info in getattr(self, 'FINCODE_TO_REQUEST_MAP', {}).items():
#             try:
#                 target_field = map_info[0] if isinstance(map_info, (list, tuple)) else map_info
#             except Exception:
#                 target_field = map_info
#             if not target_field or target_field not in self._fields:
#                 _logger.debug("Fincode mapping: target field %s not present on request model; skipping", target_field)
#                 continue
#             if fin_name not in fincode._fields:
#                 _logger.debug("Fincode mapping: source field %s not present on fincode; skipping", fin_name)
#                 continue
#
#             fmeta = fincode._fields[fin_name]
#             ftype = fmeta.type
#             if ftype not in supported_types:
#                 _logger.debug("Fincode mapping: unsupported type %s for field %s; skipping", ftype, fin_name)
#                 continue
#
#             try:
#                 if ftype in ('char', 'text', 'selection', 'date', 'datetime', 'integer', 'float', 'boolean'):
#                     vals[target_field] = getattr(fincode, fin_name) or False
#                 elif ftype == 'many2one':
#                     rel = getattr(fincode, fin_name)
#                     vals[target_field] = rel.id if rel else False
#                 elif ftype == 'many2many':
#                     relset = getattr(fincode, fin_name)
#                     ids = relset.ids if relset else []
#                     vals[target_field] = [(6, 0, ids)]
#                 _logger.debug("Mapped fin.%s -> req.%s = %s", fin_name, target_field, vals.get(target_field))
#             except Exception:
#                 _logger.exception("Failed to map fin.%s -> req.%s", fin_name, target_field)
#
#         for fname, fmeta in fincode._fields.items():
#             if fname in ignore_names:
#                 continue
#             if fname in getattr(self, 'FINCODE_TO_REQUEST_MAP', {}):
#                 continue
#             if fname not in self._fields:
#                 continue
#             if fname in vals:
#                 continue
#             ftype = fmeta.type
#             if ftype not in supported_types:
#                 continue
#             try:
#                 if ftype in ('char', 'text', 'selection', 'date', 'datetime', 'integer', 'float', 'boolean'):
#                     vals[fname] = getattr(fincode, fname) or False
#                 elif ftype == 'many2one':
#                     rel = getattr(fincode, fname)
#                     vals[fname] = rel.id if rel else False
#                 elif ftype == 'many2many':
#                     relset = getattr(fincode, fname)
#                     ids = relset.ids if relset else []
#                     vals[fname] = [(6, 0, ids)]
#                 _logger.debug("Copied fin.%s -> req.%s = %s", fname, fname, vals.get(fname))
#             except Exception:
#                 _logger.exception("Failed to copy field %s from fincode %s", fname, getattr(fincode, 'id', False))
#         return vals
#
#     def apply_fincode_to_request(self, fincode=None):
#         for rec in self:
#             fin = None
#             if fincode:
#                 try:
#                     if isinstance(fincode, int):
#                         fin = self.env['codeware.fincode'].browse(int(fincode))
#                     else:
#                         fin = fincode
#                 except Exception:
#                     fin = None
#
#             if not fin and getattr(rec, 'dest_fincode_id', False):
#                 fin = rec.dest_fincode_id
#             if not fin:
#                 zip_val = getattr(rec, 'zip_input', False) or getattr(rec, 'dest_zip', False) or False
#                 if zip_val:
#                     fin = self.env['codeware.fincode'].search([('name', '=', zip_val)], limit=1)
#
#             if not fin or not fin.exists():
#                 _logger.debug("apply_fincode_to_request: no fincode for request %s (zip=%s, dest_fincode=%s)", rec.id,
#                               getattr(rec, 'zip_input', False), getattr(rec, 'dest_fincode_id', False))
#                 continue
#
#             vals = rec._copy_fincode_fields_to_vals(fin)
#             if 'dest_fincode_id' in rec._fields and fin.id:
#                 vals['dest_fincode_id'] = fin.id
#
#             if not vals:
#                 _logger.debug("apply_fincode_to_request: no vals built for request %s from fincode %s", rec.id, fin.id)
#                 continue
#
#             try:
#                 rec.with_context(_skip_apply_fincode=True).sudo().write(vals)
#                 _logger.info("apply_fincode_to_request: wrote fields %s to request %s from fincode %s",
#                              list(vals.keys()), rec.id, fin.id)
#             except Exception:
#                 _logger.exception("apply_fincode_to_request: failed to write vals for request %s from fincode %s",
#                                   rec.id, fin.id)
#         return True
#
#     # PRICING RULE
#     @api.depends('weight', 'distance', 'priority_type')
#     def _compute_amounts(self):
#         Weight = self.env['codeware.weight.pricelist']
#         Distance = self.env['codeware.distance.pricelist']
#         Priority = self.env['codeware.priority.pricelist']
#
#         for rec in self:
#             rec.weight_cost = 0.0
#             rec.distance_cost = 0.0
#             rec.priority_cost = 0.0
#             rec.subtotal = 0.0
#
#             # -- WEIGHT --
#             if rec.weight is not None:
#                 try:
#                     w = float(rec.weight)
#                 except Exception:
#                     w = None
#                 if w is not None:
#                     w_domain = [
#                         ('min_weight', '<=', w),
#                         ('max_weight', '>=', w),
#                         ('status', '=', 'active')
#                     ]
#                     w_rec = Weight.search(w_domain, limit=1, order='min_weight asc')
#                     if w_rec:
#                         rec.weight_cost = w_rec.cost
#                     else:
#                         _logger.debug("No weight pricelist match for weight=%s (domain=%s)", w, w_domain)
#
#             # -- DISTANCE --
#             if rec.distance is not None:
#                 try:
#                     d = float(rec.distance)
#                 except Exception:
#                     d = None
#                 if d is not None:
#                     d_domain = [
#                         ('min_distance', '<=', d),
#                         ('max_distance', '>=', d),
#                         ('status', '=', 'active')
#                     ]
#                     d_rec = Distance.search(d_domain, limit=1, order='min_distance asc')
#                     if d_rec:
#                         rec.distance_cost = d_rec.cost
#                     else:
#                         _logger.debug("No distance pricelist match for distance=%s (domain=%s)", d, d_domain)
#
#             # -- PRIORITY --
#             if rec.priority_type:
#                 p_domain = [
#                     ('priority_type', '=', rec.priority_type),
#                     ('status', '=', 'active')
#                 ]
#                 p_rec = Priority.search(p_domain, limit=1)
#                 if p_rec:
#                     rec.priority_cost = p_rec.cost
#                 else:
#                     _logger.debug("No priority pricelist match for priority=%s", rec.priority_type)
#
#             # -- SUBTOTAL --
#             rec.subtotal = (rec.weight_cost or 0.0) + (rec.distance_cost or 0.0) + (rec.priority_cost or 0.0)
#             _logger.debug(
#                 "Computed costs for request %s: weight=%s cost=%s, distance=%s cost=%s, priority=%s cost=%s, subtotal=%s",
#                 rec.id, rec.weight, rec.weight_cost, rec.distance, rec.distance_cost, rec.priority_type,
#                 rec.priority_cost, rec.subtotal)
#
#     @api.depends('line_ids.price_subtotal', 'base_price', 'subtotal')
#     def _compute_total(self):
#         for rec in self:
#             base = rec.base_price or 0.0
#             lines_total = sum(rec.line_ids.mapped('price_subtotal')) if rec.line_ids else 0.0
#             rec.amount_total = base + (rec.subtotal or 0.0) + lines_total