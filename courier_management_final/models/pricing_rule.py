
from odoo import models, fields, api, _

class PricingRule(models.Model):
    _name = 'codeware.pricing.rule'
    _description = 'Pricing Rule'

    name = fields.Char(string='Name', required=True)
    priority_type = fields.Selection([
        ('Standard', 'Standard'),
        ('express', 'Express'),
        # ('urgent', 'Urgent'),
    ], string='Priority', default='Standard')
    min_weight = fields.Float(string='Min Weight (kg)', required=True)
    max_weight = fields.Float(string='Max Weight (kg)', required=True)
    price_per_kg = fields.Float(string='Price per Kg', required=True)
    discount_percent = fields.Float(string='Discount (%)')
    active = fields.Boolean(string='Active', default=True)


class PriorityPricelist(models.Model):
    _name = 'codeware.priority.pricelist'
    _description = 'Priority Pricelist'

    rules = fields.Text(string='Rules')
    priority_type = fields.Selection([
        ('Standard', 'Standard'),
        ('express', 'Express'),
        # ('urgent', 'Urgent')
    ], string='Priority Type', required=True)
    # priority = fields.Selection([
    #     ('normal', 'Normal'),
    #     ('express', 'Express'),
    #     ('urgent', 'Urgent'),
    # ], string='Priority', default='normal')
    cost = fields.Float(string='Cost', required=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='active')


class DistancePricelist(models.Model):
    _name = 'codeware.distance.pricelist'
    _description = 'Distance Pricelist'

    name = fields.Char(string='Name', required=True)
    min_distance = fields.Float(string='Min Distance (km)', required=True)
    max_distance = fields.Float(string='Max Distance (km)', required=True)
    cost = fields.Float(string='Cost', required=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='active')


class WeightPricelist(models.Model):
    _name = 'codeware.weight.pricelist'
    _description = 'Weight Pricelist'

    name = fields.Char(string='Name', required=True)
    min_weight = fields.Integer(string='Min Weight (kg)', required=True)
    max_weight = fields.Integer(string='Max Weight (kg)', required=True)
    cost = fields.Float(string='Cost', required=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='active')
