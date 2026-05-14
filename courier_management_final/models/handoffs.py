# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from datetime import datetime

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CourierHandoff(models.Model):
    _name = 'courier.handoff'
    _description = 'Courier Handoff / Delivery Handoff'
    _order = 'assigned_datetime desc, id desc'

    name = fields.Char(string='Handoff Reference', required=True, copy=False, default=lambda self: _('New'))
    # picking_id = fields.Many2one('stock.picking', string='Delivery Picking', ondelete='cascade', index=True)
    picking_id = fields.Many2many(
        'stock.picking',
        'handoff_picking_rel',
        'handoff_id', 'picking_id',
        string='Pickings',
        help='Delivery pickings linked to this handoff'
    )
    vehicle_number = fields.Char(string="Vehicle Number")


    sale_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        compute='_compute_sale_id',
        store=True,
        readonly=True,
    )

    partner_id = fields.Many2one('res.partner', string='Recipient', related='picking_id.partner_id', store=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle')
    driver_id = fields.Many2one('hr.employee', string='Driver', help='Employee doing the delivery')
    courier_partner_id = fields.Many2one('res.partner', string='Courier (contact)', help='Contact person for courier company')
    assigned_datetime = fields.Datetime(string='Assigned On')
    picked_datetime = fields.Datetime(string='Picked Up On')
    delivered_datetime = fields.Datetime(string='Delivered On')
    state = fields.Selection(
        [('draft','Draft'), ('assigned','Assigned'), ('picked','Picked Up'), ('delivered','Delivered'), ('cancel','Cancelled')],
        string='Status', default='draft', tracking=True)
    parcel_count = fields.Integer(string='Number of Parcels', default=1)
    # total_weight = fields.Float(string='Total Weight (kg)')
    manifest_ref = fields.Char(string='Manifest / Tracking Ref')
    notes = fields.Text(string='Notes')
    # gps_lat = fields.Float(string='GPS Latitude')
    # gps_lon = fields.Float(string='GPS Longitude')
    created_by = fields.Many2one('res.users', string='Created by', default=lambda self: self.env.user)
    awb_number = fields.Char(string="AWB Number")
    authorized_person = fields.Char(string="Authorised Person")
    serviced_by_id = fields.Many2one('codeware.courier.company', string="Serviced By")
    internal = fields.Boolean(
        string="Internal Courier",
        related="serviced_by_id.internal",
        store=False
    )

    # @api.model
    # def create(self, vals):
    #     # generate sequence name if New
    #     if vals.get('name', _('New')) == _('New') or not vals.get('name'):
    #         seq = self.env['ir.sequence'].sudo().next_by_code('courier.handoff') or '/'
    #         vals['name'] = seq
    #     return super().create(vals)

    @api.model
    def create(self, vals):
        """Support both single-dict create and list-of-dicts create.
           Ensure 'name' is set from sequence if missing or empty.
        """

        # Helper to ensure name exists on a vals dict
        def _ensure_name(v):
            v = dict(v or {})
            if not v.get('name'):
                # Use sudo() so sequence can be generated even if current user lacks rights
                v['name'] = self.env['ir.sequence'].sudo().next_by_code('courier.handoff') or '/'
            return v

        # If a list of dicts passed, handle each one individually, ensuring name
        if isinstance(vals, list):
            records = self.env['courier.handoff']
            for v in vals:
                safe_vals = _ensure_name(v)
                records |= super(CourierHandoff, self).create(safe_vals)
            return records

        # Single dict path: ensure name then create normally
        vals = _ensure_name(vals)
        return super(CourierHandoff, self).create(vals)

    @api.depends('picking_id')
    def _compute_sale_id(self):
        """Compute sale_id from multiple pickings (Many2many)."""
        SaleOrder = self.env['sale.order']
        for rec in self:
            rec.sale_id = False
            picks = rec.picking_id.filtered(lambda p: p)  # <-- fixed field name

            if not picks:
                continue

            sale = False

            # Prefer direct link on any picking
            for p in picks:
                if hasattr(p, 'order_id') and p.order_id:
                    sale = p.order_id
                    break
                if hasattr(p, 'sale_id') and p.sale_id:
                    sale = p.sale_id
                    break

            # Fallback to origin search
            if not sale:
                first = picks[0]
                if first.origin:
                    sale = SaleOrder.search([('name', '=', first.origin)], limit=1)

            rec.sale_id = sale.id if sale else False

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.vehicle_number = self.vehicle_id.license_plate or ''

        else:
            self.vehicle_number = ''



    def action_mark_assigned(self):
        """Mark handoff(s) as assigned and set assigned_datetime."""
        now = fields.Datetime.now()
        for rec in self:
            rec.state = 'assigned'
            rec.assigned_datetime = now
        return True

    def action_mark_picked(self):
        """Mark handoff(s) as picked and set picked_datetime."""
        now = fields.Datetime.now()
        for rec in self:
            rec.state = 'picked'
            rec.picked_datetime = now
        return True

    def action_mark_delivered(self):
        """Mark handoff(s) as delivered and set delivered_datetime."""
        now = fields.Datetime.now()
        for rec in self:
            rec.state = 'delivered'
            rec.delivered_datetime = now
        return True

    def action_cancel(self):
        """Cancel handoff(s)."""
        for rec in self:
            rec.state = 'cancel'
        return True

    def action_print_handoff(self):
        self.ensure_one()
        return self.env.ref(
            'courier_management_final.action_report_courier_handoff'
        ).report_action(self)

    # class StockPicking(models.Model):
#     _inherit = 'stock.picking'
#
#     handoff_ids = fields.One2many('courier.handoff', 'picking_id', string='Handoffs')
#     handoff_count = fields.Integer(string='Handoffs Count', compute='_compute_handoff_count', store=True)
#     primary_handoff_id = fields.Many2one('courier.handoff', string='Primary Handoff',
#                                          compute='_compute_primary_handoff', store=True)
#
#     @api.depends('handoff_ids')
#     def _compute_handoff_count(self):
#         for pick in self:
#             pick.handoff_count = len(pick.handoff_ids)
#
#     @api.depends('handoff_ids', 'handoff_ids.state')
#     def _compute_primary_handoff(self):
#         for pick in self:
#             # pick the most recent handoff or False
#             pick.primary_handoff_id = pick.handoff_ids and pick.handoff_ids[0] or False
#
#     def action_create_handoff(self, vals=None):
#         """Create a handoff record linked to this picking. vals can override defaults."""
#         self.ensure_one()
#         if vals is None:
#             vals = {}
#         # compute parcel_count from move lines if available
#         parcel_count = 0
#         try:
#             if self.move_line_ids_without_package:
#                 for ml in self.move_line_ids_without_package:
#                     # use qty_done if present else product_uom_qty
#                     parcel_count += float(ml.qty_done or ml.product_uom_qty or 0)
#         except Exception:
#             parcel_count = 1
#
#         # Safely get sale id from picking if available, otherwise False
#         sale_id = False
#         try:
#             if hasattr(self, 'sale_id') and self.sale_id:
#                 sale_id = self.sale_id.id
#         except Exception:
#             sale_id = False
#
#         defaults = {
#             'picking_id': self.id,
#             'sale_id': sale_id,
#             'partner_id': self.partner_id.id if self.partner_id else False,
#             'parcel_count': int(parcel_count) if parcel_count else 1,
#             'total_weight': 0.0,
#             'state': 'delivered' if self.state == 'done' else 'assigned',
#             'assigned_datetime': fields.Datetime.now(),
#         }
#         defaults.update(vals)
#         return self.env['courier.handoff'].create(defaults)
#
#     def _create_handoff_if_needed(self):
#         """Create delivered handoff if picking is done and no delivered handoff exists."""
#         for pick in self:
#             if pick.state == 'done':
#                 # avoid duplicates: create only if no handoff with delivered state exists
#                 existing = pick.handoff_ids.filtered(lambda h: h.state == 'delivered')
#                 if not existing:
#                     pick.action_create_handoff({
#                         'state': 'delivered',
#                         'delivered_datetime': fields.Datetime.now(),
#                     })
#
#     # If your instance uses action_done for completion:
#     def action_done(self):
#         res = super(StockPicking, self).action_done()
#         # create handoff after the picking is actually done
#         try:
#             self._create_handoff_if_needed()
#         except Exception:
#             _logger.exception('Failed to auto-create handoff in action_done')
#         return res
#
#     # Some installs use button_validate instead — cover both to be safe
#     def button_validate(self):
#         res = super(StockPicking, self).button_validate()
#         try:
#             self._create_handoff_if_needed()
#         except Exception:
#             _logger.exception('Failed to auto-create handoff in button_validate')
#         return res

    # replace existing StockPicking.handoff related fields/methods
    class StockPicking(models.Model):
        _inherit = 'stock.picking'

        # inverse Many2many matching courier.handoff.picking_id relation table
        handoff_ids = fields.Many2many(
            'courier.handoff',
            'handoff_picking_rel',
            'picking_id', 'handoff_id',
            string='Handoffs',
            readonly=True,
        )

        handoff_count = fields.Integer(string='Handoffs Count', compute='_compute_handoff_count', store=True)
        primary_handoff_id = fields.Many2one('courier.handoff', string='Primary Handoff',
                                             compute='_compute_primary_handoff', store=True)

        @api.depends('handoff_ids')
        def _compute_handoff_count(self):
            for pick in self:
                pick.handoff_count = len(pick.handoff_ids)

        @api.depends('handoff_ids', 'handoff_ids.assigned_datetime')
        def _compute_primary_handoff(self):
            for pick in self:
                pick.primary_handoff_id = (
                    pick.handoff_ids.sorted(
                        key=lambda h: h.assigned_datetime or datetime(1970, 1, 1),
                        reverse=True,
                    )[:1].id
                    if pick.handoff_ids
                    else False
                )

        def action_open_handoffs(self):
            """Open handoffs filtered to show handoffs for this picking."""
            self.ensure_one()
            action = {
                'name': _('Handoffs'),
                'type': 'ir.actions.act_window',
                'res_model': 'courier.handoff',
                'view_mode': 'list,form',
                'domain': [('picking_id', 'in', self.id)],  # Many2many domain uses 'in'
                'context': {'default_picking_id': [self.id]},
            }
            return action

        def action_open_handoffs_multi(self):
            action = {
                'name': _('Handoffs'),
                'type': 'ir.actions.act_window',
                'res_model': 'courier.handoff',
                'view_mode': 'list,form',
                'domain': [('picking_id', 'in', self.ids)],
                'context': {},
            }
            return action


    # def action_open_handoffs(self):
    #     """Open an action window filtered to show handoffs for this picking."""
    #     self.ensure_one()
    #     action = {
    #         'name': _('Handoffs'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'courier.handoff',
    #         'view_mode': 'tree,form',
    #         'domain': [('picking_id', '=', self.id)],
    #         'context': {'default_picking_id': self.id},
    #     }
    #     return action
    #
    # def action_open_handoffs_multi(self):
    #     """Open handoffs for multiple pickings (useful from list view)."""
    #     action = {
    #         'name': _('Handoffs'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'courier.handoff',
    #         'view_mode': 'tree,form',
    #         'domain': [('picking_id', 'in', self.ids)],
    #         'context': {},
    #     }
    #     return action


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _action_confirm(self):
        res = super()._action_confirm()

        for order in self:
            req = order.request_id
            if not req and order.origin:
                # match request by name
                req = self.env['codeware.request'].search([('name', '=', order.origin)], limit=1)

            if req:
                for picking in order.picking_ids:
                    picking.receiver_name = req.customer_name
                    picking.receiver_phone = req.receiver_phone_partner or req.receiver_phone
                    picking.receiver_address = req.customer_address
                    picking.receiver_zip = req.dest_zip
                    picking.priority_type = req.priority_type
                    picking.delivery_description= req.delivery_description

                    # 🔥 NEW FIX → copy serviced by
                    picking.picking_serviced_by_id = req.serviced_by_id

        return res


    # Smart button support
    def action_open_handoffs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Handoffs',
            'res_model': 'courier.handoff',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.handoff_ids.ids)],
        }

