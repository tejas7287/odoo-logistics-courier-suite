# models/request_line.py
# Ready-to-replace file: CodewareRequestLine
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CodewareRequestLine(models.Model):
    _name = 'codeware.request.line'
    _description = 'Request - Price Line'

    request_id = fields.Many2one('codeware.request', string='Request', ondelete='cascade', required=True)
    # product_desc = fields.Char(string='Description')
    product_id = fields.Many2one(
        'product.product',
        domain=[('sale_ok', '=', True),('product_tmpl_id.is_published', '=', False),],
        string='Product',
        required=False
    )
    weight = fields.Float(string='Weight (kg)', default=0.0)
    distance_km = fields.Float(string='Distance (km)', default=0.0)
    # keep values aligned with your view: 'normal' / 'high' (existing)
    # priority = fields.Selection([('normal', 'Normal'), ('high', 'High')], string='Priority', default='normal')
    priority = fields.Selection([
        ('Standard', 'Standard'),
        ('express', 'Express'),
        # ('urgent', 'Urgent')
    ], string="Priority Type")

    price_rule_id = fields.Many2one('codeware.pricing.rule', string='Price Rule')
    unit_price = fields.Float(string='Unit Price', default=0.0)
    price_subtotal = fields.Float(string='Total', compute='_compute_subtotal', store=True)

    is_cod = fields.Boolean(string='COD')

    cod_amount = fields.Float(string='COD Amount')

    # computed breakdown fields (stored so UI shows quickly)
    weight_cost = fields.Float(string="Weight Cost", compute="_compute_amounts", store=True)
    distance_cost = fields.Float(string="Distance Cost", compute="_compute_amounts", store=True)
    priority_cost = fields.Float(string="Priority Cost", compute="_compute_amounts", store=True)
    courier_company_id = fields.Many2one(
        "codeware.courier.company",
        string="Courier Company"
    )
    is_courier_hidden = fields.Boolean(string="Hidden Courier Line", compute="_compute_is_courier_hidden", store=True)

    @api.depends('product_id')
    def _compute_is_courier_hidden(self):
        for rl in self:
            courier_company = self.env['codeware.courier.company'].search([
                ('courier_product_id', '=', rl.product_id.id)
            ], limit=1)

            rl.is_courier_hidden = bool(courier_company and not courier_company.internal)

    @api.depends('unit_price', 'weight', 'distance_km', 'is_cod',
                 'request_id.base_price', 'request_id.serviced_by_id', 'product_id')
    def _compute_subtotal(self):
        """
        Line-level subtotal compute.

        Behaviour:
        - If the line's product matches the courier product configured on the parent request's serviced_by_id,
          the line subtotal is forced to 0.0 (and COD amount is zero).
        - Otherwise, keep the existing behaviour (base + unit).
        """
        for rec in self:
            # Defensive defaults
            rec.cod_amount = 0.0
            rec.price_subtotal = 0.0

            # gather basic values
            base = (rec.request_id.base_price or 0.0) if rec.request_id else 0.0
            unit = rec.unit_price or 0.0

            # Try to detect courier product configured on the parent request (if any)
            courier_prod = False
            try:
                if rec.request_id and rec.request_id.serviced_by_id:
                    courier_prod = getattr(rec.request_id.serviced_by_id, 'courier_product_id', False)
            except Exception:
                courier_prod = False

            # If this line is the courier-mapped product -> force subtotal = 0
            if courier_prod and rec.product_id and rec.product_id.id == courier_prod.id:
                rec.price_subtotal = 0.0
                rec.cod_amount = 0.0 if not rec.is_cod else 0.0
                # done for this line
                continue

            # Default behaviour for non-courier lines: base + unit (preserve existing behaviour)
            rec.price_subtotal = base + unit
            rec.cod_amount = rec.price_subtotal if rec.is_cod else 0.0

    @api.onchange('is_cod')
    def _onchange_is_cod(self):
        for rec in self:
            rec.cod_amount = rec.price_subtotal if rec.is_cod else 0.0

    # --- Core compute that finds pricelist entries and applies them safely ---
    @api.depends('weight', 'distance_km', 'priority')
    def _compute_amounts(self):
        """
        Compute weight_cost, distance_cost, priority_cost.
        Determine best price_rule (if any) and set unit_price accordingly.
        Safe against missing fields on pricelist models.
        """
        WeightPL = self.env['codeware.weight.pricelist']
        DistancePL = self.env['codeware.distance.pricelist']
        PriorityPL = self.env['codeware.priority.pricelist']
        PricingRule = self.env['codeware.pricing.rule']

        # candidate field names we might match on for priority pricelist (defensive)
        priority_candidates = ['priority', 'priority_type', 'type', 'code', 'name']

        for rec in self:
            rec.weight_cost = 0.0
            rec.distance_cost = 0.0
            rec.priority_cost = 0.0
            rec.unit_price = rec.unit_price or 0.0
            rec.price_rule_id = rec.price_rule_id or False

            # --- WEIGHT lookup ---
            try:
                w = float(rec.weight) if rec.weight is not None else None
            except Exception:
                w = None
            if w is not None:
                w_domain = [
                    ('min_weight', '<=', w),
                    ('max_weight', '>=', w),
                    ('status', '=', 'active')
                ]
                try:
                    w_rec = WeightPL.search(w_domain, limit=1, order='min_weight asc')
                    if w_rec:
                        # prefer 'cost' field as shown in your views
                        rec.weight_cost = getattr(w_rec, 'cost', 0.0) or 0.0
                except Exception:
                    _logger.exception("weight pricelist lookup failed for weight=%s", w)

            # --- DISTANCE lookup ---
            try:
                d = float(rec.distance_km) if rec.distance_km is not None else None
            except Exception:
                d = None
            if d is not None:
                d_domain = [
                    ('min_distance', '<=', d),
                    ('max_distance', '>=', d),
                    ('status', '=', 'active')
                ]
                try:
                    d_rec = DistancePL.search(d_domain, limit=1, order='min_distance asc')
                    if d_rec:
                        rec.distance_cost = getattr(d_rec, 'cost', 0.0) or 0.0
                except Exception:
                    _logger.exception("distance pricelist lookup failed for distance=%s", d)

            # --- PRIORITY lookup (defensive about unknown field names) ---
            p_value = rec.priority or False
            if p_value:
                p_rec = False
                # try known candidates
                for fld in priority_candidates:
                    if fld in PriorityPL._fields:
                        try:
                            p_rec = PriorityPL.search([(fld, '=', p_value), ('status', '=', 'active')], limit=1)
                        except Exception:
                            p_rec = False
                        if p_rec:
                            break
                # fallback to matching by 'name' if nothing else found
                if not p_rec and 'name' in PriorityPL._fields:
                    try:
                        p_rec = PriorityPL.search([('name', '=', p_value), ('status', '=', 'active')], limit=1)
                    except Exception:
                        p_rec = False

                if p_rec:
                    rec.priority_cost = getattr(p_rec, 'cost', 0.0) or 0.0

            # --- Try to find a matching Pricing Rule (optional) ---
            # Pricing rule model (codeware.pricing.rule) view shows fields:
            # priority_type, min_weight, max_weight, price_per_kg, discount_percent
            # We'll try to match priority_type and weight ranges. This is optional;
            # if a rule is found we will compute unit_price using that rule.
            try:
                rule_domain = [('status', '=', 'active')]
                # match priority_type if present on rule model
                if 'priority_type' in PricingRule._fields and p_value:
                    # map 'priority' (line) to 'priority_type' expected by rule
                    rule_domain.append(('priority_type', '=', p_value))
                # weight matching if rule model has min/max
                if w is not None and ('min_weight' in PricingRule._fields and 'max_weight' in PricingRule._fields):
                    rule_domain.append(('min_weight', '<=', w))
                    rule_domain.append(('max_weight', '>=', w))
                # search for the best rule
                matched_rule = PricingRule.search(rule_domain, limit=1, order='min_weight asc')
                if matched_rule:
                    # attach rule to line
                    rec.price_rule_id = matched_rule
                    # compute unit_price based on rule fields if available
                    # common pattern: unit_price = price_per_kg * weight  (or price_per_kg + other costs)
                    price_from_rule = 0.0
                    if 'price_per_kg' in matched_rule._fields and rec.weight:
                        price_per_kg = getattr(matched_rule, 'price_per_kg', 0.0) or 0.0
                        price_from_rule += price_per_kg * (rec.weight or 0.0)
                    # if rule offers a flat 'price' or 'cost' fallback
                    if (not price_from_rule) and 'price' in matched_rule._fields:
                        price_from_rule = getattr(matched_rule, 'price', 0.0) or 0.0
                    if (not price_from_rule) and 'cost' in matched_rule._fields:
                        price_from_rule = getattr(matched_rule, 'cost', 0.0) or 0.0
                    # allow discount_percent field influence (if present)
                    if 'discount_percent' in matched_rule._fields and getattr(matched_rule, 'discount_percent', False):
                        try:
                            disc = float(getattr(matched_rule, 'discount_percent', 0.0) or 0.0)
                            price_from_rule = price_from_rule * (1.0 - (disc / 100.0))
                        except Exception:
                            pass
                    # final fallback: sum of computed components
                    if not price_from_rule:
                        price_from_rule = (rec.weight_cost or 0.0) + (rec.distance_cost or 0.0) + (
                                    rec.priority_cost or 0.0)
                    rec.unit_price = price_from_rule
                else:
                    # no pricing rule matched — fall back to sum of components
                    rec.price_rule_id = False
                    rec.unit_price = (rec.weight_cost or 0.0) + (rec.distance_cost or 0.0) + (rec.priority_cost or 0.0)
            except Exception:
                # defensive fallback if pricing rule model or fields differ unexpectedly
                _logger.exception("pricing rule search failed for line (req=%s)",
                                  rec.request_id.id if rec.request_id else False)
                rec.price_rule_id = False
                rec.unit_price = (rec.weight_cost or 0.0) + (rec.distance_cost or 0.0) + (rec.priority_cost or 0.0)

            # ensure float values (avoid None)
            rec.unit_price = float(rec.unit_price or 0.0)
            rec.weight_cost = float(rec.weight_cost or 0.0)
            rec.distance_cost = float(rec.distance_cost or 0.0)
            rec.priority_cost = float(rec.priority_cost or 0.0)


