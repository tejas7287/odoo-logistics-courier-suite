# from google.auth import default

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HandoffWizard(models.TransientModel):
    _name = "handoff.wizard"
    _description = "Wizard to Create Handoff (mirror courier.handoff fields)"



    # ✅ Pickings filtered by selected operation type
    picking_id = fields.Many2many(
        'stock.picking',
        'handoff_wizard_picking_rel',
        'wizard_id',
        'picking_id',
        string='Delivery Order Number',
        domain="[('picking_type_id', '=', picking_type_id)]",
        required=True
    )

    # ------------------------ADDED BY ME----------------
    # MODE OF PICKING (controls dropdown behaviour)
    # ✅ ALL operation types
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Operation Type',
        required=True,
        domain="[('default_location_src_id', '=', company_location_id)]"
    )
    company_location_id = fields.Many2one(
        'stock.location',
        string="Company Stock Location",
        compute="_compute_company_location",
        store=False
    )

    def _compute_company_location(self):
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1
        )
        for wiz in self:
            wiz.company_location_id = warehouse.lot_stock_id if warehouse else False

    # ---------------------------------------------------------
    # BASIC FIELDS
    # ---------------------------------------------------------
    name = fields.Char(string='Handoff Reference', default=lambda self: _('New'))
    vehicle_number = fields.Char(string="Vehicle Number")
    driver_id = fields.Many2one('hr.employee', string="Driver")
    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle")
    courier_partner_id = fields.Many2one('res.partner', string="Courier (contact)")
    manifest_ref = fields.Char(string="Manifest / Tracking Ref")
    notes = fields.Text(string="Notes")
    parcel_count = fields.Integer(string='Number of Parcels', default=1)
    assigned_datetime = fields.Datetime(string='Assigned On',default=fields.Datetime.now,readonly=True)
    picked_datetime = fields.Datetime(string='Picked Up On',default=fields.Datetime.now,readonly=True)
    delivered_datetime = fields.Datetime(string='Delivered On')

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('assigned', 'Assigned'),
            ('picked', 'Picked Up'),
            ('delivered', 'Delivered'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True
    )

    created_by = fields.Many2one(
        'res.users',
        string='Created by',
        default=lambda self: self.env.user
    )

    sale_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        readonly=True
    )

    awb_number = fields.Char(string="AWB Number")
    authorized_person = fields.Char(string="Authorised Person")

    serviced_by_id = fields.Many2one(
        'codeware.courier.company',
        string="Serviced By"
    )

    internal = fields.Boolean(
        string="Internal Courier",
        related="serviced_by_id.internal",
        store=False
    )

    # ---------------------------------------------------------
    # DEFAULT VALUES (FROM ACTIVE PICKINGS)
    # ---------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        if 'picking_id' in fields_list:
            fields_list.remove('picking_id')

        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids') or []
        if not active_ids:
            return res

        pickings = self.env['stock.picking'].browse(active_ids)

        # set pickings
        res['picking_id'] = [(6, 0, active_ids)]
        res['parcel_count'] = len(active_ids)

        # set picking mode from first picking
        first = pickings[0]
        if first.picking_type_id:
            res['picking_type_id'] = first.picking_type_id.id

        # serviced by
        if hasattr(first, 'picking_serviced_by_id'):
            res['serviced_by_id'] = first.picking_serviced_by_id.id

        # sale order (safe)
        if hasattr(first, 'order_id') and first.order_id:
            res['sale_id'] = first.order_id.id
        elif hasattr(first, 'sale_id') and first.sale_id:
            res['sale_id'] = first.sale_id.id

        res['state'] = 'delivered' if first.state == 'done' else 'assigned'

        return res

    # ---------------------------------------------------------
    # ONCHANGE HELPERS
    # ---------------------------------------------------------
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        self.vehicle_number = self.vehicle_id.license_plate if self.vehicle_id else ''

    @api.onchange('picking_id')
    def _onchange_picking_id(self):
        picks = self.picking_id
        self.parcel_count = len(picks)

        if picks:
            first = picks[0]
            sale = False
            if hasattr(first, 'order_id') and first.order_id:
                sale = first.order_id
            elif hasattr(first, 'sale_id') and first.sale_id:
                sale = first.sale_id
            elif first.origin:
                sale = self.env['sale.order'].search(
                    [('name', '=', first.origin)], limit=1
                )
            if sale:
                self.sale_id = sale.id

    @api.onchange('vehicle_number')
    def _onchange_vehicle_number(self):
        if not self.vehicle_number:
            self.vehicle_id = False
            self.driver_id = False
            return

        vehicle = self.env['fleet.vehicle'].search(
            [('license_plate', '=', self.vehicle_number)], limit=1
        )

        if vehicle:
            self.vehicle_id = vehicle
            employee = self.env['hr.employee'].search(
                [('work_contact_id', '=', vehicle.driver_id.id)], limit=1
            )
            self.driver_id = employee.id if employee else False
        else:
            self.vehicle_id = False
            self.driver_id = False

    # ---------------------------------------------------------
    # CONFIRM HANDOFF (ALL VALIDATIONS HERE)
    # ---------------------------------------------------------
    # def action_confirm_handoff(self):
    #     self.ensure_one()
    #
    #     # ---------------------------------------------------------
    #     # 1️⃣ BUSINESS VALIDATIONS FIRST (VERY IMPORTANT)
    #     # ---------------------------------------------------------
    #     errors = []
    #
    #     if not self.picked_datetime:
    #         errors.append("Picked Up On is required.")
    #
    #     if not self.authorized_person:
    #         errors.append("Authorized Person is required.")
    #
    #     is_internal = bool(self.serviced_by_id and self.serviced_by_id.internal)
    #
    #     if is_internal:
    #         if not self.vehicle_number:
    #             errors.append("Vehicle Number is required (Internal Courier).")
    #         if not self.driver_id:
    #             errors.append("Driver is required (Internal Courier).")
    #         if not self.vehicle_id:
    #             errors.append("Vehicle is required (Internal Courier).")
    #         if not self.assigned_datetime:
    #             errors.append("Assigned On is required (Internal Courier).")
    #
    #     if errors:
    #         raise UserError("\n".join(errors))
    #
    #     # ---------------------------------------------------------
    #     # 2️⃣.A BLOCK DONE PICKINGS (NEW)
    #     # ---------------------------------------------------------
    #     done_pickings = self.picking_id.filtered(lambda p: p.state == 'done')
    #     if done_pickings:
    #         raise UserError(
    #             _("%s is already validated") %
    #             ", ".join(done_pickings.mapped('name'))
    #         )
    #
    #     # ---------------------------------------------------------
    #     # 3️⃣ AUTO-VALIDATE NON-DONE PICKINGS
    #     # ---------------------------------------------------------
    #     # for picking in self.picking_id:
    #     #     for move in picking.move_ids:
    #     #         move._set_quantity_done(move.product_uom_qty)
    #     #
    #     #     picking.button_validate()
    #     for picking in self.picking_id:
    #
    #         # 1️⃣ Draft → Waiting
    #         if picking.state == 'draft':
    #             picking.action_confirm()
    #
    #         # 2️⃣ Waiting → Ready (reserve stock)
    #         if picking.state in ('confirmed', 'waiting'):
    #             picking.action_assign()
    #
    #         # 3️⃣ Set done quantities
    #         for move in picking.move_ids:
    #             if move.product_uom_qty > 0:
    #                 move._set_quantity_done(move.product_uom_qty)
    #
    #         # 4️⃣ Ready → Done (actual stock movement)
    #         picking.button_validate()
    #
    #     # ---------------------------------------------------------
    #     # 4️⃣ CREATE HANDOFF
    #     # ---------------------------------------------------------
    #     vals = {
    #         'name': self.name if self.name and self.name != _('New') else False,
    #         'driver_id': self.driver_id.id or False,
    #         'vehicle_id': self.vehicle_id.id or False,
    #         'vehicle_number': self.vehicle_number or False,
    #         'courier_partner_id': self.courier_partner_id.id or False,
    #         'authorized_person': self.authorized_person or False,
    #         'awb_number': self.awb_number or False,
    #         'serviced_by_id': self.serviced_by_id.id or False,
    #         'manifest_ref': self.manifest_ref or False,
    #         'notes': self.notes or False,
    #         'parcel_count': int(self.parcel_count or 1),
    #         'assigned_datetime': self.assigned_datetime or False,
    #         'picked_datetime': self.picked_datetime or False,
    #         'delivered_datetime': self.delivered_datetime or False,
    #         'state': self.state or 'draft',
    #         'created_by': self.created_by.id or self.env.user.id,
    #         'sale_id': self.sale_id.id or False,
    #         'picking_id': [(6, 0, self.picking_id.ids)],
    #     }
    #
    #     if not vals.get('name'):
    #         vals.pop('name', None)
    #
    #     handoff = self.env['courier.handoff'].create(vals)
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'courier.handoff',
    #         'view_mode': 'form',
    #         'res_id': handoff.id,
    #         'target': 'current',
    #     }

    def action_confirm_handoff(self):
        self.ensure_one()

        # -------------------------------0--------------------------
        # 1️⃣ BUSINESS VALIDATIONS
        # ---------------------------------------------------------
        errors = []

        if not self.picked_datetime:
            errors.append("Picked Up On is required.")

        # if not self.authorized_person:
        #     errors.append("Authorized Person is required.")

        is_internal = bool(self.serviced_by_id and self.serviced_by_id.internal)

        if is_internal:
            if not self.vehicle_number:
                errors.append("Vehicle Number is required (Internal Courier).")
            if not self.driver_id:
                errors.append("Driver is required (Internal Courier).")
            if not self.vehicle_id:
                errors.append("Vehicle is required (Internal Courier).")
            if not self.assigned_datetime:
                errors.append("Assigned On is required (Internal Courier).")

        if errors:
            raise UserError("\n".join(errors))

        # ---------------------------------------------------------
        # 2️⃣ BLOCK ONLY DONE PICKINGS
        # ---------------------------------------------------------
        done_pickings = self.picking_id.filtered(lambda p: p.state == 'done')
        if done_pickings:
            raise UserError(
                _("%s is already validated") %
                ", ".join(done_pickings.mapped('name'))
            )

        # ---------------------------------------------------------
        # 3️⃣ FORCE EVERYTHING TO DONE
        # ---------------------------------------------------------
        new_dest = self.picking_type_id.default_location_dest_id
        if not new_dest:
            raise UserError(_("Selected Operation Type has no destination location."))

        for picking in self.picking_id:

            # 🔹 1. Draft → Confirm
            if picking.state == 'draft':
                picking.action_confirm()

            # 🔹 2. Any non-done → Assign stock
            picking.action_assign()

            # 🔹 3. Force destination
            picking.location_dest_id = new_dest

            # 🔹 4. Force quantities
            for move in picking.move_ids:
                move.location_dest_id = new_dest
                move._set_quantity_done(move.product_uom_qty)

            # 🔹 5. FORCE validate (skip backorder UI)
            picking.with_context(skip_backorder=True).button_validate()

            # 🔒 HARD GUARANTEE
            if picking.state != 'done':
                raise UserError(
                    _("Picking %s could not be validated to Done.") % picking.name
                )

        # ---------------------------------------------------------
        # 4️⃣ CREATE HANDOFF
        # ---------------------------------------------------------
        vals = {
            'name': self.name if self.name and self.name != _('New') else False,
            'driver_id': self.driver_id.id or False,
            'vehicle_id': self.vehicle_id.id or False,
            'vehicle_number': self.vehicle_number or False,
            'courier_partner_id': self.courier_partner_id.id or False,
            'authorized_person': self.authorized_person or False,
            'awb_number': self.awb_number or False,
            'serviced_by_id': self.serviced_by_id.id or False,
            'manifest_ref': self.manifest_ref or False,
            'notes': self.notes or False,
            'parcel_count': int(self.parcel_count or 1),
            'assigned_datetime': self.assigned_datetime or False,
            'picked_datetime': self.picked_datetime or False,
            'delivered_datetime': self.delivered_datetime or False,
            'state': self.state or 'draft',
            'created_by': self.created_by.id or self.env.user.id,
            'sale_id': self.sale_id.id or False,
            'picking_id': [(6, 0, self.picking_id.ids)],
        }

        if not vals.get('name'):
            vals.pop('name', None)

        handoff = self.env['courier.handoff'].create(vals)

        # Write handoff reference into stock picking
        self.picking_id.write({
            'handoff_ref': handoff.name
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'courier.handoff',
            'view_mode': 'form',
            'res_id': handoff.id,
            'target': 'current',
        }
















































