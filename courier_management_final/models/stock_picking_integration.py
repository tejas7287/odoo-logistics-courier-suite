# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


# ================================================================
# PART 1 — Partner Transit Location Support
# ================================================================
class ResPartner(models.Model):
    _inherit = 'res.partner'

    transit_location_id = fields.Many2one(
        'stock.location',
        string='Transit Location',
        help='Auto-created internal stock.location used when this partner acts as a transit hub.'
    )

    def ensure_transit_location(self):
        """Create transit location for partner only when required."""
        for partner in self:
            if partner.transit_location_id and partner.transit_location_id.exists():
                continue

            stock_root = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
            parent = stock_root.id if stock_root else False

            loc = self.env['stock.location'].create({
                'name': partner.name + " (Hub)",
                'location_id': parent,
                'usage': 'internal',
                'company_id': partner.company_id.id if partner.company_id else self.env.company.id,
            })
            partner.transit_location_id = loc.id
        return True


# ================================================================
# PART 2 — Picking Automation (First Hop + Next Hops)
# ================================================================
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    planned_location_ids = fields.Many2many(
        'stock.location',
        string="Remaining Route Locations",
        help="List of next destinations: Hub B → Hub C → Customer"
    )

    courier_request_id = fields.Many2one(
        'codeware.request',
        string='Courier Request',
        help='Link back to original courier request if present'
    )

    # ----------------------------------------------------------------
    # Create missing partner transit stock.locations
    # ----------------------------------------------------------------
    @api.model
    def _partners_to_locations(self, partners):
        locs = self.env['stock.location']
        for p in partners:
            if not p:
                continue
            if not p.transit_location_id or not p.transit_location_id.exists():
                p.ensure_transit_location()
            if p.transit_location_id and p.transit_location_id.exists():
                locs |= p.transit_location_id
        return locs


    # ----------------------------------------------------------------
    # PART A — Redirect Initial Delivery to First Hub (uses courier.request)
    # ----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        picks = super().create(vals_list)

        for pick in picks:
            try:
                # Only operate for outgoing customer deliveries
                if not pick.picking_type_id or pick.picking_type_id.code != 'outgoing':
                    continue
                if not pick.location_dest_id or pick.location_dest_id.usage != 'customer':
                    continue

                # --- 1) Locate courier request:
                courier_request = pick.courier_request_id
                if not courier_request and pick.origin:
                    # try to find sale.order by origin and then related courier.request (common patterns)
                    sale = self.env['sale.order'].search([('name', '=', pick.origin)], limit=1)
                    if sale:
                        # try common fields on sale to find linked request
                        for fld in ('request_id', 'courier_request_id', 'request_ref', 'request'):
                            if hasattr(sale, fld):
                                candidate = getattr(sale, fld)
                                if candidate:
                                    courier_request = candidate
                                    break
                        # fallback: search codeware.request by sale_order_id if your module uses that link
                        if not courier_request:
                            cr = self.env['codeware.request'].search([('sale_order_id', '=', sale.id)], limit=1)
                            if cr:
                                courier_request = cr

                # --- 2) Read transit partners from courier_request (the ZIP master already populated this field)
                partners = self.env['res.partner']
                used_field = None

                if courier_request:
                    # try multiple possible field names (pick the first non-empty)
                    candidate_fields = [
                        'transit_partner_ids',   # older name
                        'transit_hub_ids',       # field seen in your logs
                        'hub_partner_ids',
                        'transit_partners',
                        'partner_ids',
                        # if the field is a line with partner_id use mapping below
                        'transit_hub_line_ids',
                        'transit_hub_line',
                    ]
                    for fld in candidate_fields:
                        if hasattr(courier_request, fld):
                            val = getattr(courier_request, fld)
                            if val:
                                # If it's a one2many of lines containing partner fields, try to map to partner
                                # Common patterns:
                                #   - direct m2m/one2many to partner: transit_hub_ids (recordset of res.partner)
                                #   - one2many lines: transit_hub_line_ids with partner_id on each line
                                if val and val._name == 'res.partner':
                                    partners = val
                                else:
                                    # try to detect lines with partner_id
                                    try:
                                        partners = val.mapped('partner_id') or val.mapped('hub_partner_id') or val.mapped('partner')
                                    except Exception:
                                        partners = val
                                used_field = fld
                                break
                    # if still not partners, fallback to checking common direct fields
                    if not partners or not partners.ids:
                        # try direct m2m with the most-likely name (transit_hub_ids)
                        if hasattr(courier_request, 'transit_hub_ids'):
                            partners = getattr(courier_request, 'transit_hub_ids') or self.env['res.partner']
                            used_field = 'transit_hub_ids'
                else:
                    partners = self.env['res.partner']
                    used_field = None

                # ----- Debug log: show what we found (helps confirm why redirect may not occur)
                _logger.warning("Create() picking=%s origin=%s courier_request=%s used_partners_field=%s partners=%s",
                                pick.name, pick.origin, bool(courier_request and courier_request.id),
                                used_field or '(none)', partners.mapped('name') if partners else [])

                if not partners or not partners.ids:
                    # no hubs found; do nothing and leave normal warehouse->customer behavior
                    _logger.debug("No transit partners found for picking %s (origin=%s)", pick.name, pick.origin)
                    continue

                # Log for easier debugging
                _logger.info("Picking %s: found partners %s from courier request %s", pick.name, partners.mapped('name'), bool(courier_request and courier_request.id))

                # --- 3) Ensure partner -> location mapping (create location if missing)
                locs = self._partners_to_locations(partners)
                if not locs:
                    _logger.warning("Partners found but no locations created for picking %s", pick.name)
                    continue

                hub_list = list(locs)
                first_hub = hub_list[0]
                remaining_hubs = hub_list[1:]

                final_customer_loc = pick.location_dest_id
                planned_chain = remaining_hubs + [final_customer_loc]

                # --- 4) Redirect initial picking: Warehouse -> Hub A
                pick.write({
                    'location_dest_id': first_hub.id,
                    'planned_location_ids': [(6, 0, [l.id for l in planned_chain])],
                    'courier_request_id': courier_request.id if courier_request else False,
                })

                _logger.info("Redirected picking %s to first hub %s; planned chain: %s",
                             pick.name, first_hub.name, [l.name for l in planned_chain])

            except Exception:
                _logger.exception("Error in create() routing logic for picking %s", pick.id)

        return picks


    # ----------------------------------------------------------------
    # PART B — On Validate, Auto-create Next Hop Picking
    # ----------------------------------------------------------------
    def button_validate(self):
        res = super().button_validate()

        for picking in self:
            try:
                remaining = picking.planned_location_ids
                if not remaining:
                    continue

                next_location = remaining[0]            # next hop
                future_locations = remaining[1:]        # remaining after that

                # CREATE NEXT PICKING
                ptype = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
                if not ptype:
                    _logger.warning("No outgoing picking type found; cannot create next hop for picking %s", picking.name)
                    continue

                next_pick = self.env['stock.picking'].create({
                    'picking_type_id': ptype.id,
                    'location_id': picking.location_dest_id.id,   # current dest becomes source
                    'location_dest_id': next_location.id,
                    'origin': picking.origin,
                    'partner_id': picking.partner_id.id,
                    'planned_location_ids': [(6, 0, [l.id for l in future_locations])],
                    'courier_request_id': picking.courier_request_id.id if picking.courier_request_id else False,
                })

                # COPY MOVES (duplicate moves into next picking)
                for mv in picking.move_lines:
                    mv.copy({
                        'picking_id': next_pick.id,
                        'location_id': next_pick.location_id.id,
                        'location_dest_id': next_pick.location_dest_id.id,
                    })

                next_pick.action_confirm()
                try:
                    next_pick.action_assign()
                except Exception:
                    _logger.exception("Assign failed for next picking %s", next_pick.id)

                # link for traceability (optional)
                try:
                    picking.write({'next_hop_picking_id': next_pick.id})
                    next_pick.write({'prev_hop_picking_id': picking.id})
                except Exception:
                    pass

                _logger.info(
                    "Created next hop picking %s: %s -> %s",
                    next_pick.name, picking.location_dest_id.name, next_location.name
                )

            except Exception:
                _logger.exception("Error creating next hop after validate for picking %s", picking.id)

        return res
