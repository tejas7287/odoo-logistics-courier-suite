# fincode_master.py  (DROP-IN replacement - paste into your module)
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FinCodeMaster(models.Model):
    _name = 'codeware.fincode'
    _description = 'FinCode Master - ZIP / Area master with hubs'

    name = fields.Char('ZIP Code', required=True, index=True)  # ZIP code / external key
    city = fields.Char('City')
    state = fields.Char('State')
    base_price = fields.Float('Base Price', default=0.0)
    # serviced_by_id = fields.Many2one(
    #     'codeware.courier.company',
    #     string='Serviced by',
    #     help='Select third-party courier/service provider that services this PIN code'
    # )
    serviced_by_id = fields.Many2one(
        'codeware.courier.company',
        string="Serviced By",
        default=lambda self: self._default_serviced_by(),
        domain="[('internal', '=', True)]",
        required=True,
    )

    hub_ids = fields.Many2many(
        'res.partner',
        string='Transit Hubs',
        help='Transit hubs (ordered by sequence)', domain=[('is_transit_hub', '=', True)],
    )

    hub_pincodes = fields.Char(
        string='Hub Pincodes (import)',
        help='During import, provide comma-separated PIN codes or a list-like value. These will be resolved to hub_ids.'
    )

    cod_available = fields.Boolean('COD Available', default=False)
    is_internal_courier = fields.Boolean(
        related="serviced_by_id.internal",
        store=True
    )
    final_transit_hub_id = fields.Many2one(
        'res.partner',
        string='Final Transit Hub',
        help='Computed: last transit hub from hub_ids',
        compute='_compute_final_transit_hub',
        store=True,
    )

    @api.depends('hub_ids')
    def _compute_final_transit_hub(self):
        """Pick the 'final' hub for this fincode.
        Preference: last by hub_ids.sequence if present, else last by recordset order.
        """
        for rec in self:
            if not rec.hub_ids:
                rec.final_transit_hub_id = False
                continue
            hubs = rec.hub_ids
            # prefer explicit sequence field if exists
            if 'sequence' in hubs._fields:
                try:
                    last = hubs.sorted('sequence')[-1]
                    rec.final_transit_hub_id = last
                    continue
                except Exception:
                    # fallback below
                    pass
            # fallback: last element by recordset order
            try:
                rec.final_transit_hub_id = hubs[-1]
            except Exception:
                rec.final_transit_hub_id = hubs and hubs[0] or False


    # NEW FIELD: many2many to Transit Hubs
    @api.model
    def _normalize_pincodes_input(self, raw):
        """Accept string, list, or None. Return ordered unique list of digit-only pincode strings."""
        if raw is None:
            return []
        # if import passes a list already (e.g. ["540001","480001"]) handle it
        if isinstance(raw, (list, tuple, set)):
            items = list(raw)
        else:
            # sometimes import may send weird object types; convert to string first
            items = [str(raw)]
        clean = []
        for it in items:
            if it is None:
                continue
            s = str(it).strip()
            if not s:
                continue
            # if cell contains comma-separated values, split them
            parts = [p.strip() for p in s.replace(';',',').split(',') if p.strip() != '']
            for p in parts:
                # keep only digits (defensive)
                p_digits = ''.join(ch for ch in p if ch.isdigit())
                if p_digits and p_digits not in clean:
                    clean.append(p_digits)
        return clean

    @api.model
    def _resolve_pincodes_to_hubs(self, pincodes):
        """Return recordset of transithubs for given list of pincode strings.
        Raise ValidationError listing missing pincodes if some not found.
        """
        if not pincodes:
            return self.env['codeware.transithub'].browse()
        # search all at once
        hubs = self.env['codeware.transithub'].search([('pincode', 'in', pincodes)])
        found = {h.pincode for h in hubs}
        missing = [p for p in pincodes if p not in found]
        if missing:
            raise ValidationError(
                _('Cannot import: the following PIN codes do not match any Transit Hub: %s') % (', '.join(missing))
            )
        # preserve input order
        ordered = self.env['codeware.transithub'].browse()
        for p in pincodes:
            rec = hubs.filtered(lambda r: r.pincode == p)
            if rec:
                ordered |= rec[:1]
        return ordered

    # Utility to handle both single-dict and list-of-dicts from import
    def _prepare_vals_with_hubs(self, vals):
        """Given a single vals dict, if it contains hub_pincodes, resolve and set hub_ids."""
        if not isinstance(vals, dict):
            return vals
        if vals.get('hub_pincodes'):
            raw = vals.get('hub_pincodes')
            pincodes = self._normalize_pincodes_input(raw)
            hubs = self._resolve_pincodes_to_hubs(pincodes)
            vals['hub_ids'] = [(6, 0, hubs.ids)]
        return vals

    @api.model
    def create(self, vals):
        # If import supplies a list of dicts (batch), handle each item
        if isinstance(vals, (list, tuple)):
            new_records = self.env['codeware.fincode']
            for v in vals:
                if not isinstance(v, dict):
                    raise ValidationError(_('Unexpected import payload row type: %s') % type(v))
                v2 = self._prepare_vals_with_hubs(dict(v))
                new = super(FinCodeMaster, self).create(v2)
                new_records |= new
            return new_records
        # single dict path
        if isinstance(vals, dict):
            vals = self._prepare_vals_with_hubs(vals)
        return super(FinCodeMaster, self).create(vals)

    def write(self, vals):
        # For write, Odoo always calls write on a recordset with vals being a dict.
        # However be defensive: if vals contains hub_pincodes, resolve them.
        if isinstance(vals, dict) and 'hub_pincodes' in vals:
            vals = dict(vals)  # copy to avoid mutating original
            raw = vals.get('hub_pincodes') or ''
            pincodes = self._normalize_pincodes_input(raw)
            hubs = self._resolve_pincodes_to_hubs(pincodes)
            vals['hub_ids'] = [(6, 0, hubs.ids)]
        return super(FinCodeMaster, self).write(vals)

    @api.model
    def _default_serviced_by(self):
        return self.env['codeware.courier.company'].search(
            [('internal', '=', True)],
            limit=1
        )

























#
# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
#
# class FinCodeMaster(models.Model):
#     _name = 'codeware.fincode'
#     _description = 'FinCode Master - ZIP / Area master with hubs'
#
#     name = fields.Char('ZIP Code', required=True, index=True)
#     city = fields.Char('City')
#     state = fields.Char('State')
#     base_price = fields.Float('Base Price', default=0.0)
#     hub_ids = fields.Many2many('codeware.transithub', string='Transit Hubs', help='Transit hubs (ordered by sequence)')
#



















#
# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
#
# class FinCodeMaster(models.Model):
#     _name = 'codeware.fincode'
#     _description = 'FinCode Master - ZIP / Area master with hubs'
#
#     name = fields.Char('ZIP Code', required=True, index=True)
#     city = fields.Char('City')
#     state = fields.Char('State')
#     base_price = fields.Float('Base Price', default=0.0)
#     hub_ids = fields.Many2many('codeware.transithub', string='Transit Hubs', help='Transit hubs (ordered by sequence)')
#
#     _sql_constraints = [
#         ('unique_fincode', 'unique(name)', 'FinCode (ZIP) must be unique.'),
#     ]


























# # fincode_master.py  (DROP-IN replacement - paste into your module)
# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
#
# class FinCodeMaster(models.Model):
#     _name = 'codeware.fincode'
#     _description = 'FinCode Master - ZIP / Area master with hubs'
#
#     name = fields.Char('ZIP Code', required=True, index=True)  # ZIP code / external key
#     city = fields.Char('City')
#     state = fields.Char('State')
#     base_price = fields.Float('Base Price', default=0.0)
#     serviced_by_id = fields.Many2one(
#         'codeware.courier.company',
#         string='Serviced by',
#         help='Select third-party courier/service provider that services this PIN code'
#     )
#
#     hub_ids = fields.Many2many(
#         'res.partner',
#         string='Transit Hubs',
#         help='Transit hubs (ordered by sequence)',domain=[('is_transit_hub', '=', True)],
#     )
#
#     hub_pincodes = fields.Char(
#         string='Hub Pincodes (import)',
#         help='During import, provide comma-separated PIN codes or a list-like value. These will be resolved to hub_ids.'
#     )
#
#     cod_available = fields.Boolean('COD Available', default=False)
#
#     @api.model
#     def _normalize_pincodes_input(self, raw):
#         """Accept string, list, or None. Return ordered unique list of digit-only pincode strings."""
#         if raw is None:
#             return []
#         # if import passes a list already (e.g. ["540001","480001"]) handle it
#         if isinstance(raw, (list, tuple, set)):
#             items = list(raw)
#         else:
#             # sometimes import may send weird object types; convert to string first
#             items = [str(raw)]
#         clean = []
#         for it in items:
#             if it is None:
#                 continue
#             s = str(it).strip()
#             if not s:
#                 continue
#             # if cell contains comma-separated values, split them
#             parts = [p.strip() for p in s.replace(';',',').split(',') if p.strip() != '']
#             for p in parts:
#                 # keep only digits (defensive)
#                 p_digits = ''.join(ch for ch in p if ch.isdigit())
#                 if p_digits and p_digits not in clean:
#                     clean.append(p_digits)
#         return clean
#
#     @api.model
#     def _resolve_pincodes_to_hubs(self, pincodes):
#         """Return recordset of transithubs for given list of pincode strings.
#         Raise ValidationError listing missing pincodes if some not found.
#         """
#         if not pincodes:
#             return self.env['codeware.transithub'].browse()
#         # search all at once
#         hubs = self.env['codeware.transithub'].search([('pincode', 'in', pincodes)])
#         found = {h.pincode for h in hubs}
#         missing = [p for p in pincodes if p not in found]
#         if missing:
#             raise ValidationError(
#                 _('Cannot import: the following PIN codes do not match any Transit Hub: %s') % (', '.join(missing))
#             )
#         # preserve input order
#         ordered = self.env['codeware.transithub'].browse()
#         for p in pincodes:
#             rec = hubs.filtered(lambda r: r.pincode == p)
#             if rec:
#                 ordered |= rec[:1]
#         return ordered
#
#     # Utility to handle both single-dict and list-of-dicts from import
#     def _prepare_vals_with_hubs(self, vals):
#         """Given a single vals dict, if it contains hub_pincodes, resolve and set hub_ids."""
#         if not isinstance(vals, dict):
#             return vals
#         if vals.get('hub_pincodes'):
#             raw = vals.get('hub_pincodes')
#             pincodes = self._normalize_pincodes_input(raw)
#             hubs = self._resolve_pincodes_to_hubs(pincodes)
#             vals['hub_ids'] = [(6, 0, hubs.ids)]
#         return vals
#
#     @api.model
#     def create(self, vals):
#         # If import supplies a list of dicts (batch), handle each item
#         if isinstance(vals, (list, tuple)):
#             new_records = self.env['codeware.fincode']
#             for v in vals:
#                 if not isinstance(v, dict):
#                     raise ValidationError(_('Unexpected import payload row type: %s') % type(v))
#                 v2 = self._prepare_vals_with_hubs(dict(v))
#                 new = super(FinCodeMaster, self).create(v2)
#                 new_records |= new
#             return new_records
#         # single dict path
#         if isinstance(vals, dict):
#             vals = self._prepare_vals_with_hubs(vals)
#         return super(FinCodeMaster, self).create(vals)
#
#     def write(self, vals):
#         # For write, Odoo always calls write on a recordset with vals being a dict.
#         # However be defensive: if vals contains hub_pincodes, resolve them.
#         if isinstance(vals, dict) and 'hub_pincodes' in vals:
#             vals = dict(vals)  # copy to avoid mutating original
#             raw = vals.get('hub_pincodes') or ''
#             pincodes = self._normalize_pincodes_input(raw)
#             hubs = self._resolve_pincodes_to_hubs(pincodes)
#             vals['hub_ids'] = [(6, 0, hubs.ids)]
#         return super(FinCodeMaster, self).write(vals)
#
#     @api.model
#     def _normalize_hub_ids_input(self, raw):
#         if raw is None:
#             return []
#         if isinstance(raw, (list, tuple, set)):
#             items = list(raw)
#         else:
#             items = [str(raw)]
#         clean = []
#         for it in items:
#             if it is None:
#                 continue
#             s = str(it).strip()
#             if not s:
#                 continue
#             parts = [p.strip() for p in s.replace(';', ',').split(',') if p.strip() != '']
#             for p in parts:
#                 if p not in clean:
#                     clean.append(p)
#         return clean
#
#     @api.model
#     def _resolve_hub_ids_from_keys(self, keys, create_missing=False):
#         Partner = self.env['res.partner']
#         ordered = Partner.browse()
#         missing = []
#         to_create = []
#
#         for k in keys:
#             if not k:
#                 continue
#             # 1) external id (module.record)
#             if '.' in k:
#                 rec = self.env.ref(k, raise_if_not_found=False)
#                 if rec:
#                     ordered |= rec
#                     continue
#                 else:
#                     # treat as not found for now
#                     missing.append(k)
#                     continue
#             # 2) numeric DB id
#             if k.isdigit():
#                 rec = Partner.browse(int(k))
#                 if rec.exists():
#                     ordered |= rec
#                     continue
#                 else:
#                     missing.append(k)
#                     continue
#             # 3) name match (case-insensitive exact)
#             candidates = Partner.search([('name', 'ilike', k)], limit=10)
#             matched = candidates.filtered(lambda r: (r.name or '').strip().lower() == k.strip().lower())
#             if matched:
#                 ordered |= matched[:1]
#                 continue
#             # not found
#             if create_missing:
#                 to_create.append({'name': k})
#             else:
#                 missing.append(k)
#
#         if missing:
#             raise ValidationError(_('Cannot import: these hub keys could not be resolved: %s') % (', '.join(missing)))
#
#         for vals in to_create:
#             newp = Partner.create(vals)
#             ordered |= newp
#
#         return ordered
#
#     # Then update your _prepare_vals_with_hubs (or create wrapper) to handle hub_ids during import:
#     def _prepare_vals_with_hubs(self, vals):
#         if not isinstance(vals, dict):
#             return vals
#         # if user mapped hub_ids as names/ids/external_ids in import, handle it
#         if 'hub_ids' in vals and vals.get('hub_ids'):
#             raw = vals.get('hub_ids')
#             keys = self._normalize_hub_ids_input(raw)
#             create_missing = bool(vals.get('hub_create_contacts'))
#             partners = self._resolve_hub_ids_from_keys(keys, create_missing=create_missing)
#             vals['hub_ids'] = [(6, 0, partners.ids)]
#             # remove helper flag if present
#             vals.pop('hub_create_contacts', None)
#             return vals
#
#         # (keep your existing hub_contact_keys / hub_pincodes logic if present)
#         if vals.get('hub_contact_keys') or vals.get('hub_pincodes'):
#             # ... existing handlers ...
#             pass
#
#         return vals
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
# # # fincode_master.py  (DROP-IN replacement - paste into your module)
# # from odoo import models, fields, api, _
# # from odoo.exceptions import ValidationError
# #
# # class FinCodeMaster(models.Model):
# #     _name = 'codeware.fincode'
# #     _description = 'FinCode Master - ZIP / Area master with hubs'
# #
# #     name = fields.Char('ZIP Code', required=True, index=True)  # ZIP code / external key
# #     city = fields.Char('City')
# #     state = fields.Char('State')
# #     base_price = fields.Float('Base Price', default=0.0)
# #     serviced_by_id = fields.Many2one(
# #         'codeware.courier.company',
# #         string='Serviced by',
# #         help='Select third-party courier/service provider that services this PIN code'
# #     )
# #
# #     hub_ids = fields.Many2many(
# #         'res.partner',
# #         string='Transit Hubs',
# #         help='Transit hubs (ordered by sequence)',domain=[('is_transit_hub', '=', True)],
# #     )
# #
# #     hub_pincodes = fields.Char(
# #         string='Hub Pincodes (import)',
# #         help='During import, provide comma-separated PIN codes or a list-like value. These will be resolved to hub_ids.'
# #     )
# #
# #     cod_available = fields.Boolean('COD Available', default=False)
# #
# #     @api.model
# #     def _normalize_pincodes_input(self, raw):
# #         """Accept string, list, or None. Return ordered unique list of digit-only pincode strings."""
# #         if raw is None:
# #             return []
# #         # if import passes a list already (e.g. ["540001","480001"]) handle it
# #         if isinstance(raw, (list, tuple, set)):
# #             items = list(raw)
# #         else:
# #             # sometimes import may send weird object types; convert to string first
# #             items = [str(raw)]
# #         clean = []
# #         for it in items:
# #             if it is None:
# #                 continue
# #             s = str(it).strip()
# #             if not s:
# #                 continue
# #             # if cell contains comma-separated values, split them
# #             parts = [p.strip() for p in s.replace(';',',').split(',') if p.strip() != '']
# #             for p in parts:
# #                 # keep only digits (defensive)
# #                 p_digits = ''.join(ch for ch in p if ch.isdigit())
# #                 if p_digits and p_digits not in clean:
# #                     clean.append(p_digits)
# #         return clean
# #
# #     @api.model
# #     def _resolve_pincodes_to_hubs(self, pincodes):
# #         """Return recordset of transithubs for given list of pincode strings.
# #         Raise ValidationError listing missing pincodes if some not found.
# #         """
# #         if not pincodes:
# #             return self.env['codeware.transithub'].browse()
# #         # search all at once
# #         hubs = self.env['codeware.transithub'].search([('pincode', 'in', pincodes)])
# #         found = {h.pincode for h in hubs}
# #         missing = [p for p in pincodes if p not in found]
# #         if missing:
# #             raise ValidationError(
# #                 _('Cannot import: the following PIN codes do not match any Transit Hub: %s') % (', '.join(missing))
# #             )
# #         # preserve input order
# #         ordered = self.env['codeware.transithub'].browse()
# #         for p in pincodes:
# #             rec = hubs.filtered(lambda r: r.pincode == p)
# #             if rec:
# #                 ordered |= rec[:1]
# #         return ordered
# #
# #     # Utility to handle both single-dict and list-of-dicts from import
# #     def _prepare_vals_with_hubs(self, vals):
# #         """Given a single vals dict, if it contains hub_pincodes, resolve and set hub_ids."""
# #         if not isinstance(vals, dict):
# #             return vals
# #         if vals.get('hub_pincodes'):
# #             raw = vals.get('hub_pincodes')
# #             pincodes = self._normalize_pincodes_input(raw)
# #             hubs = self._resolve_pincodes_to_hubs(pincodes)
# #             vals['hub_ids'] = [(6, 0, hubs.ids)]
# #         return vals
# #
# #     @api.model
# #     def create(self, vals):
# #         # If import supplies a list of dicts (batch), handle each item
# #         if isinstance(vals, (list, tuple)):
# #             new_records = self.env['codeware.fincode']
# #             for v in vals:
# #                 if not isinstance(v, dict):
# #                     raise ValidationError(_('Unexpected import payload row type: %s') % type(v))
# #                 v2 = self._prepare_vals_with_hubs(dict(v))
# #                 new = super(FinCodeMaster, self).create(v2)
# #                 new_records |= new
# #             return new_records
# #         # single dict path
# #         if isinstance(vals, dict):
# #             vals = self._prepare_vals_with_hubs(vals)
# #         return super(FinCodeMaster, self).create(vals)
# #
# #     def write(self, vals):
# #         # For write, Odoo always calls write on a recordset with vals being a dict.
# #         # However be defensive: if vals contains hub_pincodes, resolve them.
# #         if isinstance(vals, dict) and 'hub_pincodes' in vals:
# #             vals = dict(vals)  # copy to avoid mutating original
# #             raw = vals.get('hub_pincodes') or ''
# #             pincodes = self._normalize_pincodes_input(raw)
# #             hubs = self._resolve_pincodes_to_hubs(pincodes)
# #             vals['hub_ids'] = [(6, 0, hubs.ids)]
# #         return super(FinCodeMaster, self).write(vals)
# #
# #     @api.model
# #     def _normalize_hub_ids_input(self, raw):
# #         if raw is None:
# #             return []
# #         if isinstance(raw, (list, tuple, set)):
# #             items = list(raw)
# #         else:
# #             items = [str(raw)]
# #         clean = []
# #         for it in items:
# #             if it is None:
# #                 continue
# #             s = str(it).strip()
# #             if not s:
# #                 continue
# #             parts = [p.strip() for p in s.replace(';', ',').split(',') if p.strip() != '']
# #             for p in parts:
# #                 if p not in clean:
# #                     clean.append(p)
# #         return clean
# #
# #     @api.model
# #     def _resolve_hub_ids_from_keys(self, keys, create_missing=False):
# #         Partner = self.env['res.partner']
# #         ordered = Partner.browse()
# #         missing = []
# #         to_create = []
# #
# #         for k in keys:
# #             if not k:
# #                 continue
# #             # 1) external id (module.record)
# #             if '.' in k:
# #                 rec = self.env.ref(k, raise_if_not_found=False)
# #                 if rec:
# #                     ordered |= rec
# #                     continue
# #                 else:
# #                     # treat as not found for now
# #                     missing.append(k)
# #                     continue
# #             # 2) numeric DB id
# #             if k.isdigit():
# #                 rec = Partner.browse(int(k))
# #                 if rec.exists():
# #                     ordered |= rec
# #                     continue
# #                 else:
# #                     missing.append(k)
# #                     continue
# #             # 3) name match (case-insensitive exact)
# #             candidates = Partner.search([('name', 'ilike', k)], limit=10)
# #             matched = candidates.filtered(lambda r: (r.name or '').strip().lower() == k.strip().lower())
# #             if matched:
# #                 ordered |= matched[:1]
# #                 continue
# #             # not found
# #             if create_missing:
# #                 to_create.append({'name': k})
# #             else:
# #                 missing.append(k)
# #
# #         if missing:
# #             raise ValidationError(_('Cannot import: these hub keys could not be resolved: %s') % (', '.join(missing)))
# #
# #         for vals in to_create:
# #             newp = Partner.create(vals)
# #             ordered |= newp
# #
# #         return ordered
# #
# #     # Then update your _prepare_vals_with_hubs (or create wrapper) to handle hub_ids during import:
# #     def _prepare_vals_with_hubs(self, vals):
# #         if not isinstance(vals, dict):
# #             return vals
# #         # if user mapped hub_ids as names/ids/external_ids in import, handle it
# #         if 'hub_ids' in vals and vals.get('hub_ids'):
# #             raw = vals.get('hub_ids')
# #             keys = self._normalize_hub_ids_input(raw)
# #             create_missing = bool(vals.get('hub_create_contacts'))
# #             partners = self._resolve_hub_ids_from_keys(keys, create_missing=create_missing)
# #             vals['hub_ids'] = [(6, 0, partners.ids)]
# #             # remove helper flag if present
# #             vals.pop('hub_create_contacts', None)
# #             return vals
# #
# #         # (keep your existing hub_contact_keys / hub_pincodes logic if present)
# #         if vals.get('hub_contact_keys') or vals.get('hub_pincodes'):
# #             # ... existing handlers ...
# #             pass
# #
# #         return vals
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# # #
# # # from odoo import models, fields, api, _
# # # from odoo.exceptions import ValidationError
# # #
# # # class FinCodeMaster(models.Model):
# # #     _name = 'codeware.fincode'
# # #     _description = 'FinCode Master - ZIP / Area master with hubs'
# # #
# # #     name = fields.Char('ZIP Code', required=True, index=True)
# # #     city = fields.Char('City')
# # #     state = fields.Char('State')
# # #     base_price = fields.Float('Base Price', default=0.0)
# # #     hub_ids = fields.Many2many('codeware.transithub', string='Transit Hubs', help='Transit hubs (ordered by sequence)')
# # #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# # #
# # # from odoo import models, fields, api, _
# # # from odoo.exceptions import ValidationError
# # #
# # # class FinCodeMaster(models.Model):
# # #     _name = 'codeware.fincode'
# # #     _description = 'FinCode Master - ZIP / Area master with hubs'
# # #
# # #     name = fields.Char('ZIP Code', required=True, index=True)
# # #     city = fields.Char('City')
# # #     state = fields.Char('State')
# # #     base_price = fields.Float('Base Price', default=0.0)
# # #     hub_ids = fields.Many2many('codeware.transithub', string='Transit Hubs', help='Transit hubs (ordered by sequence)')
# # #
# # #     _sql_constraints = [
# # #         ('unique_fincode', 'unique(name)', 'FinCode (ZIP) must be unique.'),
# # #     ]
