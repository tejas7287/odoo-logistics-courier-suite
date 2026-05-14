# models/courier_company.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CourierCompany(models.Model):
    _name = 'codeware.courier.company'
    _description = 'Third-party Courier Company / Service Provider'
    _rec_name = 'name'
    _order = 'name'

    # <-- add these mixins so the model provides mail.thread methods -->
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, index=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact (Partner)',
        ondelete='set null',
        help='Link to partner record. You can create/select a partner from the dropdown.'
    )
    contact_person = fields.Char(string='Contact Person')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    address = fields.Text(string='Address')
    notes = fields.Text(string='Notes')
    active = fields.Boolean(string='Active', default=True)
    internal = fields.Boolean(string="Internal", default=False)

    courier_product_id = fields.Many2one(
        'product.product',
        string='Courier Product',
        domain="[('tracking', 'in', ('lot','serial'))]",
        help="Product to use for this courier (e.g. DHL_AWBN, UPS_AWBN). "
             "Should be serial-tracked so the system can consume an existing lot."
    )



    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Courier Company with this name already exists.'),
    ]

    @api.onchange('partner_id')
    def _onchange_partner_id_fill_fields(self):
        """
        When partner selected:
         - if name is empty or identical to partner name, set courier name to partner name
         - copy phone (mobile or phone), email, and full address to courier fields
         - set contact_person from partner.name if appropriate
        """
        for rec in self:
            p = rec.partner_id
            if not p:
                # nothing to fill
                continue

            # Set name if blank or same as partner name
            if not rec.name or rec.name.strip() == (getattr(p, 'name', '') or '').strip():
                rec.name = getattr(p, 'name', rec.name)

            # Contact person
            rec.contact_person = getattr(p, 'name', rec.contact_person)

            # Prefer mobile then phone (safe getattr usage)
            rec.phone = getattr(p, 'mobile', None) or getattr(p, 'phone', None) or rec.phone

            # Email (safe)
            rec.email = getattr(p, 'email', None) or rec.email

            # Build an address text (street, street2, city, state, zip, country)
            parts = []
            street = getattr(p, 'street', None)
            street2 = getattr(p, 'street2', None)
            if street:
                parts.append(street)
            if street2:
                parts.append(street2)
            city = getattr(p, 'city', None)
            state = getattr(getattr(p, 'state_id', None), 'name', None)
            zip_code = getattr(p, 'zip', None)
            line2 = ', '.join(filter(None, [city, state, zip_code]))
            if line2:
                parts.append(line2)
            country = getattr(getattr(p, 'country_id', None), 'name', None)
            if country:
                parts.append(country)
            rec.address = '\n'.join(parts) if parts else rec.address

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or (rec.partner_id.name if rec.partner_id else '')
            if rec.phone:
                label = "%s (%s)" % (label, rec.phone)
            res.append((rec.id, label))
        return res



























# # models/courier_company.py
# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
#
# class CourierCompany(models.Model):
#     _name = 'codeware.courier.company'
#     _description = 'Third-party Courier Company / Service Provider'
#     _rec_name = 'name'
#     _order = 'name'
#
#     # <-- add these mixins so the model provides mail.thread methods -->
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#
#     name = fields.Char(string='Name', required=True, index=True, tracking=True)
#     partner_id = fields.Many2one(
#         'res.partner',
#         string='Contact (Partner)',
#         ondelete='set null',
#         help='Link to partner record. You can create/select a partner from the dropdown.'
#     )
#     contact_person = fields.Char(string='Contact Person')
#     phone = fields.Char(string='Phone')
#     email = fields.Char(string='Email')
#     address = fields.Text(string='Address')
#     notes = fields.Text(string='Notes')
#     active = fields.Boolean(string='Active', default=True)
#
#     _sql_constraints = [
#         ('name_uniq', 'unique(name)', 'Courier Company with this name already exists.'),
#     ]
#
#     @api.onchange('partner_id')
#     def _onchange_partner_id_fill_fields(self):
#         """
#         When partner selected:
#          - if name is empty or identical to partner name, set courier name to partner name
#          - copy phone (mobile or phone), email, and full address to courier fields
#          - set contact_person from partner.name if appropriate
#         """
#         for rec in self:
#             p = rec.partner_id
#             if not p:
#                 # nothing to fill
#                 continue
#
#             # Set name if blank or same as partner name
#             if not rec.name or rec.name.strip() == (getattr(p, 'name', '') or '').strip():
#                 rec.name = getattr(p, 'name', rec.name)
#
#             # Contact person
#             rec.contact_person = getattr(p, 'name', rec.contact_person)
#
#             # Prefer mobile then phone (safe getattr usage)
#             rec.phone = getattr(p, 'mobile', None) or getattr(p, 'phone', None) or rec.phone
#
#             # Email (safe)
#             rec.email = getattr(p, 'email', None) or rec.email
#
#             # Build an address text (street, street2, city, state, zip, country)
#             parts = []
#             street = getattr(p, 'street', None)
#             street2 = getattr(p, 'street2', None)
#             if street:
#                 parts.append(street)
#             if street2:
#                 parts.append(street2)
#             city = getattr(p, 'city', None)
#             state = getattr(getattr(p, 'state_id', None), 'name', None)
#             zip_code = getattr(p, 'zip', None)
#             line2 = ', '.join(filter(None, [city, state, zip_code]))
#             if line2:
#                 parts.append(line2)
#             country = getattr(getattr(p, 'country_id', None), 'name', None)
#             if country:
#                 parts.append(country)
#             rec.address = '\n'.join(parts) if parts else rec.address
#
#     def name_get(self):
#         res = []
#         for rec in self:
#             label = rec.name or (rec.partner_id.name if rec.partner_id else '')
#             if rec.phone:
#                 label = "%s (%s)" % (label, rec.phone)
#             res.append((rec.id, label))
#         return res
